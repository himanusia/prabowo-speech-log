#!/usr/bin/env python3
"""import_panels.py — ubah transkrip di data/panel_raw/ menjadi entri arsip.

Ini langkah yang HILANG. Selama ini penarik berjalan dan menyimpan ratusan
transkrip ke data/panel_raw/, tetapi tidak ada satu pun skrip yang
mengubahnya menjadi data/speeches/*.json. Akibatnya arsip berhenti di 67
pidato meski transkripnya sudah ada — persis yang membuat jumlah di situs
tidak pernah bertambah.

Aturan:
- Hanya panel berstatus `ok` dan punya `raw_snippets`.
- Beberapa unggahan untuk acara yang sama digabung jadi SATU entri; yang
  transkripnya terpanjang jadi kanonik, sisanya masuk daftar `uploads`.
- Tanggal diambil dari worklist; kalau tidak presisi, dicoba dibaca dari
  judul (banyak judul memuat "Jakarta, 3 Maret 2026").
- Angka dihitung ulang dari transkrip yang benar-benar dipakai, bukan
  diwarisi dari unggahan lain.

Pakai:
    python3 scripts/import_panels.py            # tulis ke data/speeches/
    python3 scripts/import_panels.py --dry-run  # lihat dulu, tidak menulis
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "panel_raw"
SPEECHES = DATA / "speeches"
PROFILE = ROOT / "profiles" / "prabowo.json"

BULAN = {b: i for i, b in enumerate(
    ["januari", "februari", "maret", "april", "mei", "juni", "juli",
     "agustus", "september", "oktober", "november", "desember"], start=1)}


def norm(text: str) -> str:
    """Kunci pengelompokan: buang aksen, tanda baca, dan kata kanal."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    buang = {"full", "fragment", "breaking", "news", "live", "lengkap", "resmi",
             "video", "hd", "part", "official"}
    return " ".join(w for w in text.split() if w not in buang)[:190]


def baca_tanggal_dari_judul(judul: str) -> str | None:
    """Banyak judul memuat tanggal lengkap, mis. 'Jakarta, 3 Maret 2026'."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", judul or "")
    if m:
        b = BULAN.get(m.group(2).lower())
        if b:
            return f"{int(m.group(3)):04d}-{b:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", judul or "")
    if m:
        a, b2, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12:            # 29/8/2024 -> hari dulu
            return f"{c:04d}-{b2:02d}-{a:02d}"
        return f"{c:04d}-{a:02d}-{b2:02d}"
    return None


def hms(detik: float | None) -> str | None:
    if not detik:
        return None
    d = int(detik)
    h, sisa = divmod(d, 3600)
    m, s = divmod(sisa, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def slug(judul: str, tanggal: str, maks: int = 7) -> str:
    t = unicodedata.normalize("NFKD", judul or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9\s-]", " ", t)
    kata = [w for w in t.split() if w and w not in {
        "pidato", "presiden", "prabowo", "subianto", "sambutan", "ri", "republik",
        "indonesia", "full", "lengkap", "live", "resmi", "video"}]
    return f"{tanggal}-{'-'.join(kata[:maks]) or 'pidato'}"


def paragraf(snippets: list[dict]) -> list[dict]:
    """Gabungkan snippet jadi paragraf; cap waktu = snippet pertama tiap blok."""
    blok, buf, mulai, durasi = [], [], None, 0.0

    def tutup():
        nonlocal buf, mulai, durasi
        if buf and mulai is not None:
            teks = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if teks:
                blok.append({"t": round(mulai, 2), "d": round(durasi, 2), "text": teks})
        buf, mulai, durasi = [], None, 0.0

    for sn in snippets:
        teks = re.sub(r"\s+", " ", sn.get("text", "")).strip()
        if not teks:
            continue
        if mulai is None:
            mulai = float(sn.get("start", 0.0))
        buf.append(teks)
        durasi += float(sn.get("duration", 0.0))
        if len(" ".join(buf)) > 400 or teks.endswith((".", "?", "!")):
            tutup()
    tutup()
    return blok


def hitung_topik(teks: str, topik: dict) -> dict:
    rendah = teks.lower()
    return {k: sum(len(re.findall(rf"\b{re.escape(w)}\b", rendah)) for w in kata)
            for k, kata in topik.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    prof = json.loads(PROFILE.read_text(encoding="utf-8"))
    topik_kw = prof.get("topics", {})
    prog_re = prof.get("programs", [])
    konsep_re = prof.get("concepts", [])

    wl = json.loads((DATA / "worklist.json").read_text(encoding="utf-8"))
    info = {t["video_id"]: t for t in wl["todo"]}

    arsip = set()
    for f in SPEECHES.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        arsip.add(d["video_id"])
        for u in d.get("uploads", []):
            arsip.add(u["video_id"])

    panel = []
    for f in RAW.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("status") != "ok" or not d.get("raw_snippets"):
            continue
        if d["id"] in arsip:
            continue
        panel.append(d)
    panel.sort(key=lambda d: -d.get("snippet_count", 0))
    if a.limit:
        panel = panel[:a.limit]

    print(f"panel siap diimpor : {len(panel)}")
    if not panel:
        print("tidak ada yang perlu diimpor")
        return 0

    # kelompokkan acara yang sama
    grup: dict[str, list[dict]] = {}
    for d in panel:
        grup.setdefault(norm(d.get("title", "")) or d["id"], []).append(d)

    dibuat = 0
    for kunci, anggota in grup.items():
        anggota.sort(key=lambda d: -len(d.get("raw_snippets", [])))
        utama = anggota[0]
        t = info.get(utama["id"], {})
        judul = utama.get("title", "")
        # Tanggal dicari berurutan, dan kalau tidak ada yang presisi kita
        # TIDAK mengarang tanggal penuh — cukup tahunnya, ditandai presisi
        # rendah supaya situs bisa menampilkannya dengan jujur.
        presisi = True
        tanggal = t.get("date") if t.get("date_precise") else None
        if not tanggal:
            dari_judul = baca_tanggal_dari_judul(judul)
            if dari_judul:
                tanggal = dari_judul
            else:
                presisi = False
                th = re.match(r"(\d{4})", t.get("date") or judul or "")
                tanggal = f"{th.group(1)}-01-01" if th and th.group(1) != "0000" else None
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", tanggal or ""):
            presisi = False
            tanggal = "2025-01-01"      # tidak diketahui: bukan karangan, tapi ditandai

        blok = paragraf(utama.get("raw_snippets", []))
        if not blok:
            continue
        teks_penuh = " ".join(b["text"] for b in blok)
        kata = re.findall(r"[a-z][a-z'-]+", teks_penuh.lower())
        total_durasi = sum(float(s.get("duration", 0.0)) for s in utama["raw_snippets"])

        kanal = utama.get("channel", "")
        tier = "official" if any(
            x in kanal.lower() for x in prof["source_tiers"]["official_channel_or_title"]) else "media"

        rekaman = {
            "id": slug(judul, tanggal),
            "video_id": utama["id"],
            "date": tanggal,
            "date_precise": presisi,
            "title": judul,
            "channel": kanal,
            "youtube_url": utama.get("url", f"https://www.youtube.com/watch?v={utama['id']}"),
            "duration_s": int(total_durasi) or None,
            "duration_hms": hms(total_durasi),
            "source_tier": tier,
            "fetch_method": utama.get("fetch_method", "transcript_panel"),
            "snippet_count": len(utama.get("raw_snippets", [])),
            "token_count": len(kata),
            "unique_word_count": len(set(kata)),
            "canonical_overridden": False,
            "canonical_note": "Diimpor oleh import_panels.py dari panel transkrip.",
            "duplicate_count": max(0, len(anggota) - 1),
            "uploads": [{"video_id": m["id"], "url": m.get("url", ""),
                         "title": m.get("title", ""), "channel": m.get("channel", ""),
                         "canonical": m["id"] == utama["id"]} for m in anggota],
            "topics": hitung_topik(teks_penuh, topik_kw),
            "policy_signals": {},
            "transcript": blok,
            "provenance": {
                "source": "youtube transcript panel via scripts/collect_panel.py",
                "imported_by": "scripts/import_panels.py",
                "worklist_kind": t.get("kind"),
            },
        }
        # sinyal program & konsep: hitung kemunculan regex profil
        for p in prog_re:
            n = len(re.findall(p["re"], teks_penuh, re.I))
            if n:
                rekaman["policy_signals"][p["label"]] = {"count": n}
        for c in konsep_re:
            n = len(re.findall(c["re"], teks_penuh, re.I))
            if n:
                rekaman["policy_signals"][c["label"]] = {"count": n}

        if a.dry_run:
            if dibuat < 8:
                print(f"  {tanggal}  {judul[:62]}")
            dibuat += 1
            continue
        (SPEECHES / f"{rekaman['id']}.json").write_text(
            json.dumps(rekaman, ensure_ascii=False, indent=1), encoding="utf-8")
        dibuat += 1

    print(f"{'akan dibuat' if a.dry_run else 'dibuat'} : {dibuat} entri")
    if not a.dry_run:
        print(f"total arsip sekarang: {len(list(SPEECHES.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
