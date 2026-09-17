#!/usr/bin/env python3
"""insight.py — hitung temuan analitik untuk halaman utama.

Bedanya dengan aggregate.py:
    aggregate.py menghitung frekuensi kata mentah. Frekuensi mentah tidak
    memberi pemahaman: "kata X muncul 300 kali" tidak berarti apa-apa tanpa
    penyebut dan tanpa pembanding.

    Skrip ini menghitung UKURAN YANG BISA DITAFSIRKAN:
      - berapa PIDATO yang membahas sesuatu, bukan berapa kali katanya muncul
      - perbandingan antar periode, bukan satu angka tunggal
      - varian istilah digabung (MBG = MBG + makan bergizi + sppg + ...)
      - penyebut selalu ditampilkan (n dari N)

Aturan yang dipegang:
    1. Selalu tampilkan n/N. "30%" tanpa "63/211" tidak jujur.
    2. Istilah dicari dalam SEMUA variannya. Nol dengan satu ejaan bukan nol.
    3. Anotasi panggung dibuang ([Tepuk tangan], [bersorak], [Musik]).
    4. Entri pra-era (sebelum 20 Okt 2024) tidak dihitung.

Pakai:
    python3 scripts/insight.py            # hitung + tulis data/insight.json
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

ANOT = re.compile(r"\[[^\]]{0,60}\]")          # anotasi panggung di transkrip
KATA = re.compile(r"[a-zA-Z][a-zA-Z'-]+")


def terbit(d: dict) -> bool:
    k = d.get("speaker_kind")
    return True if k is None else k in ("pidato_prabowo", "prabowo_bicara")


def teks(s: dict) -> str:
    """Transkrip resmi kalau ada (lebih akurat), kalau tidak caption YouTube."""
    tr = s.get("transkrip_resmi") or {}
    t = tr["teks"] if tr.get("teks") else " ".join(p.get("text", "") for p in s.get("transcript", []))
    return ANOT.sub(" ", t)


def tok(t: str) -> int:
    return len(KATA.findall(t))


def muat() -> list[tuple[dict, str]]:
    out = []
    for f in sorted((DATA / "speeches").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if not terbit(d) or d.get("pra_era") or d.get("tanpa_transkrip"):
            continue
        if d.get("transcript_language") == "en":
            continue
        if not d.get("date"):
            continue
        out.append((d, teks(d)))
    out.sort(key=lambda x: x[0]["date"])
    return out


def kuartal(tgl: str) -> str:
    y, m = int(tgl[:4]), int(tgl[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}"


def semester(tgl: str) -> str:
    y, m = int(tgl[:4]), int(tgl[5:7])
    return f"{y}-S{(m - 1) // 6 + 1}"


def main() -> int:
    S = muat()
    N = len(S)
    TOT = sum(tok(t) for _, t in S)
    print(f"korpus: {N} pidato · {TOT:,} token")

    def hitung(pat: str) -> dict:
        """Kemunculan, jumlah pidato, dan tingkat per 1.000 kata."""
        n = docs = 0
        for _, t in S:
            c = len(re.findall(pat, t, re.I))
            if c:
                n += c
                docs += 1
        return {"kemunculan": n, "pidato": docs,
                "persen_pidato": round(docs * 100 / N, 1) if N else 0,
                "per_1000": round(n * 1000 / TOT, 2) if TOT else 0}

    # ---------- istilah, dengan SEMUA variannya ----------
    ISTILAH = {
        "korupsi": r"korupsi|koruptor|kebocoran|penyelewengan|menyeleweng|maling|merampok|mencuri|memeras",
        "mbg": r"\bmbg\b|makan bergizi|bergizi gratis|program gizi|\bsppg\b|dapur gizi",
        "bencana": r"\bbencana\b|banjir|gempa|longsor|erupsi|tsunami|kekeringan|pengungsi|korban jiwa",
        "danantara": r"danantara|dana abadi|sovereign wealth",
        "swasembada": r"swasembada|swasembah|surplus pangan|ekspor beras",
        "hilirisasi": r"hilirisasi|smelter|\bnikel\b|pengolahan dalam negeri",
        "sawit": r"kelapa sawit|\bsawit\b|\bb50\b|\bb40\b|biodiesel",
        "karhutla": r"karhutla|kebakaran hutan|kebakaran lahan|kabut asap|titik api",
    }
    istilah = {k: hitung(p) for k, p in ISTILAH.items()}

    # ---------- per kuartal: berapa PIDATO yang membahas ----------
    kuar = defaultdict(lambda: {"n": 0})
    for d, t in S:
        k = kuartal(d["date"])
        kuar[k]["n"] += 1
        for nama, pat in ISTILAH.items():
            if re.search(pat, t, re.I):
                kuar[k][nama] = kuar[k].get(nama, 0) + 1
    seri_kuartal = [
        {"kuartal": k, "n": v["n"],
         **{nama: {"pidato": v.get(nama, 0),
                   "persen": round(v.get(nama, 0) * 100 / v["n"], 1)}
            for nama in ISTILAH}}
        for k, v in sorted(kuar.items()) if v["n"] >= 20
    ]

    # ---------- kata ganti ----------
    GANTI = {"saya": r"\bsaya\b", "kita": r"\bkita\b", "kami": r"\bkami\b",
             "rakyat": r"\brakyat\b", "pemerintah": r"\bpemerintah\b",
             "bangsa": r"\bbangsa\b", "negara": r"\bnegara\b"}
    ganti = {k: hitung(p) for k, p in GANTI.items()}
    sem = defaultdict(lambda: Counter())
    semn = defaultdict(int)
    for d, t in S:
        k = semester(d["date"])
        semn[k] += tok(t)
        sem[k].update(re.findall(r"[a-z]+", t.lower()))
    seri_ganti = [
        {"periode": k, "n": sum(1 for d, _ in S if semester(d["date"]) == k),
         **{w: round(sem[k][w] * 1000 / semn[k], 2) for w in GANTI}}
        for k in sorted(semn) if semn[k] > 12000
    ]

    # ---------- bahasa: proporsi pidato berbahasa Inggris ----------
    semua_era = []
    for f in sorted((DATA / "speeches").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if terbit(d) and not d.get("pra_era") and not d.get("tanpa_transkrip") and d.get("date"):
            semua_era.append((d, teks(d)))
    bahasa = defaultdict(lambda: {"n": 0, "inggris": 0})
    for d, t in semua_era:
        k = kuartal(d["date"])
        bahasa[k]["n"] += 1
        en = len(re.findall(r"\b(the|and|we|our|with|for|have|are|this|that|will)\b", t.lower()))
        idn = len(re.findall(r"\b(yang|dan|kita|saya|untuk|dengan|tidak|ini|itu|akan)\b", t.lower()))
        if en > idn:
            bahasa[k]["inggris"] += 1
    seri_bahasa = [{"kuartal": k, "n": v["n"], "inggris": v["inggris"],
                    "persen": round(v["inggris"] * 100 / v["n"], 1)}
                   for k, v in sorted(bahasa.items()) if v["n"] >= 20]

    # ---------- panjang per jenis acara ----------
    JENIS = [
        ("kenegaraan", r"kenegaraan|sidang tahunan|paripurna|nota keuangan|apbn|rapbn"),
        ("sidang kabinet", r"sidang kabinet|ratas|rapat terbatas|retret|rakornas|raker|taklimat"),
        ("partai / ormas", r"gerindra|golkar|demokrat|pkb|nahdlatul|muhammadiyah|nasdem|harlah|munas|muktamar|kongres"),
        ("hari besar", r"hari guru|hari buruh|pancasila|kemerdekaan|hari koperasi|natal|idulfitri|imlek"),
        ("peresmian", r"resmikan|peresmian|groundbreaking|meresmikan"),
        ("luar negeri", r"\bktt\b|apec|g20|brics|asean|\bpbb\b|unga|bilateral|world government|davos|\bd-8\b"),
    ]

    def jenis(d: dict) -> str:
        j = (d.get("title") or "").lower() + " " + " ".join(
            u.get("title", "").lower() for u in d.get("uploads", []))
        for nama, pat in JENIS:
            if re.search(pat, j):
                return nama
        return "lain-lain"

    gj = defaultdict(list)
    for d, _ in S:
        gj[jenis(d)].append(d.get("token_count") or 0)
    panjang = []
    for k, v in sorted(gj.items(), key=lambda x: -sum(x[1]) / max(len(x[1]), 1)):
        if len(v) < 5:
            continue
        v2 = sorted(v)
        panjang.append({"jenis": k, "n": len(v), "median": v2[len(v2) // 2],
                        "maks": max(v), "rata2": round(sum(v) / len(v))})

    hasil = {
        "korpus": {"pidato": N, "token": TOT,
                   "catatan": "Hanya pidato era presiden yang bertranskrip Indonesia."},
        "istilah": istilah,
        "seri_kuartal": seri_kuartal,
        "ganti": ganti,
        "seri_ganti": seri_ganti,
        "seri_bahasa": seri_bahasa,
        "panjang": panjang,
    }
    out = DATA / "insight.json"
    out.write_text(json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nOK  {out.relative_to(ROOT)}")
    print(f"\n  {'istilah':14} {'kemunculan':>11} {'pidato':>10} {'persen':>8}")
    for k, v in sorted(istilah.items(), key=lambda x: -x[1]["pidato"]):
        print(f"  {k:14} {v['kemunculan']:>11,} {v['pidato']:>6}/{N} {v['persen_pidato']:>7}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
