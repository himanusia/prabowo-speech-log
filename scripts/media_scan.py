#!/usr/bin/env python3
"""media_scan.py — cari pidato di kanal media yang BELUM ada di arsip.

Masalah yang dipecahkan:
    Daftar kerja awal disusun HANYA dari satu kanal, @SekretariatPresiden.
    Akibatnya pidato yang cuma diunggah kanal media (KOMPASTV, Metro TV,
    tvOne, CNN, dll) tidak pernah masuk radar sama sekali. Arsip jadi tidak
    lengkap, dan hitungan frekuensi kata di situs tidak mewakili seluruh
    pidato.

Cara kerja:
    1. Baca hasil pencarian YouTube (id|kanal|judul) dari berkas.
    2. Buang yang videonya sudah ada di arsip atau sudah pernah dicoba.
    3. Kelompokkan sisa video menjadi ACARA (bukan video), karena satu acara
       biasanya diunggah banyak kanal.
    4. Tulis daftar acara baru ke data/media-worklist.json.

Pakai:
    python3 scripts/media_scan.py /tmp/media-uniq.txt
    python3 scripts/media_scan.py /tmp/media-uniq.txt --tulis
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

# Kanal yang jelas bukan sumber pidato (potongan berita, reaksi, kompilasi).
BUKAN_SUMBER = re.compile(
    r"\b(reaksi|reaction|komentar pengamat|bedah|analisis|podcast|pod|"
    r"kompilasi|kumpulan|momen|kilas|kaleidoskop|vlog|prank|edit|shorts)\b",
    re.I,
)
# Judul yang menandakan ini pidato/sambutan, bukan sekadar kunjungan.
IS_PIDATO = re.compile(
    r"\b(pidato|speech|sambutan|pernyataan|kenegaraan|keynote|remarks|"
    r"address|arahan|pengantar|orasi)\b",
    re.I,
)


def norm(teks: str) -> str:
    t = unicodedata.normalize("NFKD", (teks or "").lower())
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\b(full|breaking|news|live|delay|highlight|terbaru|hd|4k|part|official)\b", " ", t)
    return " ".join(t.split())


def kunci_acara(judul: str) -> str:
    """Ambil inti judul sebagai kunci pengelompokan acara."""
    t = norm(judul)
    # buang frasa pembuka yang selalu ada
    for buang in ("pidato lengkap presiden prabowo", "pidato presiden prabowo",
                  "pidato prabowo", "presiden prabowo", "prabowo subianto",
                  "full pidato", "pidato kenegaraan"):
        t = t.replace(buang, " ")
    t = " ".join(t.split())
    return t[:70]


def mirip(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    sumber = Path(sys.argv[1])
    tulis = "--tulis" in sys.argv

    # --- yang sudah kita punya ---
    ada: set[str] = set()
    judul_arsip: list[str] = []
    for f in sorted((DATA / "speeches").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        ada.add(d["video_id"])
        for u in d.get("uploads", []):
            ada.add(u["video_id"])
        judul_arsip.append(d.get("title") or "")

    pernah: set[str] = set()
    prog = DATA / "panel-progress.jsonl"
    if prog.exists():
        for line in prog.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    pernah.add(json.loads(line)["id"])
                except Exception:
                    pass
    sudah = ada | pernah

    # --- hasil pencarian ---
    baris: list[dict] = []
    for line in sumber.read_text(encoding="utf-8").splitlines():
        p = line.split("|")
        if len(p) >= 3 and len(p[0]) == 11:
            baris.append({"id": p[0], "channel": p[1], "title": "|".join(p[2:])})
    unik = {b["id"]: b for b in baris}
    semua = list(unik.values())
    baru = [b for b in semua if b["id"] not in sudah]

    # --- kelompokkan jadi acara ---
    kandidat = [b for b in baru if IS_PIDATO.search(b["title"]) and not BUKAN_SUMBER.search(b["title"])]
    acara: list[dict] = []
    for b in kandidat:
        k = kunci_acara(b["title"])
        tempat = None
        for a in acara:
            if mirip(k, a["kunci"]) > 0.72:
                tempat = a
                break
        if tempat is None:
            # cek juga terhadap judul yang sudah ada di arsip
            sudah_ada = any(mirip(k, norm(j)) > 0.80 for j in judul_arsip if j)
            acara.append({"kunci": k, "judul": b["title"], "video": [],
                          "kanal": [], "mungkin_sudah_ada": sudah_ada})
            tempat = acara[-1]
        tempat["video"].append(b["id"])
        if b["channel"] not in tempat["kanal"]:
            tempat["kanal"].append(b["channel"])

    baru_acara = [a for a in acara if not a["mungkin_sudah_ada"]]
    ragu = [a for a in acara if a["mungkin_sudah_ada"]]

    print("=== HASIL PEMINDAIAN KANAL MEDIA ===")
    print(f"  video dari pencarian      : {len(semua):,}")
    print(f"  sudah ada / pernah dicoba : {len(semua)-len(baru):,}")
    print(f"  belum pernah disentuh     : {len(baru):,}")
    print(f"    judulnya pidato         : {len(kandidat):,}")
    print()
    print(f"  ACARA BARU (perkiraan)    : {len(baru_acara):,}")
    print(f"  perlu diperiksa manual    : {len(ragu):,}")
    print()
    print("=== 40 ACARA BARU PERTAMA ===")
    for a in baru_acara[:40]:
        print(f"  [{a['video'][0]}] {len(a['video'])} unggahan | {a['judul'][:62]}")
    if ragu:
        print("\n=== PERLU DIPERIKSA (judulnya mirip yang sudah ada) ===")
        for a in ragu[:15]:
            print(f"  [{a['video'][0]}] {a['judul'][:66]}")

    if tulis:
        out = DATA / "media-worklist.json"
        out.write_text(json.dumps({
            "sumber": str(sumber),
            "jumlah_video_dipindai": len(semua),
            "belum_pernah_disentuh": len(baru),
            "acara_baru": baru_acara,
            "perlu_diperiksa": ragu,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n  ditulis: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
