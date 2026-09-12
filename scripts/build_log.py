#!/usr/bin/env python3
"""
build_log.py — ubah korpus (library) jadi arsip pidato yang bisa ditelusuri.

Masukan  : engine/data/prabowo/  (analysis.json, manifest.json, metadata.json, raw/*.json)
Keluaran : data/speeches/<slug>.json   satu berkas per pidato, lengkap dengan transkrip + cap waktu
           data/index.json             daftar ringkas untuk web
           data/coverage.json          peta cakupan + lubang yang jujur
           data/meta.json              asal-usul build (provenance)

Prinsip: setiap klaim harus bisa ditelusuri balik ke video_id + detik.
Transkrip penuh disertakan karena itu yang membuat klaim bisa diverifikasi.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
OUT = ROOT / "data"
WIB = timezone(timedelta(hours=7))

# ---------------------------------------------------------------------------
# Sumber korpus.
#
# Repo korpus sengaja TIDAK mempublikasikan `manifest.json` dan `raw/`
# (keduanya di .gitignore sana), jadi engine tidak cukup untuk build penuh.
# Arsip ini justru tempat transkrip penuhnya dipublikasikan.
#
# Urutan pencarian:
#   1. argumen --source PATH
#   2. variabel lingkungan CORPUS_SOURCE
#   3. working copy korpus di sebelah repo ini
#   4. engine/data/<profile>  (hanya kalau sudah ada raw+manifest)
# ---------------------------------------------------------------------------

def resolve_source() -> Path:
    if "--source" in sys.argv:
        p = Path(sys.argv[sys.argv.index("--source") + 1]).expanduser().resolve()
        return p
    env = os.environ.get("CORPUS_SOURCE")
    if env:
        return Path(env).expanduser().resolve()
    candidates = [
        ROOT.parent / "prabowo-speech-wordcount" / "data" / "prabowo",
        ENGINE / "data" / "prabowo",
    ]
    for c in candidates:
        if (c / "analysis.json").exists() and (c / "raw").is_dir():
            return c
    # Tidak ada yang lengkap — kembalikan kandidat pertama supaya pesan
    # errornya menunjuk tempat yang diharapkan.
    return candidates[0]


SRC = resolve_source()

# Paragraf dibentuk dari beberapa snippet supaya enak dibaca, tapi cap waktunya
# tetap dipegang oleh snippet pertama. Batas ini yang menentukan panjang blok.
PARA_MIN_CHARS = 260
PARA_MAX_CHARS = 620
PARA_HARD_MAX = 900


def slugify(text: str, max_words: int = 7) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    words = [w for w in text.split() if w and w not in {
        "full", "fragment", "breaking", "news", "live", "lengkap", "resmi",
        "pidato", "presiden", "prabowo", "subianto", "sambutan",
    }]
    return "-".join(words[:max_words]) or "pidato"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def merge_paragraphs(snippets: list[dict]) -> list[dict]:
    """Gabungkan snippet jadi paragraf; cap waktu = snippet pertama tiap blok."""
    blocks: list[dict] = []
    buf: list[str] = []
    start = None
    dur = 0.0

    def flush():
        nonlocal buf, start, dur
        if buf and start is not None:
            text = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if text:
                blocks.append({
                    "t": round(start, 2),
                    "d": round(dur, 2),
                    "text": text,
                })
        buf, start, dur = [], None, 0.0

    for sn in snippets:
        text = re.sub(r"\s+", " ", sn.get("text", "")).strip()
        if not text:
            continue
        if start is None:
            start = float(sn.get("start", 0.0))
        buf.append(text)
        dur += float(sn.get("duration", 0.0))
        joined_len = sum(len(x) + 1 for x in buf)
        ends_sentence = text.endswith((".", "?", "!", '"', ":"))
        if joined_len >= PARA_HARD_MAX or (joined_len >= PARA_MIN_CHARS and ends_sentence):
            flush()
    flush()
    return blocks


def main() -> int:
    analysis = load_json(SRC / "analysis.json")
    manifest = load_json(SRC / "manifest.json")
    metadata = load_json(SRC / "metadata.json")

    by_id_manifest = {s["id"]: s for s in manifest.get("sources", [])}
    by_id_variant = {v["id"]: v for v in analysis.get("variants", [])}

    # `variants` = daftar LENGKAP semua caption yang lolos saring (128 item).
    # `manifest.sources` cuma memuat yang terpilih jadi kanonik (67). Untuk
    # traceability kita butuh yang lengkap, termasuk unggahan duplikat.
    by_event: dict[str, list[dict]] = {}
    for v in analysis.get("variants", []):
        by_event.setdefault(v.get("event_group"), []).append(v)

    speeches = []
    (OUT / "speeches").mkdir(parents=True, exist_ok=True)

    for src in analysis["sources"]:
        vid = src["id"]
        raw_path = SRC / "raw" / f"{vid}.json"
        if not raw_path.exists():
            print(f"  lewat {vid}: raw tidak ada")
            continue
        raw = load_json(raw_path)
        meta = metadata.get(vid, {})

        gid = src.get("duplicate_group") or vid
        members = by_event.get(gid, [])
        if not members:
            fallback = by_id_variant.get(vid) or {
                "id": vid, "url": src.get("url"), "title": src.get("title"),
                "channel": src.get("channel"), "is_canonical": True,
            }
            members = [fallback]

        uploads = []
        for v in members:
            eid = v.get("id")
            emeta = metadata.get(eid, {})
            ment = by_id_manifest.get(eid, {})
            uploads.append({
                "video_id": eid,
                "url": v.get("url") or f"https://www.youtube.com/watch?v={eid}",
                "title": v.get("title") or emeta.get("title", ""),
                "channel": v.get("channel") or emeta.get("channel", ""),
                "upload_date": _iso_date(emeta.get("upload_date", "")),
                "duration_s": v.get("duration") or emeta.get("duration"),
                "source_tier": v.get("source_tier"),
                "fetch_method": v.get("fetch_method"),
                "token_count": v.get("token_count"),
                "status": ment.get("status"),
                "language": ment.get("language"),
                "is_generated": ment.get("is_generated"),
                "snippet_count": ment.get("snippet_count"),
                "discovery_origins": ment.get("discovery_origins", []),
                "selection_reason": ment.get("selection_reason"),
                "canonical": bool(v.get("is_canonical")) or eid == vid,
            })
        uploads.sort(key=lambda u: (not u["canonical"], u.get("upload_date") or ""))

        slug = f"{src['date']}-{slugify(src['title'])}"
        record = {
            "id": slug,
            "video_id": vid,
            "date": src["date"],
            "title": src["title"],
            "channel": src["channel"],
            "youtube_url": src.get("url") or f"https://www.youtube.com/watch?v={vid}",
            "duration_s": src.get("duration"),
            "duration_hms": _hms(src.get("duration")),
            "source_tier": src.get("source_tier"),
            "fetch_method": src.get("fetch_method"),
            "snippet_count": len(raw.get("raw_snippets", [])),
            "token_count": src.get("token_count"),
            "unique_word_count": src.get("unique_word_count"),
            "duplicate_count": src.get("duplicate_count", max(0, len(uploads) - 1)),
            "uploads": uploads,
            "topics": src.get("topics", {}),
            "policy_signals": src.get("policy_signals", {}),
            "transcript": merge_paragraphs(raw.get("raw_snippets", [])),
            "provenance": {
                "engine_repo": "himanusia/youtube-speech-corpus",
                "engine_commit": _engine_commit(),
                "canonical_video_id": vid,
                "language_code": raw.get("language_code", "id"),
                "language": raw.get("language"),
                "is_generated": raw.get("is_generated"),
                "fetched_via": src.get("fetch_method"),
                "source_of_truth": f"engine/data/prabowo/raw/{vid}.json",
            },
        }
        (OUT / "speeches" / f"{slug}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        speeches.append(record)

    speeches.sort(key=lambda s: s["date"])

    index = [{
        "id": s["id"],
        "date": s["date"],
        "title": s["title"],
        "channel": s["channel"],
        "video_id": s["video_id"],
        "youtube_url": s["youtube_url"],
        "duration_s": s["duration_s"],
        "duration_hms": s["duration_hms"],
        "token_count": s["token_count"],
        "unique_word_count": s["unique_word_count"],
        "source_tier": s["source_tier"],
        "fetch_method": s["fetch_method"],
        "upload_count": len(s["uploads"]),
        "duplicate_count": s["duplicate_count"],
        "para_count": len(s["transcript"]),
        "topics": s["topics"],
    } for s in speeches]

    (OUT / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    (OUT / "coverage.json").write_text(
        json.dumps(build_coverage(speeches), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    (OUT / "meta.json").write_text(json.dumps({
        "built_at": datetime.now(WIB).isoformat(timespec="seconds"),
        "engine_commit": _engine_commit(),
        "engine_repo": "https://github.com/himanusia/youtube-speech-corpus",
        "event_count": len(speeches),
        "upload_count": sum(len(s["uploads"]) for s in speeches),
        "token_count": sum(s["token_count"] or 0 for s in speeches),
        "date_first": speeches[0]["date"] if speeches else None,
        "date_last": speeches[-1]["date"] if speeches else None,
        "generated_captions": sum(
            1 for s in speeches if s["provenance"].get("is_generated")
        ),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"OK  {len(speeches)} pidato")
    print(f"    {sum(len(s['uploads']) for s in speeches)} upload")
    print(f"    {sum(len(s['transcript']) for s in speeches)} paragraf ber-cap-waktu")
    print(f"    {sum(s['token_count'] or 0 for s in speeches):,} token")
    return 0


def _iso_date(yyyymmdd: str) -> str | None:
    if not yyyymmdd or len(str(yyyymmdd)) != 8:
        return None
    s = str(yyyymmdd)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def _hms(seconds) -> str | None:
    if not seconds:
        return None
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _engine_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(ENGINE), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return None


def build_coverage(speeches: list[dict]) -> dict:
    """Peta cakupan — termasuk bulan yang bolong, supaya lubangnya terlihat."""
    from collections import Counter, defaultdict

    per_month: dict[str, dict] = defaultdict(lambda: {"events": 0, "tokens": 0})
    for s in speeches:
        m = s["date"][:7]
        per_month[m]["events"] += 1
        per_month[m]["tokens"] += s["token_count"] or 0

    if speeches:
        start = _month_range(speeches[0]["date"][:7], speeches[-1]["date"][:7])
    else:
        start = []

    months = [{
        "month": m,
        "events": per_month.get(m, {}).get("events", 0),
        "tokens": per_month.get(m, {}).get("tokens", 0),
        "covered": m in per_month,
    } for m in start]

    per_year = Counter(s["date"][:4] for s in speeches)
    year_tokens = defaultdict(int)
    for s in speeches:
        year_tokens[s["date"][:4]] += s["token_count"] or 0

    tier = Counter(s["source_tier"] for s in speeches)
    method = Counter(s["fetch_method"] for s in speeches)

    gaps = [m["month"] for m in months if not m["covered"]]

    return {
        "date_first": speeches[0]["date"] if speeches else None,
        "date_last": speeches[-1]["date"] if speeches else None,
        "span_days": _span_days(speeches),
        "months": months,
        "months_without_events": gaps,
        "per_year": [{
            "year": y,
            "events": per_year[y],
            "tokens": year_tokens[y],
            "event_share": round(per_year[y] / len(speeches) * 100, 1) if speeches else 0,
        } for y in sorted(per_year)],
        "source_tiers": dict(tier),
        "fetch_methods": dict(method),
        # Batas yang harus ditampilkan apa adanya di web.
        "known_limits": [
            "Penemuan lewat pencarian YouTube, yang condong ke hasil terbaru — "
            "periode lama lebih tipis bukan karena Prabowo lebih jarang bicara.",
            "Semua caption auto-generated, bukan transkrip dari audio.",
            "Yang masuk hanya pidato, sambutan, dan pernyataan resmi — "
            "bukan wawancara, konferensi pers pendek, atau potongan klip.",
            "Pidato berbahasa asing (forum internasional) tidak punya track Indonesia "
            "sehingga tidak masuk.",
        ],
    }


def _month_range(a: str, b: str) -> list[str]:
    ya, ma = int(a[:4]), int(a[5:7])
    yb, mb = int(b[:4]), int(b[5:7])
    out = []
    y, m = ya, ma
    while (y, m) <= (yb, mb):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _span_days(speeches: list[dict]) -> int | None:
    if len(speeches) < 2:
        return None
    a = datetime.fromisoformat(speeches[0]["date"])
    b = datetime.fromisoformat(speeches[-1]["date"])
    return (b - a).days


if __name__ == "__main__":
    raise SystemExit(main())
