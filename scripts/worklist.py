#!/usr/bin/env python3
"""
worklist.py — susun daftar kerja: video mana yang perlu diambil transkripnya.

Masukan : data/channel.json (hasil enumerate_channel.py) + data/speeches/*.json
Keluaran: data/worklist.json

Cara kerja:
1. Tentukan batas era presiden memakai tanggal yang tertulis di judul.
   Daftar kanal tersusun dari yang terbaru, jadi tanggalnya menurun —
   posisi dipakai sebagai proksi untuk video yang judulnya tanpa tanggal.
2. Kelompokkan tiap video: pidato, keterangan pers, kunjungan, atau lain.
3. Buang yang sudah ada di arsip.

Hasilnya dipakai collect_panel.py sebagai daftar tugas.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WIB = timezone(timedelta(hours=7))

CUT = (2024, 10, 20)  # pelantikan Prabowo

BULAN = {b: i + 1 for i, b in enumerate(
    ["januari", "februari", "maret", "april", "mei", "juni", "juli",
     "agustus", "september", "oktober", "november", "desember"])}
BULAN_EN = {b: i + 1 for i, b in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}


def title_date(t: str):
    """Ambil tanggal dari judul.

    Kembalikan (y, m, d, presisi):
      presisi True  -> tanggal lengkap, aman untuk membandingkan urutan
      presisi False -> hanya tahun, JANGAN dipakai menentukan batas era
    """
    m = re.search(r"(\d{1,2})\s+(" + "|".join(list(BULAN) + list(BULAN_EN)) + r")\s+(\d{4})", t, re.I)
    if m:
        bln = m.group(2).lower()
        return (int(m.group(3)), BULAN.get(bln) or BULAN_EN.get(bln) or 0, int(m.group(1)), True)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Judul Indonesia hampir selalu hari/bulan/tahun. Kalau salah satu
        # angka > 12, itu jelas bagian harinya. Kalau dua-duanya <= 12,
        # pakai hari/bulan (bukan bulan/hari) karena itu konvensi di sini.
        if a > 12:
            d, mo = a, b
        elif b > 12:
            mo, d = a, b
        else:
            d, mo = a, b
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return None
        return (y, mo, d, True)
    m = re.search(r"\b(20\d\d)\b", t)
    if m:
        return (int(m.group(1)), 0, 0, False)
    return None


# --- klasifikasi judul -------------------------------------------------------

OTHER_SPEAKER = re.compile(
    r"(?:press statement|keterangan pers|statement)\s+by\s+(?:the\s+)?"
    r"(?:coordinating |acting |deputy |vice )?"
    r"(?:minister|head|governor|director|secretary|chairman|chief|spokesperson|"
    r"u\.s\.|attorney|ambassador|committee|financial|state secretary|"
    r"deputy|general|panglima)", re.I)

SPEECH = re.compile(
    r"\b(pidato|sambutan|arahan|amanat|pengarahan|orasi|kuliah\s+umum|keynote|"
    r"pidato\s+kenegaraan|speech|remarks|address)\b", re.I)
PRESS = re.compile(r"keterangan\s+pers|press\s+statement|doorstop", re.I)
VISIT = re.compile(
    r"\b(tiba|disambut|menyambut|jemput|menjemput|berangkat|bertolak|kembali|"
    r"kunjungi|mengunjungi|kunjungan|tinjau|meninjau|blusukan|panen|menanam|"
    r"serah\s+terima|penyerahan|meresmikan|resmikan|groundbreaking|"
    r"peluncuran|launching|arrives?|welcomed|departs?|visits?|inspects?)\b", re.I)
PRABOWO = re.compile(r"prabowo|presiden\s+ri\b|president\s+prabowo|presiden\s+republik", re.I)


def classify(title: str) -> str:
    if OTHER_SPEAKER.search(title):
        return "bukan_prabowo"
    has_speech = bool(SPEECH.search(title))
    has_press = bool(PRESS.search(title))
    is_prabowo = bool(PRABOWO.search(title)) or bool(
        re.search(r"\b(pidato|sambutan|arahan|amanat|pengarahan)\s+(presiden|kenegaraan)\b", title, re.I))
    if has_speech and (is_prabowo or re.search(r"kenegaraan", title, re.I)):
        return "pidato"
    if has_press and is_prabowo:
        return "keterangan_pers"
    if VISIT.search(title):
        return "kunjungan"
    return "ambigu"


def main() -> int:
    ch = json.loads((DATA / "channel.json").read_text(encoding="utf-8"))
    videos = ch["videos"]

    # --- batas era ---
    # Daftar kanal tersusun dari yang terbaru, tapi tidak dijamin persis
    # kronologis. Jadi jangan berhenti di pelanggaran pertama: cari posisi
    # TERJAUH yang tanggalnya masih di dalam era, lalu potong sedikit di
    # belakangnya. Hanya tanggal lengkap yang dipakai — judul yang cuma
    # memuat tahun tidak cukup untuk memutuskan urutan.
    last_era = -1
    dated = 0
    for v in videos:
        d = title_date(v["title"])
        if not d or not d[3]:
            continue
        dated += 1
        if d[:3] >= CUT:
            last_era = max(last_era, v["position"])
    boundary = last_era + 1 if last_era >= 0 else len(videos)
    print(f"video kanal          : {len(videos):,}")
    print(f"judul bertanggal     : {dated:,}")
    print(f"posisi era terjauh   : {last_era:,}")
    print(f"batas era presiden   : {boundary:,} video pertama")

    era = videos[:boundary]
    print(f"video era presiden   : {len(era):,}")

    have = {json.loads(p.read_text(encoding="utf-8"))["video_id"]
            for p in (DATA / "speeches").glob("*.json")}
    known = set(have)
    for p in (DATA / "speeches").glob("*.json"):
        for u in json.loads(p.read_text(encoding="utf-8")).get("uploads", []):
            known.add(u["video_id"])
    print(f"sudah di arsip       : {len(known)} id")

    items = []
    for v in era:
        kind = classify(v["title"])
        d = title_date(v["title"])
        items.append({
            "video_id": v["id"],
            "title": v["title"],
            "position": v["position"],
            "date": ("-".join(f"{x:02d}" for x in d[:3]) + ("" if d[3] else "?")) if d else None,
            "date_precise": bool(d and d[3]),
            "kind": kind,
            "status": "have" if v["id"] in known else "pending",
        })

    c = Counter(i["kind"] for i in items)
    cp = Counter(i["kind"] for i in items if i["status"] == "pending")

    print("\n=== klasifikasi (era presiden) ===")
    for k, n in c.most_common():
        print(f"   {k:16} {n:>4}   (belum diambil: {cp.get(k,0)})")

    todo = [i for i in items if i["status"] == "pending" and i["kind"] != "bukan_prabowo"]
    print(f"\nmasuk daftar kerja   : {len(todo):,}")
    print(f"  pidato             : {cp.get('pidato',0)}")
    print(f"  keterangan pers    : {cp.get('keterangan_pers',0)}")
    print(f"  ambigu             : {cp.get('ambigu',0)}")
    print(f"  kunjungan          : {cp.get('kunjungan',0)}")

    (DATA / "worklist.json").write_text(json.dumps({
        "generated_at": datetime.now(WIB).isoformat(timespec="seconds"),
        "channel_url": ch["channel_url"],
        "era_boundary_position": boundary,
        "channel_total": len(videos),
        "era_total": len(era),
        "already_in_archive": len(known),
        "counts": dict(c),
        "pending_counts": dict(cp),
        "items": items,
        "todo": todo,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nOK  data/worklist.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
