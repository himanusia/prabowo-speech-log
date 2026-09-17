#!/usr/bin/env python3
"""import_setkab.py — masukkan transkrip RESMI dari setkab.go.id.

Kenapa penting:
    Situs arsip ini dibangun dari caption otomatis YouTube. Caption otomatis
    punya salah dengar, dan beberapa pidato hanya tersedia sebagai potongan
    berita. Sekretariat Kabinet menerbitkan TRANSKRIP RESMI untuk pidato-
    pidato kenegaraan besar. Itu teks otoritatif dan bisa menutup lubang.

Cara kerja:
    Sumber: REST API WordPress setkab.go.id (kategori 87 = "Transkrip Pidato").
    Situsnya dilindungi bot-protection, tapi REST API-nya terbuka.
    Ambil semua post sejak 20 Okt 2024 beserta isi lengkapnya.

Pencocokan:
    Memakai TANGGAL PERSIS, bukan kemiripan judul. Percobaan sebelumnya
    mencocokkan judul dan gagal total: judul resmi Setkab panjang dan formal
    ("Pidato Presiden Republik Indonesia pada Penyampaian Keterangan
    Pemerintah Atas RUU tentang APBN..."), sementara judul entri arsip berasal
    dari kanal berita yang cenderung clickbait. Skor kemiripannya jatuh di
    0,26-0,58 sehingga pidato yang JELAS ada terhitung hilang.
    Tanggal tidak bisa salah seperti itu.

    - Tanggal sama dengan entri arsip -> transkrip resmi DITEMPELKAN ke entri
      itu sebagai `transkrip_resmi` (entri tidak digandakan).
    - Tanggal tidak ada padanannya -> dibuatkan entri baru bertanda
      `sumber_transkrip: "setkab_resmi"`.

Pakai:
    python3 scripts/import_setkab.py <setkab.json> [--tulis]
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPEECHES = DATA / "speeches"


def terbit(d: dict) -> bool:
    k = d.get("speaker_kind")
    return True if k is None else k in ("pidato_prabowo", "prabowo_bicara")


def slug(judul: str, tanggal: str, kunci: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (judul or "").lower()).strip("-")[:56]
    return f"{tanggal or '0000-00-00'}-{s or kunci}"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    tulis = "--tulis" in sys.argv
    setkab = json.loads(src.read_text(encoding="utf-8"))
    setkab = [x for x in setkab if x.get("panjang", 0) > 500]
    print(f"transkrip resmi Setkab: {len(setkab)}")

    # indeks entri arsip per tanggal
    per_tanggal = defaultdict(list)
    for f in SPEECHES.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if not terbit(d):
            continue
        tgl = (d.get("date") or "")[:10]
        if tgl:
            per_tanggal[tgl].append((f, d))

    import unicodedata
    from difflib import SequenceMatcher

    def norm(x: str) -> str:
        x = unicodedata.normalize("NFKD", (x or "").lower())
        x = re.sub(r"[^a-z0-9 ]", " ", x)
        x = re.sub(r"\b(pidato|sambutan|presiden|republik|indonesia|pada|di|ke|dari|dan|yang|"
                   r"dalam|rangka|acara|upacara|peresmian|keterangan|pers|resmi|tahun|kota|"
                   r"provinsi|kabupaten|jakarta|pusat)\b", " ", x)
        return " ".join(x.split())

    # Kelompokkan per tanggal, lalu pasangkan SATU-LAWAN-SATU dengan entri arsip.
    # Satu tanggal bisa memuat beberapa pidato berbeda (mis. 20 Okt 2024:
    # pelantikan MPR DAN jamuan santap malam). Menempelkan semuanya ke satu
    # entri adalah kesalahan; jadi dipasangkan berdasarkan kemiripan judul.
    per_tgl: dict[str, list] = defaultdict(list)
    for x in setkab:
        per_tgl[x["tanggal"]].append(x)
    tempel = 0
    baru = 0
    for tgl, daftar in sorted(per_tgl.items()):
        entri_tgl = list(per_tanggal.get(tgl, []))
        dipakai: set[int] = set()
        # Aturan pasti: satu tanggal dengan SATU entri arsip dan SATU transkrip
        # resmi tidak mungkin acara berbeda. Tidak perlu menebak dari judul.
        if len(entri_tgl) == 1 and len(daftar) == 1:
            f, d = entri_tgl[0]
            x = daftar[0]
            d["transkrip_resmi"] = {
                "sumber": "Sekretariat Kabinet RI", "link": x["link"],
                "judul_resmi": x["judul"], "panjang_karakter": x["panjang"],
                "teks": x["teks"],
            }
            if tulis:
                f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  TEMPEL* {tgl} (satu-satunya di tanggal itu)")
            print(f"          {(d.get('title') or '')[:42]}")
            print(f"          resmi: {x['judul'][:56]}")
            tempel += 1
            continue
        for x in daftar:
            nj = norm(x["judul"])
            best = (0.0, -1)
            for i, (f, d) in enumerate(entri_tgl):
                if i in dipakai:
                    continue
                r = SequenceMatcher(None, nj, norm(d.get("title"))).ratio()
                if r > best[0]:
                    best = (r, i)
            if best[1] >= 0 and best[0] >= 0.34:
                i = best[1]
                dipakai.add(i)
                f, d = entri_tgl[i]
                d["transkrip_resmi"] = {
                    "sumber": "Sekretariat Kabinet RI",
                    "link": x["link"],
                    "judul_resmi": x["judul"],
                    "panjang_karakter": x["panjang"],
                    "teks": x["teks"],
                }
                if tulis:
                    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  TEMPEL  {tgl} ({best[0]:.2f})  {(d.get('title') or '')[:40]}")
                print(f"          resmi: {x['judul'][:58]}")
                tempel += 1
                continue
            # Sebelum memutuskan "baru", cek kata kunci khas: pidato kenegaraan
            # dan APBN selalu punya padanan di arsip meski judulnya beda gaya.
            KHAS = ("kenegaraan", "apbn", "nota keuangan", "rapbn", "pelantikan presiden")
            kj = norm(x["judul"])
            jodoh = None
            for i, (f, d) in enumerate(entri_tgl):
                if i in dipakai:
                    continue
                if any(k in kj and k in norm(d.get("title")) for k in KHAS):
                    jodoh = i
                    break
            if jodoh is not None:
                dipakai.add(jodoh)
                f, d = entri_tgl[jodoh]
                d["transkrip_resmi"] = {
                    "sumber": "Sekretariat Kabinet RI", "link": x["link"],
                    "judul_resmi": x["judul"], "panjang_karakter": x["panjang"],
                    "teks": x["teks"],
                }
                if tulis:
                    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  TEMPEL# {tgl} (kata kunci khas)")
                print(f"          {(d.get('title') or '')[:42]}")
                print(f"          resmi: {x['judul'][:56]}")
                tempel += 1
                continue
            # tidak ada pasangan -> entri baru
            e = {
                "id": slug(x["judul"], tgl, str(x["id"])),
                "video_id": None, "date": tgl, "date_precise": True,
                "title": x["judul"], "channel": "Sekretariat Kabinet RI",
                "youtube_url": None, "duration_s": 0, "duration_hms": "?",
                "source_tier": "resmi_setkab", "fetch_method": "setkab_rest_api",
                "canonical_overridden": False,
                "canonical_note": "Transkrip resmi Sekretariat Kabinet, bukan caption otomatis.",
                "duplicate_count": 0, "uploads": [], "topics": {}, "policy_signals": {},
                "transcript": [{"t": 0.0, "d": 0.0, "text": x["teks"]}],
                "token_count": len(re.findall(r"[a-zA-Z][a-zA-Z'-]+", x["teks"])),
                "unique_word_count": 0, "snippet_count": 1,
                "sumber_transkrip": "setkab_resmi",
                "provenance": {"source": "setkab.go.id REST API (kategori 87)",
                               "link": x["link"],
                               "note": "Transkrip resmi. Tidak ada cap waktu per paragraf."},
                "speaker_kind": "pidato_prabowo", "worklist_kind": "pidato", "is_fragment": False,
            }
            print(f"  BARU    {tgl}  {x['judul'][:62]}")
            baru += 1
            if tulis:
                (SPEECHES / f"{e['id']}.json").write_text(
                    json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n  ditempelkan ke entri ada : {tempel}")
    print(f"  entri baru               : {baru}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
