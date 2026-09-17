#!/usr/bin/env python3
"""import_known_no_transcript.py — catat pidato yang ADA tapi tidak punya transkrip.

Kenapa perlu:
    Ada pidato yang kita tahu pasti ada (judul, URL, kanal, tanggal semuanya
    diketahui) tapi videonya tidak punya track caption sama sekali — bukan
    bahasa Indonesia, bukan bahasa Inggris. Tanpa skrip ini, pidato-pidato
    itu hanya tercatat di daftar kerja dan log percobaan, TIDAK di database
    pidato. Akibatnya siapa pun yang memakai arsip ini tidak akan pernah tahu
    ada pidato yang belum masuk, kecuali membaca catatan internal.

    Itu lubang keterlacakan. Skrip ini menutupnya.

Bentuk entri:
    transcript   : []            (memang tidak ada)
    token_count  : 0
    tanpa_transkrip : True
    Entri TIDAK ikut statistik kata (aggregate.py memfilternya) dan tidak
    dihitung sebagai pidato berteks, tapi MUNCUL di daftar dengan tanda jelas.

Pakai:
    python3 scripts/import_known_no_transcript.py <berkas-json> [--tulis]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPEECHES = DATA / "speeches"


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\b(full|breaking|news|live|delay|highlight|terbaru|hd|part|official|"
               r"lengkap|presiden|prabowo|subianto|ri|republik|indonesia|pada|di|ke|dari|dan|yang)\b", " ", t)
    return " ".join(t.split())


def slug(judul: str, tanggal: str, vid: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (judul or "").lower()).strip("-")[:56]
    return f"{tanggal or '0000-00-00'}-{s or vid}"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    tulis = "--tulis" in sys.argv
    kandidat = json.loads(src.read_text(encoding="utf-8"))

    wl = {t["video_id"]: t for t in json.loads(
        (DATA / "worklist.json").read_text(encoding="utf-8"))["todo"]}

    # yang sudah ada di database (sebagai entri atau unggahan)
    ada: set[str] = set()
    for f in SPEECHES.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        ada.add(d["video_id"])
        ada.update(u["video_id"] for u in d.get("uploads", []))

    # Kata kunci khas tiap acara. Dipakai untuk menebak apakah acara ini sudah
    # terwakili entri lain (mis. pidato yang sama sudah masuk sebagai transkrip
    # bahasa Inggris). Kalau sudah, videonya cukup ditempelkan ke entri itu —
    # TIDAK dibuatkan entri baru, supaya daftar tidak menampilkan acara dua kali.
    KUNCI = [
        (r"apec", "APEC"),
        (r"\bg20\b", "G20"),
        (r"sidang umum pbb|pbb|united nations|new york", "PBB"),
        (r"\bd-?8\b", "D-8"),
        (r"brics", "BRICS"),
        (r"naruhito|jepang.*bisnis|japan.*business", "Jepang"),
        (r"kadin", "KADIN"),
        (r"two[- ]state", "TwoState"),
        (r"osaka", "Osaka"),
        (r"\beef\b|forum ekonomi rusia|putin", "Rusia"),
        (r"flores|pascagempa", "Flores"),
        (r"hut ke-80 tni|tni ke-80", "HUTTNI"),
    ]

    def cari_entri_serupa(judul: str) -> Path | None:
        j = norm(judul)
        kunci_judul = {nama for pat, nama in KUNCI if re.search(pat, judul, re.I)}
        if not kunci_judul:
            return None
        for f in SPEECHES.glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            teks = (d.get("title") or "") + " " + " ".join(
                u.get("title", "") for u in d.get("uploads", []))
            kunci_arsip = {nama for pat, nama in KUNCI if re.search(pat, teks, re.I)}
            if kunci_judul & kunci_arsip:
                return f
        return None

    ditempel = 0
    dibuat = 0
    for k in kandidat:
        vid = k["video_id"] if "video_id" in k else (k.get("vids") or [None])[0]
        if not vid or vid in ada:
            continue
        judul = k.get("judul") or k.get("title") or ""
        meta = wl.get(vid) or {}
        tanggal = k.get("date") or meta.get("date")
        presisi = bool(meta.get("date_precise")) if not k.get("date") else True
        if not tanggal or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(tanggal)):
            m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", judul)
            B = {"januari":1,"februari":2,"maret":3,"april":4,"mei":5,"juni":6,"juli":7,
                 "agustus":8,"september":9,"oktober":10,"november":11,"desember":12,
                 "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"agu":8,"ags":8,
                 "sep":9,"okt":10,"nov":11,"des":12}
            tanggal = (f"{int(m.group(3)):04d}-{B[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
                       if m and m.group(2).lower() in B else None)
            presisi = False

        vids = k.get("vids") or [vid]

        # sudah terwakili entri lain? tempelkan saja videonya ke sana.
        f_lama = cari_entri_serupa(judul)
        if f_lama:
            d_lama = json.loads(f_lama.read_text(encoding="utf-8"))
            punya = {u.get("video_id") for u in d_lama.get("uploads", [])}
            semula = len(d_lama.get("uploads", []))
            for v in vids:
                if v not in punya:
                    d_lama.setdefault("uploads", []).append({
                        "video_id": v,
                        "url": f"https://www.youtube.com/watch?v={v}",
                        "title": judul, "channel": meta.get("channel") or "",
                        "canonical": False,
                    })
            d_lama.setdefault("kanal_terkait", []).append({
                "video_id": vid,
                "catatan": "dicoba, hasil: no_indonesian_track (acara sudah terwakili entri ini)",
            })
            if tulis:
                f_lama.write_text(json.dumps(d_lama, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  TEMPEL  {vid:14} -> {d_lama['id'][:46]}  (+{len(d_lama.get('uploads', [])) - semula} unggahan)")
            ditempel += 1
            continue

        entri = {
            "id": slug(judul, tanggal or "", vid),
            "video_id": vid,
            "date": tanggal,
            "date_precise": presisi,
            "title": judul,
            "channel": meta.get("channel") or "(kanal tidak tercatat)",
            "youtube_url": f"https://www.youtube.com/watch?v={vid}",
            "duration_s": 0,
            "duration_hms": "?",
            "source_tier": "media",
            "fetch_method": "tidak_ada_caption",
            "canonical_overridden": True,
            "canonical_note": "Tidak ada track caption, baik Indonesia maupun Inggris.",
            "duplicate_count": len(vids) - 1,
            "uploads": [{"video_id": v,
                         "url": f"https://www.youtube.com/watch?v={v}",
                         "title": judul,
                         "channel": meta.get("channel") or "",
                         "canonical": v == vid} for v in vids],
            "topics": {},
            "policy_signals": {},
            "transcript": [],
            "token_count": 0,
            "unique_word_count": 0,
            "snippet_count": 0,
            "kanal_terkait": [{"video_id": v, "catatan": "dicoba, hasil: no_indonesian_track"}
                              for v in vids],
            "provenance": {
                "source": "daftar kerja + pemindaian kanal media",
                "note": "Pidato ini terkonfirmasi ada, tetapi tidak punya transkrip. "
                        "Tidak dihitung dalam statistik kata.",
            },
            "speaker_kind": "pidato_prabowo",
            "worklist_kind": meta.get("kind", "pidato"),
            "is_fragment": False,
            "tanpa_transkrip": True,
        }
        print(f"  {tanggal or '?':10}  {vid:14}  {judul[:56]}")
        if tulis:
            (SPEECHES / f"{entri['id']}.json").write_text(
                json.dumps(entri, ensure_ascii=False, indent=1), encoding="utf-8")
            dibuat += 1

    if tulis:
        print(f"\n  entri baru dibuat : {dibuat}")
        print(f"  ditempel ke entri : {ditempel}")
    else:
        print(f"\n  (lihat saja)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
