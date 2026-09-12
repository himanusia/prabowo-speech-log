#!/usr/bin/env python3
"""
enumerate_channel.py — daftar SELURUH video kanal resmi, sekali jalan.

Metadata saja (--flat-playlist): tidak mengunduh, tidak memutar apa pun.
Hasilnya jadi data/channel.json, dan tidak perlu diulang kecuali mau menyegarkan.

Dipakai oleh worklist.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "channel.json"
WIB = timezone(timedelta(hours=7))

CHANNEL_URL = "https://www.youtube.com/@SekretariatPresiden/videos"

# yt-dlp ada di venv repo korpus (engine tidak membundelnya).
YTDLP_CANDIDATES = [
    ROOT.parent / "prabowo-speech-wordcount" / ".venv" / "bin" / "yt-dlp",
    Path("/opt/homebrew/bin/yt-dlp"),
    Path("/usr/local/bin/yt-dlp"),
]


def find_ytdlp() -> str:
    for c in YTDLP_CANDIDATES:
        if c.exists():
            return str(c)
    raise SystemExit("yt-dlp tidak ditemukan — pasang dulu atau sesuaikan YTDLP_CANDIDATES")


def main() -> int:
    ytdlp = find_ytdlp()
    print(f"yt-dlp: {ytdlp}")
    print(f"kanal : {CHANNEL_URL}")
    print("mengambil daftar (metadata saja, tanpa unduh)…")

    cmd = [
        ytdlp, "--flat-playlist", "--skip-download", "--no-warnings",
        "--sleep-requests", "1",
        "--print", "%(id)s\t%(title)s",
        CHANNEL_URL,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-800:], file=sys.stderr)

    rows = []
    for line in proc.stdout.splitlines():
        if "\t" not in line:
            continue
        vid, title = line.split("\t", 1)
        vid, title = vid.strip(), title.strip()
        if vid:
            rows.append({"id": vid, "title": title, "position": len(rows)})

    if not rows:
        print("tidak ada hasil — kemungkinan kena rate limit, coba lagi nanti")
        return 1

    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "channel_url": CHANNEL_URL,
        "collected_at": datetime.now(WIB).isoformat(timespec="seconds"),
        "count": len(rows),
        "note": "Urutan sesuai kanal: paling baru dulu. Tanggal unggah tidak "
                "tersedia di mode flat-playlist, jadi posisi dipakai sebagai proksi.",
        "videos": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"OK  {len(rows):,} video → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
