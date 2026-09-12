#!/usr/bin/env python3
"""
aggregate.py — hitung angka untuk halaman utama dari transkrip.

Masukan : data/speeches/*.json  +  profiles/<nama>.json
Keluaran: data/home.json

Prinsip yang ditanam di sini: setiap program dan konsep diukur dari SELURUH
cara ia disebut, bukan dari satu kata yang kita harapkan. Definisi rujukannya
ada di profil, bukan di kode ini — supaya domain knowledge punya satu rumah.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROFILE = ROOT / "profiles" / "prabowo.json"
OUT = DATA / "home.json"


def load_speeches() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((DATA / "speeches").glob("*.json"))]


def text_of(s: dict) -> str:
    return "\n".join(p["text"] for p in s["transcript"])


def main() -> int:
    prof = json.loads(PROFILE.read_text(encoding="utf-8"))
    speeches = load_speeches()
    if not speeches:
        print("tidak ada pidato — jalankan build_log.py dulu")
        return 1

    N = len(speeches)
    total_tokens = sum(s["token_count"] or 0 for s in speeches)

    # ---------- cakupan ----------
    years = Counter(s["date"][:4] for s in speeches)
    year_tokens = defaultdict(int)
    for s in speeches:
        year_tokens[s["date"][:4]] += s["token_count"] or 0

    # ---------- topik ----------
    # Dihitung dari transkrip langsung, bukan dibaca dari keluaran mesin —
    # supaya skrip ini berdiri sendiri dan tidak rapuh terhadap perubahan skema.
    topic_order = prof.get("topic_order") or sorted(prof.get("topics", {}))
    topic_words = prof.get("topics", {})
    topic_agg = []
    for name in topic_order:
        vocab = topic_words.get(name) or []
        if not vocab:
            continue
        rx = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in vocab) + r")\b", re.I)
        count = 0
        ev = 0
        for s in speeches:
            found = rx.findall(text_of(s))
            count += len(found)
            if found:
                ev += 1
        topic_agg.append({
            "topic": name,
            "count": count,
            "per_1000": round(count / total_tokens * 1000, 2) if total_tokens else 0,
            "speeches": ev,
            "share": round(ev / N * 100, 1),
        })
    topic_metrics = sorted(topic_agg, key=lambda x: -x["per_1000"])

    # ---------- program & konsep ----------
    def measure(patterns: list[dict]) -> list[dict]:
        out = []
        for pat in patterns:
            rx = re.compile(pat["re"], re.I)
            hits = 0
            ev = []
            for s in speeches:
                found = rx.findall(text_of(s))
                if found:
                    ev.append(s)
                    hits += len(found)
            out.append({
                "label": pat["label"],
                "full": pat.get("full") or pat.get("note") or "",
                "events": len(ev),
                "share": round(len(ev) / N * 100, 1),
                "mentions": hits,
                "per_event": round(hits / len(ev), 1) if ev else 0,
                "first": min((s["date"] for s in ev), default=None),
                "last": max((s["date"] for s in ev), default=None),
            })
        out.sort(key=lambda x: (-x["share"], -x["mentions"]))
        return out

    programs = measure(prof.get("programs", []))
    concepts = measure(prof.get("concepts", []))

    # ---------- framing ----------
    PRON = {
        "kita": r"\bkita\b", "saya": r"\bsaya\b", "kami": r"\bkami\b",
        "mereka": r"\bmereka\b", "saudara": r"\bsaudara(?:-saudara)?\b",
        "kalian": r"\bkalian\b", "rakyat": r"\brakyat\b",
    }
    framing = []
    for label, rx in PRON.items():
        r = re.compile(rx, re.I)
        c = sum(len(r.findall(text_of(s))) for s in speeches)
        ev = sum(1 for s in speeches if r.search(text_of(s)))
        framing.append({
            "label": label, "count": c,
            "per_1000": round(c / total_tokens * 1000, 2) if total_tokens else 0,
            "speeches": ev, "share": round(ev / N * 100, 1),
        })
    framing.sort(key=lambda x: -x["per_1000"])
    kita = next((f for f in framing if f["label"] == "kita"), None)
    saya = next((f for f in framing if f["label"] == "saya"), None)
    ratio = round(kita["per_1000"] / saya["per_1000"], 2) if kita and saya and saya["per_1000"] else None

    # framing per tahun
    per_year_framing = []
    for y in sorted(years):
        sub = [s for s in speeches if s["date"].startswith(y)]
        tk = sum(s["token_count"] or 0 for s in sub)
        if not tk:
            continue
        ck = sum(len(re.findall(r"\bkita\b", text_of(s), re.I)) for s in sub)
        cs = sum(len(re.findall(r"\bsaya\b", text_of(s), re.I)) for s in sub)
        per_year_framing.append({
            "year": y, "speeches": len(sub), "tokens": tk,
            "kita_per_1000": round(ck / tk * 1000, 2),
            "saya_per_1000": round(cs / tk * 1000, 2),
            "ratio": round(ck / cs, 2) if cs else None,
        })

    # ---------- kata isi teratas ----------
    STOP = set(prof.get("stopwords", []))
    PRONOUNS = set(prof.get("pronouns", []))
    words = Counter()
    for s in speeches:
        for w in re.findall(r"[a-z][a-z'-]{2,}", text_of(s).lower()):
            if w in STOP or w in PRONOUNS or len(w) < 4:
                continue
            words[w] += 1
    top_words = [{"word": w, "count": c, "per_1000": round(c / total_tokens * 1000, 2)}
                 for w, c in words.most_common(60)]

    # Sebaran panjang pidato — untuk histogram.
    buckets = [(0, 500), (500, 1000), (1000, 1500), (1500, 2000), (2000, 3000),
               (3000, 4000), (4000, 6000), (6000, 10**9)]
    labels = ["<500", "500–1k", "1k–1,5k", "1,5k–2k", "2k–3k", "3k–4k", "4k–6k", ">6k"]
    hist = []
    for (lo, hi), lab in zip(buckets, labels):
        n = sum(1 for s in speeches if lo <= (s["token_count"] or 0) < hi)
        hist.append({"label": lab, "count": n})
    max_hist = max((h["count"] for h in hist), default=1)

    # Kata terbanyak per tahun — untuk melihat pergeseran kosakata
    per_year_words = []
    for y in sorted(years):
        sub = [s for s in speeches if s["date"].startswith(y)]
        tk = sum(s["token_count"] or 0 for s in sub)
        c = Counter()
        for s in sub:
            for w in re.findall(r"[a-z][a-z'-]{2,}", text_of(s).lower()):
                if w in STOP or w in PRONOUNS or len(w) < 4:
                    continue
                c[w] += 1
        per_year_words.append({
            "year": y, "tokens": tk,
            "top": [{"word": w, "count": n,
                     "per_1000": round(n / tk * 1000, 2) if tk else 0}
                    for w, n in c.most_common(8)],
        })

    # ---------- panjang pidato ----------
    toks = sorted((s["token_count"] or 0) for s in speeches)
    mid = toks[len(toks) // 2] if toks else 0
    longest = max(speeches, key=lambda s: s["token_count"] or 0)
    shortest = min(speeches, key=lambda s: s["token_count"] or 0)

    home = {
        "event_count": N,
        "token_count": total_tokens,
        "upload_count": sum(len(s["uploads"]) for s in speeches),
        "date_first": speeches[0]["date"],
        "date_last": speeches[-1]["date"],
        "length": {
            "median": mid, "longest": longest["token_count"], "longest_title": longest["title"],
            "shortest": shortest["token_count"], "shortest_title": shortest["title"],
        },
        "topics": topic_metrics,
        "programs": programs,
        "concepts": concepts,
        "framing": framing,
        "kita_saya_ratio": ratio,
        "framing_per_year": per_year_framing,
        "top_words": top_words,
        "length_histogram": hist,
        "length_histogram_max": max_hist,
        "per_year_words": per_year_words,
        "per_year": [{"year": y, "speeches": years[y], "tokens": year_tokens[y]}
                     for y in sorted(years)],
    }
    OUT.write_text(json.dumps(home, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"OK  home.json  ({N} pidato, {total_tokens:,} token)")
    print(f"    program teratas : {programs[0]['label']} {programs[0]['share']}%")
    print(f"    konsep teratas  : {concepts[0]['label']} {concepts[0]['share']}%")
    print(f"    rasio kita/saya : {ratio}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
