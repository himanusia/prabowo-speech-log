#!/usr/bin/env python3
"""import_english.py — arsipkan pidato yang transkrip aslinya BAHASA INGGRIS.

Kenapa ada berkas ini:
    Sebagian pidato Prabowo disampaikan di luar negeri dan memang dalam bahasa
    Inggris. Video-videonya hanya punya track `en-orig` (bahasa asli) plus
    `id` yang merupakan TERJEMAHAN MESIN. Memakai yang `id` akan mengganti
    pilihan kata Prabowo, sementara seluruh situs ini dibangun atas hitungan
    kata.

Keputusan yang diambil:
    Transkrip INGGRIS aslinya tetap diarsipkan supaya daftar pidatonya utuh
    dan bisa ditelusuri, TAPI entri ini ditandai `transcript_language: "en"`
    dan DIKECUALIKAN dari seluruh statistik kata berbahasa Indonesia. Jadi
    situs menyebut "ada pidato ini", tanpa mencemari angka frekuensi kata.

Pakai:
    python3 scripts/import_english.py <direktori-vtt> [--tulis]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

TAG = re.compile(r"<[^>]+>")
CUE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+-->")


def baca_vtt(path: Path) -> str:
    """Ubah VTT caption bergulir YouTube menjadi teks mengalir.

    YouTube mengulang baris yang sama di beberapa cue, jadi baris yang
    benar-benar baru diambil dari baris TERAKHIR tiap cue, lalu yang
    duplikat atau sudah tercakup baris berikutnya dibuang.
    """
    baris: list[str] = []
    for blok in path.read_text(encoding="utf-8").split("\n\n"):
        isi = [TAG.sub("", l).strip() for l in blok.splitlines()]
        isi = [l for l in isi if l and not CUE.match(l) and not l.startswith("WEBVTT")
               and not l.startswith("Kind:") and not l.startswith("Language:")]
        if isi:
            terakhir = isi[-1]
            if not baris or baris[-1] != terakhir:
                baris.append(terakhir)
    # buang baris yang sudah tercakup baris sebelumnya (caption bergulir)
    rapi: list[str] = []
    for b in baris:
        if rapi and (b == rapi[-1] or b.startswith(rapi[-1])):
            rapi[-1] = b
        elif rapi and rapi[-1].startswith(b):
            continue
        else:
            rapi.append(b)
    teks = " ".join(rapi)
    return re.sub(r"\s+", " ", teks).strip()


def slug(judul: str, tanggal: str, vid: str) -> str:
    t = re.sub(r"[^a-z0-9]+", "-", (judul or "").lower()).strip("-")[:64]
    return f"{tanggal or '0000-00-00'}-{t or vid}"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    tulis = "--tulis" in sys.argv

    wl = json.loads((DATA / "worklist.json").read_text(encoding="utf-8"))
    info = {t["video_id"]: t for t in wl["todo"]}
    KANAL = json.loads((DATA / "kanal-peta.json").read_text(encoding="utf-8")) \
        if (DATA / "kanal-peta.json").exists() else {}
    # video yang tidak ada di daftar kerja resmi (ditemukan lewat pemindaian
    # kanal media) perlu judul dan tanggal manual, kalau tidak judulnya kosong.
    TAMBAH_JUDUL = {
        "EpcOrAUKXsY": ("Pidato Presiden Prabowo pada KTT BRICS 2026 Sesi Terbuka, India, 13 September 2026", "2026-09-13"),
        "fscocewY504": ("Pernyataan Presiden Prabowo pada Sesi Terbatas KTT BRICS 2026, India, 14 September 2026", "2026-09-14"),
        "dJ5CNS2bLio": ("Pidato Presiden Prabowo pada Forum Kerja Sama Jepang-Indonesia, 30 Maret 2026", "2026-03-30"),
    }

    ada = set()
    for f in (DATA / "speeches").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        ada.add(d["video_id"])
        ada.update(u["video_id"] for u in d.get("uploads", []))

    siap: list[dict] = []
    # `en-orig` adalah track asli; `en` isinya sama persis (duplikat).
    # Ambil en-orig saja kalau ada.
    kandidat: dict[str, Path] = {}
    for f in sorted(src.glob("*.vtt")):
        vid = f.name.split(".")[0]
        if vid in kandidat:
            if ".en-orig." in f.name:
                kandidat[vid] = f
        else:
            kandidat[vid] = f
    for vid, f in sorted(kandidat.items()):
        if vid in ada:
            continue
        teks = baca_vtt(f)
        kata = re.findall(r"[a-zA-Z][a-zA-Z'-]+", teks)
        if len(kata) < 50:
            print(f"  lewat  {vid}: hanya {len(kata)} kata")
            continue
        t = info.get(vid, {})
        if vid in TAMBAH_JUDUL:
            j, tg = TAMBAH_JUDUL[vid]
            t = {"title": j, "date": tg, "date_precise": True, "kind": "pidato"}
        judul = t.get("title") or f"(tanpa judul) {vid}"
        tanggal = (t.get("date") if t.get("date_precise") else None) or "1970-01-01"
        siap.append({
            "id": slug(judul, tanggal, vid),
            "video_id": vid,
            "channel": KANAL.get(vid, "(kanal tidak tercatat)"),
            "youtube_url": f"https://www.youtube.com/watch?v={vid}",
            "duration_s": 0,
            "duration_hms": "?",
            "source_tier": "media",
            "fetch_method": "auto_caption_en_orig",
            "canonical_overridden": False,
            "canonical_note": "Diarsipkan oleh import_english.py dari track en-orig (bahasa asli pidato).",
            "duplicate_count": 0,
            "uploads": [{"video_id": vid,
                         "url": f"https://www.youtube.com/watch?v={vid}",
                         "title": judul,
                         "channel": KANAL.get(vid, "(kanal tidak tercatat)"),
                         "canonical": True}],
            "topics": {},
            "policy_signals": {},
            "provenance": {"source": "youtube auto-caption en-orig via yt-dlp",
                           "note": "Transkrip bahasa Inggris; TIDAK dihitung dalam statistik kata Indonesia."},
            "speaker_kind": "pidato_prabowo",
            "worklist_kind": "pidato",
            "is_fragment": False,
            "title": judul,
            "date": tanggal,
            "date_precise": bool(t.get("date_precise")),
            "transcript": [{"t": 0.0, "d": 0.0, "text": teks}],
            "token_count": len(kata),
            "unique_word_count": len({k.lower() for k in kata}),
            "snippet_count": 1,
            "transcript_language": "en",
            "source": "auto-caption en-orig (bahasa asli pidato)",
        })

    print("=== PIDATO BERBAHASA INGGRIS ===")
    print(f"  berkas VTT diperiksa : {len(list(src.glob('*.vtt')))}")
    print(f"  siap diarsipkan      : {len(siap)}")
    print()
    for s in siap:
        print(f"  {s['video_id']}  {s['token_count']:5,} kata  {s['title'][:56]}")

    if tulis:
        n = 0
        for s in siap:
            out = DATA / "speeches" / f"{s['video_id']}.json"
            if out.exists():
                continue
            out.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
        print(f"\n  ditulis: {n} entri ke data/speeches/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
