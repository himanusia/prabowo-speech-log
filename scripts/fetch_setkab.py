#!/usr/bin/env python3
"""fetch_setkab.py — tarik transkrip resmi dari REST API setkab.go.id.

Kategori 87 = "Transkrip Pidato". Situsnya di balik bot-protection (F5/
TSPD), tapi REST API WordPress-nya sendiri terbuka — lihat
references/corpus-sources.md untuk resepnya.

Keluaran: data/setkab-fetch.json — daftar {id, tanggal, judul, link,
panjang, teks}, siap diumpankan ke scripts/import_setkab.py.

Pakai:
    python3 scripts/fetch_setkab.py
"""
from __future__ import annotations

import html as ihtml
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "setkab-fetch.json"
API = "https://setkab.go.id/api/wp/v2/posts"
AFTER = "2024-10-20T00:00:00"
WIB = timezone(timedelta(hours=7))


def bersih_html(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = ihtml.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def ambil(semua: list[dict]) -> list[dict]:
    out = []
    page = 1
    while True:
        url = (f"{API}?categories=87&per_page=100&page={page}"
               f"&after={AFTER}&_fields=id,date,slug,title,link,content")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        if not data:
            break
        for x in data:
            teks = bersih_html((x.get("content") or {}).get("rendered") or "")
            judul = ihtml.unescape(re.sub(r"<[^>]+>", " ", x["title"]["rendered"]))
            out.append({
                "id": x["id"],
                "tanggal": x["date"][:10],
                "judul": re.sub(r"\s+", " ", judul).strip(),
                "link": x["link"],
                "panjang": len(teks),
                "teks": teks,
            })
        if len(data) < 100:
            break
        page += 1
    return out


def main() -> int:
    try:
        items = ambil([])
    except Exception as exc:
        print(f"GAGAL ambil setkab: {type(exc).__name__}: {exc}")
        return 1
    # Stub/pengumuman pendek bukan transkrip — buang. Batas ini sama dengan
    # yang dipakai import_setkab.py dan tercatat di references/corpus-sources.md.
    items = [x for x in items if x["panjang"] > 500]
    items.sort(key=lambda x: (x["tanggal"], x["id"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK  {len(items)} transkrip resmi -> {OUT.relative_to(ROOT)}")
    if items:
        print(f"    rentang: {items[0]['tanggal']} .. {items[-1]['tanggal']}")
        print(f"    terbaru: {items[-1]['judul'][:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
