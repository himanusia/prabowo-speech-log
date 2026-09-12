#!/usr/bin/env python3
"""
audit_speeches.py — apakah entri yang ada benar-benar pidato, dan apakah
transkripnya sehat?

Pelajaran yang ditanam di sini: panjang BUKAN penanda pidato atau bukan.
Sambutan Hari Santri 2:55 adalah pidato sungguhan; sebaliknya transkrip
70 detik dari acara 1 jam 39 menit adalah klip, dan itu masalah pemilihan
sumber, bukan masalah panjang pidato.

Yang diuji, dan buktinya:
  1. bentuk pembuka  — salam ritual, sapaan resmi, atau mulai di tengah kalimat
  2. bentuk penutup  — ada "terima kasih"/salam penutup
  3. ukuran          — token vs durasi (rasio wajar ~60-90 kata/menit)
  4. pembanding      — kanonik vs unggahan terpanjang di acara yang sama

Keluaran: data/audit-pidato.json. Murni pembacaan, tidak mengubah apa pun.
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

RE_PRESS = re.compile(r"keterangan\s+pers|press\s+statement|pernyataan\s+pers|doorstop", re.I)
RE_SPEECH = re.compile(
    r"\b(pidato|sambutan|arahan|amanat|pengarahan|orasi|kuliah\s+umum|keynote|"
    r"pidato\s+kenegaraan|remarks|speech|address)\b", re.I)

# pembuka ritual (keagamaan / kebangsaan)
RE_RITUAL = re.compile(
    r"(bismillah|assalamualaikum|assalamu'alaikum|salam\s+sejahtera|shalom|"
    r"om\s+swastiastu|namo\s+buddhaya|salam\s+kebajikan|salve)", re.I)
# sapaan resmi (bukan ritual, tapi tetap pembuka pidato)
RE_FORMAL = re.compile(
    r"(yang\s+saya\s+hormati|yang\s+terhormat|saudara-saudara|hadirin|"
    r"sidang\s+dewan|saudara\s+presiden|bapak\s+presiden|para\s+hadirin|"
    r"para\s+yang\s+saya\s+muliakan|pimpinan\s+dewan)", re.I)
RE_CLOSING = re.compile(
    r"(terima\s+kasih|wassalamualaikum|wasalamualaikum|merdeka|salam\s+kebajikan|"
    r"namo\s+budhaya|semoga)", re.I)


def main() -> int:
    rows = []
    for p in sorted((DATA / "speeches").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        text = "\n".join(x["text"] for x in s["transcript"])
        head = text[:300].strip()
        tail = text[-260:].strip()
        toks = s["token_count"] or 0
        dur = s["duration_s"] or 0

        ups = [u for u in s["uploads"] if u.get("token_count")]
        longest = max((u["token_count"] for u in ups), default=toks)
        ratio = (toks / longest) if longest else 1.0

        title_kind = "keterangan_pers" if RE_PRESS.search(s["title"]) else (
            "pidato" if RE_SPEECH.search(s["title"]) else "lain")

        starts_mid = bool(head) and head[0].islower()
        has_ritual = bool(RE_RITUAL.search(head))
        has_formal = bool(RE_FORMAL.search(head))
        has_closing = bool(RE_CLOSING.search(tail))
        wpm = round(toks / (dur / 60), 1) if dur else None

        flags = []
        if title_kind == "keterangan_pers":
            flags.append("judulnya keterangan pers, bukan pidato")
        if not (has_ritual or has_formal):
            flags.append("pembukanya bukan salam ritual maupun sapaan resmi")
        if starts_mid:
            flags.append("transkrip dimulai di tengah kalimat — kemungkinan terpotong di awal")
        if not has_closing:
            flags.append("tidak ada penutup (terima kasih/salam)")
        if wpm is not None and wpm < 25:
            flags.append(f"hanya {wpm} kata/menit — terlalu jarang untuk pidato utuh")

        # --- putusan ---
        if ratio < 0.5 and len(ups) > 1:
            verdict = "kanonik_salah_pilih"
        elif toks < 150 and dur > 120:
            verdict = "transkrip_rusak"
        elif starts_mid and toks < 300:
            verdict = "transkrip_terpotong"
        elif title_kind == "keterangan_pers":
            verdict = "keterangan_pers"
        elif has_ritual or has_formal:
            verdict = "pidato"
        else:
            verdict = "perlu_diperiksa"

        rows.append({
            "id": s["id"], "date": s["date"], "title": s["title"],
            "channel": s["channel"], "video_id": s["video_id"],
            "tokens": toks, "duration_s": dur, "wpm": wpm,
            "uploads": len(ups),
            "longest_sibling_tokens": longest,
            "canonical_ratio": round(ratio, 3),
            "title_kind": title_kind,
            "opens_ritual": has_ritual, "opens_formal": has_formal,
            "starts_mid_sentence": starts_mid, "has_closing": has_closing,
            "verdict": verdict, "flags": flags,
            "opening_140": head[:140],
        })

    c = Counter(r["verdict"] for r in rows)
    print(f"=== AUDIT {len(rows)} ENTRI ===\n")
    for k, n in c.most_common():
        print(f"  {k:22} {n:>3}")

    for v in ("kanonik_salah_pilih", "transkrip_rusak", "transkrip_terpotong",
              "keterangan_pers", "perlu_diperiksa"):
        hit = [r for r in rows if r["verdict"] == v]
        if not hit:
            continue
        print(f"\n=== {v.upper().replace('_',' ')} ===")
        for r in hit:
            if v == "kanonik_salah_pilih":
                print(f'  {r["date"]}  kanonik {r["tokens"]:,} vs {r["longest_sibling_tokens"]:,} '
                      f'({r["canonical_ratio"]*100:.1f}%)  {r["title"][:48]}')
            else:
                print(f'  {r["date"]}  {r["tokens"]:>6}tok  {r["title"][:60]}')
            for f in r["flags"]:
                print(f'        - {f}')

    (DATA / "audit-pidato.json").write_text(json.dumps({
        "generated_at": datetime.now(WIB).isoformat(timespec="seconds"),
        "total": len(rows),
        "verdicts": dict(c),
        "rows": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nOK  data/audit-pidato.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
