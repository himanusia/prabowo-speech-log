#!/usr/bin/env python3
"""dedupe_events.py — gabungkan entri yang sebenarnya acara yang sama.

Masalah:
    Satu acara diunggah banyak kanal. Beberapa sudah tergabung (satu entri
    dengan banyak `uploads`), tapi yang masuk lewat import_panels.py dibuat
    sebagai entri TERPISAH. Akibatnya "Pidato Kenegaraan 14 Agu 2026" muncul
    dua kali dan jumlah pidato di situs jadi menggelembung.

Cara mendeteksi:
    Membandingkan ISI INTI transkrip, bukan judul dan bukan awalan. Semua
    pidato Prabowo dibuka dengan litani sapaan yang sama (assalamualaikum,
    shalom, swastiastu, namo buddhaya) sehingga 350 karakter pertama nyaris
    identik di semua pidato. Membandingkan awalan membuat acara berbeda
    terlihat sama; membandingkan judul tidak menolong karena kanal media
    memakai judul clickbait.

    Karena itu: buang 350 karakter pertama, lalu bandingkan sisa isinya
    HANYA di antara entri yang tanggalnya sama.

Pakai:
    python3 scripts/dedupe_events.py            # lihat saja
    python3 scripts/dedupe_events.py --gabung   # tulis perubahannya
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPEECHES = DATA / "speeches"


def terbit(d: dict) -> bool:
    k = d.get("speaker_kind")
    return True if k is None else k in ("pidato_prabowo", "prabowo_bicara")


def isi(s: dict, mulai: int = 350, panjang: int = 3000) -> str:
    t = " ".join(p.get("text", "") for p in s.get("transcript", []))
    t = unicodedata.normalize("NFKD", t.lower())
    t = " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())
    return t[mulai:mulai + panjang]


def main() -> int:
    gabung = "--gabung" in sys.argv
    semua = [json.loads(f.read_text(encoding="utf-8"))
             for f in sorted(SPEECHES.glob("*.json"))]
    pub = [s for s in semua if terbit(s)]

    per_tanggal: dict[str, list[dict]] = defaultdict(list)
    for s in pub:
        per_tanggal[(s.get("date") or "")[:10]].append(s)

    kelompok: list[list[dict]] = []
    for tgl, items in per_tanggal.items():
        if len(items) < 2 or not tgl:
            continue
        dipakai: set[int] = set()
        for i, a in enumerate(items):
            if i in dipakai:
                continue
            ca = isi(a)
            if len(ca) < 100:
                continue
            grup = [a]
            for j in range(i + 1, len(items)):
                if j in dipakai:
                    continue
                cb = isi(items[j])
                if len(cb) < 100:
                    continue
                if SequenceMatcher(None, ca, cb).ratio() > 0.70:
                    grup.append(items[j])
                    dipakai.add(j)
            if len(grup) > 1:
                dipakai.add(i)
                kelompok.append(grup)

    lebih = sum(len(g) - 1 for g in kelompok)
    print(f"entri terbit       : {len(pub)}")
    print(f"kelompok duplikat  : {len(kelompok)}")
    print(f"entri berlebih     : {lebih}")
    print(f"acara unik         : {len(pub) - lebih}\n")

    for g in sorted(kelompok, key=lambda x: -(x[0].get("token_count") or 0)):
        urut = sorted(g, key=lambda x: -(x.get("token_count") or 0))
        print(f"  {(g[0].get('date') or '?')[:10]}  {len(g)} -> 1   kanonik: {urut[0]['video_id']}")
        for s in urut:
            tanda = "KANONIK" if s is urut[0] else "  gabung"
            print(f"     {tanda}  {s['video_id']}  {s.get('token_count', 0):>6,} tok  {(s.get('title') or '')[:50]}")

    if not gabung:
        print("\n(lihat saja — jalankan dengan --gabung untuk menerapkan)")
        return 0

    dihapus = 0
    for g in kelompok:
        urut = sorted(g, key=lambda x: -(x.get("token_count") or 0))
        utama, lain = urut[0], urut[1:]
        uploads = list(utama.get("uploads") or [])
        ada = {u.get("video_id") for u in uploads}
        for s in lain:
            # Entri tanpa video (mis. transkrip resmi Setkab) tidak bisa jadi
            # baris unggahan — cukup tercatat lewat catatan penggabungan.
            if not s.get("video_id"):
                continue
            if s["video_id"] not in ada:
                uploads.append({
                    "video_id": s["video_id"],
                    "url": s.get("youtube_url") or f"https://www.youtube.com/watch?v={s['video_id']}",
                    "title": s.get("title") or "",
                    "channel": s.get("channel") or "",
                    "canonical": False,
                })
            # entri yang digabung tidak lagi diterbitkan sendiri
            p = SPEECHES / f"{s['id']}.json"
            if p.exists():
                p.unlink()
                dihapus += 1
        utama["uploads"] = uploads
        utama["duplicate_count"] = len(uploads) - 1
        utama["canonical_note"] = (utama.get("canonical_note") or "") + \
            f" Digabung dari {len(lain) + 1} unggahan acara yang sama."
        (SPEECHES / f"{utama['id']}.json").write_text(
            json.dumps(utama, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n  digabung : {dihapus} entri berlebih dihapus")
    print(f"  sisa     : {len(pub) - dihapus} entri")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
