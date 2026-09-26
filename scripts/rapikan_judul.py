#!/usr/bin/env python3
"""rapikan_judul.py — judul tampilan yang manusiawi untuk entri arsip.

Masalah:
    Banyak entri masuk dari kanal berita, dan judul unggahannya judul berita:
    "BREAKING NEWS - [FULL] ...", emoji, nama kanal di ekor. Arsip ini soal
    PIDATO, jadi yang ditampilkan harus nama acara/pidatonya, bukan sensasi
    beritanya.

Aturan:
- Judul asli TIDAK dihapus. build_site.py memanggil `bersih()` dari modul ini
  untuk menampilkan versi bersih; `--tulis` menyimpan hasilnya sebagai
  `title_tampilan` di data/speeches/*.json (dipakai juga oleh indeks JSON).
- Judul unggahan di tabel per-pidato dibersihkan dengan fungsi yang sama.

Pakai:
    python3 scripts/rapikan_judul.py            # lihat saja
    python3 scripts/rapikan_judul.py --tulis    # simpan title_tampilan
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEECHES = ROOT / "data" / "speeches"
REPORT = ROOT / "data" / "judul-rapi.json"

# Emoji dan simbol dekoratif yang lazim di judul kanal berita.
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d"
    "\u25CF\u2605\u2606\u2660-\u2667\u2705\u274C\u2757\u2753]"
)

# Awalan berita: [FULL], (FULL), FULL!, BREAKING NEWS, LIVE, dll.
# Token boleh dibungkus [] atau (), diulang beberapa kali (judul menumpuk).
_TOK = (r"(?:full|fuul|f[uú]{1,2}l|live(?:\s*stream)?|breaking\s*news|breaking"
        r"|happening\s*now|highlights?|terbaru|update|video|part\s*\d+|hd)")
PREFIX = re.compile(
    rf"^\s*(?:▶\s*)?(?:\[\s*{_TOK}\s*\]|\(\s*{_TOK}\s*\)|{_TOK})"
    rf"\s*[:!\-–—|]*\s*",
    re.I,
)
# Frasa sensasi di awal judul.
SENSASI = re.compile(
    r"^\s*(?:kocak|menggelegar|mengguncang|berapi-api|menggebu-gebu|heboh|geger|"
    r"viral|pukau\s*dunia|pecah\s*tawa|detik-detik|ternyata|jangan\s*kaget)\s*"
    r"[!,.:\-–—]*\s*",
    re.I,
)
# Ekor " | tvOne", " • Kompas TV" (nama kanal).
SUFFIX_PIPE = re.compile(r"\s*[|•]\s*[^|•]{1,30}\s*$")
HASHTAG = re.compile(r"\s*#[\w\-]+")
# Ekor tanggal dalam kurung: "(09/09)".
TAIL_DATE = re.compile(r"\s*\(\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?\)\s*$")

_KECIL = {"di", "ke", "dari", "dan", "yang", "untuk", "pada", "dengan", "dalam",
          "atau", "se", "the", "of", "and", "in", "on", "at", "to"}


def _smart_case(t: str) -> str:
    """Judul HURUF BESAR SEMUA diubah jadi huruf normal; akronim tetap."""
    letters = [c for c in t if c.isalpha()]
    if not letters or sum(1 for c in letters if c.isupper()) / len(letters) <= 0.7:
        return t
    out = []
    for i, w in enumerate(t.split()):
        m = re.match(r"^(\W*)(\w[\w''-]*)(\W*)$", w)
        if not m:
            out.append(w)
            continue
        pre, core, post = m.groups()
        if core.isupper() and len(core) <= 5:      # akronim: NTT, DPR, TNI, KTT
            out.append(w)
            continue
        cl = core.lower()
        core2 = cl if (i and cl in _KECIL) else (cl[:1].upper() + cl[1:])
        out.append(pre + core2 + post)
    return " ".join(out)


def bersih(judul: str) -> str:
    """Versi tampilan dari satu judul. Selalu mengembalikan sesuatu."""
    asli = (judul or "").strip()
    t = EMOJI.sub(" ", asli)
    for _ in range(6):                      # awalan bisa menumpuk
        t2 = PREFIX.sub("", t)
        if t2 == t:
            break
        t = t2
    t = SENSASI.sub("", t)
    t = SUFFIX_PIPE.sub("", t)
    t = HASHTAG.sub("", t)
    t = TAIL_DATE.sub("", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" \t\u2013\u2014-:|,!" + '"')
    t = _smart_case(t)
    # Huruf pertama jangan kecil.
    for i, ch in enumerate(t):
        if ch.isalpha():
            if ch.islower():
                t = t[:i] + ch.upper() + t[i + 1:]
            break
    return t or asli


def main() -> int:
    tulis = "--tulis" in sys.argv
    berubah = []
    total = 0
    for p in sorted(SPEECHES.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        total += 1
        judul = d.get("title") or ""
        rapi = bersih(judul)
        if rapi == judul and d.get("title_tampilan") is None:
            continue
        if rapi != judul:
            berubah.append({"file": p.name, "asli": judul, "rapi": rapi})
        if tulis and rapi != judul and d.get("title_tampilan") != rapi:
            d["title_tampilan"] = rapi
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    REPORT.write_text(json.dumps(berubah, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"entri diperiksa : {total}")
    print(f"judul dirapikan : {len(berubah)}")
    for x in berubah[:40]:
        print(f"\n  {x['file']}")
        print(f"    asli : {x['asli'][:100]}")
        print(f"    rapi : {x['rapi'][:100]}")
    if len(berubah) > 40:
        print(f"\n  ... dan {len(berubah) - 40} lagi (lihat {REPORT.name})")
    if not tulis:
        print("\n(lihat saja — jalankan dengan --tulis untuk menyimpan title_tampilan)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
