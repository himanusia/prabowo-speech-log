#!/usr/bin/env python3
"""build_momen.py — gabungkan hasil riset momen jadi data/momen.json.

Masukan : data/riset-momen-*.json (riset bersumber; tiap butir punya
          `sumber` berisi URL yang benar-benar dibuka penelitinya)
Keluaran: data/momen.json

Aturan:
- Tiap momen WAJIB punya minimal satu URL sumber dan kutipan. Yang tidak,
  dibuang — momen tanpa sumber tidak layak tayang.
- `pidato_id` divalidasi ke entri yang benar-benar terbit (punya halaman);
  kalau kosong, dicocokkan lewat tanggal
  hanya bila tanggal itu punya TEPAT SATU entri. Ragu = biarkan kosong
  (momen tetap tampil di beranda dengan sumber beritanya).
- Urut terbaru di atas.

Pakai:
    python3 scripts/build_momen.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPEECHES = DATA / "speeches"
OUT = DATA / "momen.json"


# Kata yang tidak membedakan acara satu dengan lainnya.
_STOP = {
    "pada", "di", "ke", "dan", "yang", "dengan", "untuk", "dari", "dalam",
    "acara", "pidato", "sambutan", "presiden", "prabowo", "subianto", "ri",
    "republik", "indonesia", "nasional", "the", "of", "in", "at", "a", "an",
    "dan/atau", "secara", "resmi",
}


def _kata(x: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (x or "").lower())
            if len(w) > 2 and w not in _STOP}


def _terbit(path: Path) -> bool:
    """True kalau entri ini benar-benar diterbitkan build_site (punya halaman)."""
    if not path.exists():
        return False
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if d.get("pra_era"):
        return False
    k = d.get("speaker_kind")
    return k is None or k in ("pidato_prabowo", "prabowo_bicara")


def main() -> int:
    per_tanggal: dict[str, list[tuple[str, str]]] = {}
    yt_by_id: dict[str, str] = {}
    for p in SPEECHES.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        k = d.get("speaker_kind")
        if not (k is None or k in ("pidato_prabowo", "prabowo_bicara")):
            continue
        if d.get("pra_era"):
            continue
        tgl = (d.get("date") or "")[:10]
        if tgl:
            per_tanggal.setdefault(tgl, []).append((d["id"], d.get("title") or ""))
        if d.get("youtube_url"):
            yt_by_id[d["id"]] = d["youtube_url"]

    items, seen = [], set()
    for f in sorted(DATA.glob("riset-momen-*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  lewat {f.name}: {exc}")
            continue
        ms = raw.get("momen") if isinstance(raw, dict) else raw
        for m in (ms or []):
            if not isinstance(m, dict):
                continue
            sumber = [u for u in (m.get("sumber") or [])
                      if isinstance(u, str) and u.startswith("http")]
            if not sumber or not (m.get("kutipan") or "").strip():
                print(f"  buang (tanpa sumber/kutipan): {(m.get('acara') or '')[:60]}")
                continue
            tgl = (m.get("tanggal") or "")[:10]
            pid = m.get("pidato_id")
            if pid and not _terbit(SPEECHES / f"{pid}.json"):
                pid = None
            if not pid and tgl:
                kandidat = per_tanggal.get(tgl) or []
                if len(kandidat) == 1:
                    # Tanggal sama belum cukup: satu tanggal bisa memuat dua
                    # acara berbeda (mis. 18 Sep 2026 punya HUT PAN dan
                    # penerimaan Wapres Malaysia). Butuh irisan kata >= 2
                    # antara nama acara dan judul entri; ragu = kosong.
                    kid, kjudul = kandidat[0]
                    if len(_kata(m.get("acara")) & _kata(kjudul)) >= 2:
                        pid = kid
            key = (tgl, (m.get("kutipan") or "").strip()[:80])
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "tanggal": tgl,
                "acara": (m.get("acara") or "").strip(),
                "pidato_id": pid,
                "kutipan": m["kutipan"].strip(),
                "konteks": (m.get("konteks") or "").strip(),
                "ramai": (m.get("ramai") or "").strip(),
                "sumber": sumber,
                "video_url": (m.get("video_url") or (yt_by_id.get(pid) if pid else None)),
            })

    items.sort(key=lambda x: x["tanggal"], reverse=True)
    OUT.write_text(json.dumps({"momen": items}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    taut = sum(1 for x in items if x["pidato_id"])
    print(f"OK  {len(items)} momen -> {OUT.relative_to(ROOT)}")
    print(f"    tertaut ke entri arsip: {taut} | tanpa tautan: {len(items) - taut}")
    for x in items[:6]:
        print(f"    {x['tanggal']}  {(x['acara'] or '')[:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
