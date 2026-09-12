#!/usr/bin/env python3
"""
collect_panel.py — ambil transkrip lewat panel YouTube, jalan lama tanpa diawasi.

Kenapa panel: endpoint caption (/api/timedtext) memblokir IP ini secara
kumulatif (terukur: 74 video lalu 429, blokir 23j40m, memperlambat 2x tidak
menolong). Panel memakai endpoint lain (youtubei get_panel) yang tidak
terthrottle, dan teksnya sudah divalidasi identik dengan jalur API
(15.621 karakter / 2.362 kata, rasio 1.000).

TIGA LAPIS PENGAMAN AUDIO — tidak ada suara yang mungkin keluar:
  1. Chrome dijalankan --headless=new --mute-audio --disable-audio-output
  2. Network.setBlockedURLs memblokir *googlevideo.com* di level jaringan
  3. Setiap evaluasi JS mem-pause + mute + volume 0 semua elemen media

Dipakai:
    python3 scripts/collect_panel.py --limit 40
    python3 scripts/collect_panel.py --kind pidato --limit 20
    python3 scripts/collect_panel.py --retry-failed

Progres dicatat per baris di data/panel-progress.jsonl, jadi bisa dihentikan
kapan saja dan dilanjutkan tanpa mengulang.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "panel_raw"
PROGRESS = DATA / "panel-progress.jsonl"
WORKLIST = DATA / "worklist.json"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = Path("/tmp/yt-collector-profile")
PORT = 9333

# --------------------------------------------------------------------- JS ---

QUIET_JS = ("(() => { document.querySelectorAll('video,audio').forEach("
            "e => { try { e.pause(); e.muted = true; e.volume = 0; } catch (x) {} }); return 1; })()")

META_JS = r"""(() => {
  const p = window.ytInitialPlayerResponse || {};
  const v = p.videoDetails || {};
  const tracks = (p.captions && p.captions.playerCaptionsTracklistRenderer
    && p.captions.playerCaptionsTracklistRenderer.captionTracks) || [];
  return JSON.stringify({
    title: v.title || '', author: v.author || '',
    lengthSeconds: v.lengthSeconds ? Number(v.lengthSeconds) : null,
    trackCount: tracks.length,
    tracks: tracks.map(x => ({ code: x.languageCode,
      name: (x.name && x.name.simpleText) || '', generated: x.kind === 'asr' }))
  });
})()"""

CLICK_JS = r"""(() => {
  const b = [...document.querySelectorAll('button')]
    .find(x => /show transcript|transkrip/i.test(x.textContent || ''));
  if (b) { b.click(); return 'clicked'; }
  return 'wait';
})()"""

SEG_COUNT_JS = "document.querySelectorAll('transcript-segment-view-model').length"

PANEL_JS = r"""(() => {
  const segs = [...document.querySelectorAll('transcript-segment-view-model')];
  const parse = t => { const p = t.split(':').map(Number);
    return p.length === 3 ? p[0]*3600 + p[1]*60 + p[2] : p[0]*60 + p[1]; };
  return segs.map(s => {
    const ts = s.querySelector('.ytwTranscriptSegmentViewModelTimestamp');
    const tx = s.querySelector('span[role=text]') || s.querySelector('span');
    return { t: ts ? ts.textContent.trim() : '', text: tx ? tx.textContent.trim() : '' };
  }).filter(r => r.t).map(r => ({ start: parse(r.t), text: r.text }));
})()"""


# ---------------------------------------------------------------- CDP klien ---

class CDP:
    """Klien websocket CDP minimal, tanpa dependensi."""

    def __init__(self, ws_url: str):
        u = urlparse(ws_url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
             f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
             f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        self.sock.recv(4096)
        self._id = 0
        self._buf = b""

    def _send(self, method: str, params: dict | None = None, session: str | None = None):
        self._id += 1
        payload = {"id": self._id, "method": method, "params": params or {}}
        if session:
            payload["sessionId"] = session
        data = json.dumps(payload).encode()
        mask = os.urandom(4)
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < (1 << 16):
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        hdr += mask
        self.sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        return self._id

    def _recv_frame(self) -> str:
        while True:
            head = self.sock.recv(2)
            if len(head) < 2:
                raise ConnectionError("socket ditutup")
            length = head[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", self.sock.recv(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self.sock.recv(8))[0]
            data = b""
            while len(data) < length:
                chunk = self.sock.recv(length - len(data))
                if not chunk:
                    break
                data += chunk
            return data.decode("utf-8", "ignore")

    def call(self, method: str, params: dict | None = None, session: str | None = None,
             timeout: float = 30.0):
        want = self._send(method, params, session)
        self.sock.settimeout(timeout)
        while True:
            msg = json.loads(self._recv_frame())
            if msg.get("id") == want:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def eval(self, expr: str, session: str, timeout: float = 30.0):
        r = self.call("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True, "awaitPromise": True},
                      session=session, timeout=timeout)
        return (r.get("result") or {}).get("value")

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


# ------------------------------------------------------------------ browser ---

def launch_browser() -> None:
    """Nyalakan Chrome headless khusus, audio dimatikan sejak proses lahir."""
    PROFILE.mkdir(parents=True, exist_ok=True)
    if is_up():
        return
    cmd = [
        CHROME,
        "--headless=new",
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE}",
        "--no-first-run", "--no-default-browser-check",
        "--disable-gpu", "--disable-extensions", "--disable-background-networking",
        "--mute-audio",              # lapis 1a
        "--disable-audio-output",    # lapis 1b
        "--window-size=1280,900",
        "about:blank",
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        if is_up():
            time.sleep(1.0)
            return
        time.sleep(1.0)
    raise SystemExit("Chrome headless gagal start")


def is_up() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def page_target() -> tuple[str, str]:
    """Kembalikan (targetId, webSocketDebuggerUrl) untuk satu tab page."""
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=5) as r:
        tabs = json.loads(r.read().decode())
    for t in tabs:
        if t.get("type") == "page":
            return t["id"], t["webSocketDebuggerUrl"]
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?about:blank", timeout=5) as r:
        t = json.loads(r.read().decode())
    return t["id"], t["webSocketDebuggerUrl"]


# ------------------------------------------------------------------ kolektor ---

def pick_track(tracks: list[dict]) -> dict | None:
    for t in tracks:
        if str(t.get("code", "")).startswith("id"):
            return t
    return None


def collect_one(cdp: CDP, session: str, video_id: str,
                click_wait: int = 22, seg_wait: int = 40) -> dict:
    cdp.call("Page.navigate", {"url": f"https://www.youtube.com/watch?v={video_id}"},
             session=session, timeout=45)
    # tunggu pemutar siap
    for _ in range(30):
        time.sleep(1.0)
        try:
            ready = cdp.eval("!!window.ytInitialPlayerResponse", session)
        except Exception:
            ready = False
        if ready:
            break
        cdp.eval(QUIET_JS, session)
    cdp.eval(QUIET_JS, session)

    try:
        meta = json.loads(cdp.eval(META_JS, session) or "{}")
    except Exception:
        meta = {}

    track = pick_track(meta.get("tracks") or [])
    if not track:
        cdp.eval(QUIET_JS, session)
        return {"id": video_id, "status": "no_indonesian_track",
                "title": meta.get("title", ""), "tracks": meta.get("tracks", [])}

    clicked = False
    for _ in range(click_wait):
        try:
            if cdp.eval(CLICK_JS, session) == "clicked":
                clicked = True
                break
        except Exception:
            pass
        time.sleep(1.0)
    cdp.eval(QUIET_JS, session)

    if not clicked:
        return {"id": video_id, "status": "no_panel", "title": meta.get("title", "")}

    segs = []
    for _ in range(seg_wait):
        try:
            n = cdp.eval(SEG_COUNT_JS, session)
            if n and int(n) > 3:
                segs = cdp.eval(PANEL_JS, session) or []
                if len(segs) > 3:
                    break
        except Exception:
            pass
        time.sleep(1.0)
    cdp.eval(QUIET_JS, session)

    if len(segs) <= 3:
        return {"id": video_id, "status": "empty_panel",
                "segments": len(segs), "title": meta.get("title", "")}

    snippets = []
    for i, row in enumerate(segs):
        nxt = segs[i + 1]["start"] if i + 1 < len(segs) else row["start"] + 3
        snippets.append({
            "text": row["text"],
            "start": float(row["start"]),
            "duration": max(round(nxt - row["start"], 3), 0.5),
        })

    raw = {
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": meta.get("title", ""),
        "channel": meta.get("author", ""),
        "selection_reason": "panel_fetch",
        "discovery_origins": ["official_channel"],
        "available_tracks": meta.get("tracks", []),
        "status": "ok",
        "language": track.get("name") or "Indonesian",
        "language_code": track.get("code", "id"),
        "is_generated": bool(track.get("generated")),
        "is_translatable": True,
        "fetch_method": "transcript_panel",
        "snippet_count": len(snippets),
        "raw_snippets": snippets,
    }
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{video_id}.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")

    return {"id": video_id, "status": "ok", "segments": len(snippets),
            "chars": sum(len(s["text"]) for s in snippets),
            "duration": meta.get("lengthSeconds"),
            "is_generated": raw["is_generated"],
            "title": (meta.get("title") or "")[:70],
            "channel": meta.get("author", "")}


def load_done() -> set[str]:
    done = set()
    if PROGRESS.exists():
        for line in PROGRESS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") == "ok":
                done.add(r["id"])
    return done


def append(row: dict) -> None:
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40, help="jumlah video per jalan")
    ap.add_argument("--kind", default=None,
                    help="pidato | keterangan_pers | ambigu | kunjungan (kosong = prioritas)")
    ap.add_argument("--retry-failed", action="store_true",
                    help="coba lagi yang sebelumnya gagal (bukan no_indonesian_track)")
    ap.add_argument("--pause", type=float, default=1.5, help="jeda antar video (detik)")
    ap.add_argument("--id", action="append", default=None,
                    help="ambil video tertentu (boleh diulang), mengabaikan daftar kerja")
    args = ap.parse_args()

    if args.id:
        batch = [{"video_id": v, "kind": "manual", "title": "(diminta manual)"} for v in args.id]
        print(f"mode manual: {len(batch)} video")
        launch_browser()
        target_id, ws = page_target()
        cdp = CDP(ws)
        session = cdp.call("Target.attachToTarget",
                           {"targetId": target_id, "flatten": True})["sessionId"]
        cdp.call("Page.enable", session=session)
        cdp.call("Network.enable", session=session)
        cdp.call("Network.setBlockedURLs",
                 {"urls": ["*googlevideo.com*", "*manifest.googlevideo.com*"]}, session=session)
        ok = 0
        for i, item in enumerate(batch, 1):
            vid = item["video_id"]
            try:
                row = collect_one(cdp, session, vid)
            except Exception as exc:
                row = {"id": vid, "status": "error",
                       "error": f"{type(exc).__name__}: {str(exc)[:150]}"}
            row["index"] = i
            row["kind"] = "manual"
            append(row)
            if row["status"] == "ok":
                ok += 1
                print(f'{i:>3}/{len(batch)} OK   {vid}  {row["segments"]:>4} seg  '
                      f'{row.get("duration")}s  {row["title"][:50]}')
            else:
                print(f'{i:>3}/{len(batch)} {row["status"]:<16} {vid}')
        cdp.close()
        print(f"\nselesai: {ok}/{len(batch)} berhasil")
        return 0

    wl = json.loads(WORKLIST.read_text(encoding="utf-8"))
    todo = wl["todo"]

    done = load_done()
    failed = set()
    if PROGRESS.exists():
        for line in PROGRESS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") not in ("ok",):
                failed.add(r["id"])

    PRIORITY = {"pidato": 0, "keterangan_pers": 1, "ambigu": 2, "kunjungan": 3}
    pool = [t for t in todo if t["video_id"] not in done]
    if args.kind:
        pool = [t for t in pool if t["kind"] == args.kind]
    elif not args.retry_failed:
        pool = [t for t in pool if t["video_id"] not in failed]
    elif args.retry_failed:
        pool = [t for t in pool if t["video_id"] in failed]
    pool.sort(key=lambda t: PRIORITY.get(t["kind"], 9))

    batch = pool[:args.limit]
    if not batch:
        print("tidak ada yang perlu diambil")
        return 0

    print(f"daftar kerja : {len(todo):,} | sudah ok: {len(done):,} | batch ini: {len(batch)}")
    launch_browser()
    target_id, ws = page_target()
    cdp = CDP(ws)
    session = cdp.call("Target.attachToTarget",
                       {"targetId": target_id, "flatten": True})["sessionId"]
    cdp.call("Page.enable", session=session)
    cdp.call("Network.enable", session=session)
    # LAPIS 2: blokir media di level jaringan
    cdp.call("Network.setBlockedURLs",
             {"urls": ["*googlevideo.com*", "*manifest.googlevideo.com*"]}, session=session)

    ok = 0
    for i, item in enumerate(batch, 1):
        vid = item["video_id"]
        try:
            row = collect_one(cdp, session, vid)
        except Exception as exc:
            row = {"id": vid, "status": "error",
                   "error": f"{type(exc).__name__}: {str(exc)[:150]}"}
        row["index"] = i
        row["kind"] = item["kind"]
        row["known_title"] = item["title"][:90]
        append(row)
        if row["status"] == "ok":
            ok += 1
            print(f'{i:>3}/{len(batch)} OK        {vid}  {row["segments"]:>4} seg  '
                  f'{row.get("duration")}s  {row["title"][:46]}')
        else:
            print(f'{i:>3}/{len(batch)} {row["status"]:<17} {vid}  {item["title"][:46]}')
        time.sleep(args.pause + random.uniform(0, 0.8))

    cdp.close()
    print(f"\nselesai: {ok}/{len(batch)} berhasil")
    print(f"progres  : {PROGRESS}")
    print(f"raw      : {RAW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
