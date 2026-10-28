#!/usr/bin/env python3
"""perbaiki_tanggal.py — isi tanggal entri arsip yang masih kosong.

Kenapa ada skrip ini
--------------------
`import_panels.py` sengaja TIDAK mengarang tanggal: kalau judul video tidak
memuat tanggal dan daftar kerja tidak punya tanggal presisi, entri disimpan
dengan `date: null` (lihat komentar di importer). Akibatnya id-nya jadi
"None-..." dan seluruh build mati karena satu entri tanpa tanggal.

Skrip ini mengambil SATU fakta yang benar-benar ada di sumber: tanggal unggah
video (`uploadDate` di halaman YouTube), lalu mengonversinya ke WIB. Tanggal
itu bukan tanggal acara, jadi `date_precise` tetap False dan asalnya dicatat
di `provenance`. Tidak ada tanggal yang dikarang.

Pakai:
    python3 scripts/perbaiki_tanggal.py            # tulis perubahan
    python3 scripts/perbaiki_tanggal.py --dry-run  # lihat saja
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEECHES = ROOT / "data" / "speeches"
sys.path.insert(0, str(ROOT / "scripts"))

from import_panels import slug_unik  # noqa: E402

WIB = timezone(timedelta(hours=7))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def upload_date(video_id: str) -> str | None:
    """Tanggal unggah (zona WIB) dari halaman watch, fallback yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        html = subprocess.run(
            ["curl", "-sS", "--max-time", "30", "-A", UA, url],
            capture_output=True, text=True, check=True).stdout
        m = re.search(r'"uploadDate":"([^"]+)"', html)
        if m:
            return _to_wib(m.group(1))
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["yt-dlp", "--skip-download", "--print", "%(upload_date)s", url],
            capture_output=True, text=True, check=True).stdout.strip()
        if re.fullmatch(r"\d{8}", out):
            return f"{out[:4]}-{out[4:6]}-{out[6:]}"
    except Exception:
        pass
    return None


def _to_wib(iso: str) -> str | None:
    """2026-10-26T05:22:17-07:00 -> 2026-10-26 (tanggal WIB)."""
    try:
        return datetime.fromisoformat(iso).astimezone(WIB).date().isoformat()
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    berkas = sorted(SPEECHES.glob("*.json"))
    dipakai = {p.stem for p in berkas}
    kosong = []
    for p in berkas:
        d = json.loads(p.read_text(encoding="utf-8"))
        if not d.get("date"):
            kosong.append((p, d))

    print(f"entri tanpa tanggal : {len(kosong)}")
    if not kosong:
        return 0

    gagal = 0
    for p, d in kosong:
        vid = d.get("video_id") or (d.get("uploads") or [{}])[0].get("video_id")
        if not vid:
            print(f"  LEWAT  {p.name}: tidak ada video_id")
            gagal += 1
            continue
        tanggal = upload_date(vid)
        if not tanggal:
            print(f"  GAGAL  {p.name}: tanggal unggah {vid} tidak terbaca")
            gagal += 1
            continue

        dipakai.discard(d["id"])
        baru = slug_unik(d.get("title", ""), tanggal, dipakai)
        print(f"  {'AKAN ' if a.dry_run else ''}OK     {d['id']}  ->  {baru}  (unggah {tanggal})")
        if a.dry_run:
            continue

        d["id"] = baru
        d["date"] = tanggal
        d["date_precise"] = False
        prov = d.setdefault("provenance", {})
        prov["date_source"] = "tanggal unggah YouTube (dikonversi ke WIB), bukan tanggal acara"
        prov["date_from_upload"] = True
        for u in d.get("uploads", []):
            if not u.get("published"):
                u["published"] = tanggal

        (SPEECHES / f"{baru}.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        p.unlink()

    if gagal:
        print(f"masih {gagal} entri tanpa tanggal — build tetap akan gagal kalau tidak dibereskan")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
