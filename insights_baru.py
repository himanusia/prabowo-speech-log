#!/usr/bin/env python3
"""Cari insight baru dari arsip 390 pidato Prabowo.

Sumber: data/speeches/*.json
Aturan corpus:
- speaker_kind hanya None, pidato_prabowo, prabowo_bicara
- keluarkan 12 transkrip Inggris dan entri tanpa_transkrip
- pilih transkrip_resmi.teks bila tersedia
- buang anotasi panggung dengan regex yang ditentukan tugas

Tidak ada paket pihak ketiga.
"""
from __future__ import annotations

import json
import re
import statistics
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEECH_DIR = ROOT / "data" / "speeches"
ALLOWED_SPEAKER_KIND = {None, "pidato_prabowo", "prabowo_bicara"}

# WAJIB dari spesifikasi tugas: buang [Tepuk tangan], [Musik], dst.
STAGE_RE = re.compile(r"\[[^\]]{0,60}\]")
TOKEN_RE = re.compile(r"(?u)[^\W_]+(?:[-'][^\W_]+)*")


def clean_text(text: str) -> str:
    return unicodedata.normalize("NFC", STAGE_RE.sub(" ", text)).casefold()


def tokens(text: str) -> list[str]:
    # Token angka murni tidak diperlukan untuk phrase/entity coverage; angka
    # dihitung terpisah oleh numeric_expression_count().
    return [
        token
        for token in TOKEN_RE.findall(clean_text(text))
        if any(char.isalpha() for char in token)
    ]


def load_corpus() -> list[dict]:
    rows = []
    for path in sorted(SPEECH_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("speaker_kind") not in ALLOWED_SPEAKER_KIND:
            continue
        if data.get("transcript_language") == "en":
            continue
        if data.get("tanpa_transkrip"):
            continue

        official = data.get("transkrip_resmi") or {}
        if isinstance(official, dict) and official.get("teks"):
            text = str(official["teks"])
            source = "official"
        else:
            text = " ".join(
                str(segment.get("text", ""))
                for segment in (data.get("transcript") or [])
                if isinstance(segment, dict)
            )
            source = "caption"

        row = {
            "file": path.name,
            "title": data.get("title", ""),
            "date": data.get("date", ""),
            "year": str(data.get("date", ""))[:4],
            "source": source,
            "clean": clean_text(text),
        }
        row["tokens"] = tokens(text)
        if row["tokens"]:
            rows.append(row)

    # Guard against silently analysing a different corpus.
    assert len(rows) == 390, f"expected 390 Indonesian speeches, got {len(rows)}"
    return rows


def phrase_positions(ts: list[str], phrase: str) -> list[int]:
    wanted = phrase.casefold().split()
    return [
        i
        for i in range(len(ts) - len(wanted) + 1)
        if ts[i : i + len(wanted)] == wanted
    ]


def phrase_stats(rows: list[dict], phrase: str) -> tuple[int, int]:
    docs = 0
    occurrences = 0
    for row in rows:
        count = len(phrase_positions(row["tokens"], phrase))
        if count:
            docs += 1
            occurrences += count
    return docs, occurrences


def exact_docs(rows: list[dict], term: str) -> tuple[int, int]:
    term = term.casefold()
    return (
        sum(term in row["tokens"] for row in rows),
        sum(row["tokens"].count(term) for row in rows),
    )


def near_docs(rows: list[dict], target: str, companion: str, radius: int = 50) -> int:
    target = target.casefold()
    companion = companion.casefold()
    count = 0
    for row in rows:
        ts = row["tokens"]
        found = False
        for i, token in enumerate(ts):
            if token != target:
                continue
            left = max(0, i - radius)
            right = min(len(ts), i + radius + 1)
            if companion in ts[left:right]:
                found = True
                break
        count += found
    return count


# A numeric expression is a number (digit or spoken number) near a unit.
NUMBER_BASE = (
    r"(?:"
    r"\d{1,3}(?:[.,]\d+)?"
    r"|nol|satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|"
    r"sebelas|belasan|puluhan|ratusan|ribuan|jutaan|miliaran|triliunan|"
    r"puluh|ratus|setengah|separuh|sepertiga|seperempat"
    r")"
)
NUMBER_WITH_MAGNITUDE = (
    r"(?:" + NUMBER_BASE[3:-1] + r"|ribu|juta|miliar|milyar|triliun)"
)
UNITS = {
    "currency": r"(?:\b(?:rupiah|rp|dolar|usd|euro|yen)\b)",
    "percent": r"(?:\bpersen\b|%)",
    "scale": r"(?:\b(?:ribu|juta|miliar|milyar|triliun)\b)",
    "physical": r"(?:\b(?:orang|jiwa|unit|ton|kilometer|km|hektare|hektar)\b)",
}


def numeric_expression_count(cleaned: str, kind: str) -> int:
    unit = UNITS[kind]
    number = NUMBER_WITH_MAGNITUDE if kind == "currency" else NUMBER_BASE
    before = re.compile(r"(?i)" + number + r"(?:\s|[^\w]){0,25}" + unit)
    after = re.compile(r"(?i)" + unit + r"(?:\s|[^\w]){0,25}" + number)
    return len(before.findall(cleaned)) + len(after.findall(cleaned))


def print_results(rows: list[dict]) -> None:
    print(f"CORPUS speeches={len(rows)} lexical_tokens={sum(len(r['tokens']) for r in rows)}")
    print("sources", {source: sum(r["source"] == source for r in rows) for source in ("caption", "official")})

    # 1. Formula pembukaan lintas agama yang sama persis.
    phrase = "om swastiastu namo buddhaya salam kebajikan"
    docs, occurrences = phrase_stats(rows, phrase)
    print(f"GREETING exact={phrase!r} docs={docs} occurrences={occurrences}")

    # 2. Corruption: problem word, institution, and ±50-token context.
    korupsi_docs, korupsi_occ = exact_docs(rows, "korupsi")
    kpk_docs, kpk_occ = exact_docs(rows, "kpk")
    print(
        "CORRUPTION",
        {
            "korupsi_docs": korupsi_docs,
            "korupsi_occurrences": korupsi_occ,
            "kpk_docs": kpk_docs,
            "kpk_occurrences": kpk_occ,
            "near_rakyat_docs": near_docs(rows, "korupsi", "rakyat"),
            "near_hukum_docs": near_docs(rows, "korupsi", "hukum"),
            "near_kebocoran_docs": near_docs(rows, "korupsi", "kebocoran"),
        },
    )

    # 3. Religious/santri audience, identified only from title markers.
    religious_re = re.compile(
        r"natal|muhammadiyah|muslimat|nahdlatul|\bnu\b|santri|pesantren|"
        r"ulama|muktamar|gereja|masjid|waisak|imlek|agama|pondok",
        re.I,
    )
    religious = [row for row in rows if religious_re.search(row["title"])]
    rest = [row for row in rows if row not in religious]
    ulama = exact_docs(religious, "ulama")
    santri = exact_docs(religious, "santri")
    print(
        "RELIGIOUS_TITLE_SUBSET",
        {
            "n": len(religious),
            "ulama_docs_occ": ulama,
            "santri_docs_occ": santri,
            "rest_ulama_docs": exact_docs(rest, "ulama")[0],
            "rest_santri_docs": exact_docs(rest, "santri")[0],
        },
    )

    # 4. Repeated closing formula and its position in the speech.
    closing = "saya kira itu yang ingin saya sampaikan"
    all_positions = []
    closing_docs = 0
    for row in rows:
        positions = phrase_positions(row["tokens"], closing)
        if positions:
            closing_docs += 1
            all_positions.extend(position / len(row["tokens"]) for position in positions)
    print(
        "CLOSING_FORMULA",
        {
            "phrase": closing,
            "docs": closing_docs,
            "occurrences": len(all_positions),
            "after_half": sum(position >= 0.5 for position in all_positions),
            "median_fraction": round(statistics.median(all_positions), 4),
        },
    )

    # 5. What kind of numerical expression appears: scale vs currency.
    numeric = {}
    for kind in ("scale", "currency", "percent", "physical"):
        counts = [numeric_expression_count(row["clean"], kind) for row in rows]
        numeric[kind] = {
            "docs": sum(count > 0 for count in counts),
            "expressions": sum(counts),
        }
    print("NUMERIC_TYPES", numeric)

    # 6. Person-name footprint: broad coverage vs concentrated repetition.
    # Include the full alias Joko Widodo; searching only `jokowi` would be a
    # false null for transcripts that spell out the name.
    name_patterns = {
        "jokowi": re.compile(r"\bjokowi\b|\bjoko\s+widodo\b", re.I),
        "gibran": re.compile(r"\bgibran\b", re.I),
    }
    for name, pattern in name_patterns.items():
        docs = sum(bool(pattern.search(row["clean"])) for row in rows)
        occurrences = sum(len(pattern.findall(row["clean"])) for row in rows)
        by_year = {}
        for year in ("2024", "2025", "2026"):
            subset = [row for row in rows if row["year"] == year]
            by_year[year] = {
                "docs": sum(bool(pattern.search(row["clean"])) for row in subset),
                "n": len(subset),
            }
        print(f"NAME {name}", {"docs": docs, "occurrences": occurrences, "by_year": by_year})


if __name__ == "__main__":
    print_results(load_corpus())
