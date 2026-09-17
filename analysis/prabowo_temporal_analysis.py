#!/usr/bin/env python3
"""Analisis longitudinal pidato Prabowo, 20 Okt 2024--16 Sep 2026.

Pipeline ini sengaja hanya memakai Python stdlib agar hasil bisa dihitung ulang.
Unitnya satu berkas kanonik di data/speeches/*.json. Untuk teks, transkrip resmi
Setkab diprioritaskan; selain itu caption pada field transcript dipakai.

Aturan penting:
- stage annotations dihapus DULU: r"\\[[^\\]]{0,60}\\]".
- token denominator mengikuti token_count lama di repo: [a-z][a-z'-]+.
- semua rate adalah pooled mentions / pooled cleaned tokens * 1,000.
- topik adalah sinyal leksikal dari profiles/prabowo.json, bukan klasifikasi semantik.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEECH_DIR = ROOT / "data" / "speeches"
PROFILE_PATH = ROOT / "profiles" / "prabowo.json"
OUT_JSON = ROOT / "analysis" / "temporal_analysis.json"
OUT_MD = ROOT / "analysis" / "temporal_analysis.md"

ERA_START = "2024-10-20"
ERA_END = "2026-09-16"
STAGE_RE = re.compile(r"\[[^\]]{0,60}\]")
TOKEN_RE = re.compile(r"[a-z][a-z'-]+")

# Curated referential sets. The expression is part of the measurement definition;
# a term's zero is never interpreted without showing this set.
NAMED_PATTERNS = {
    "MBG (set alias)": r"\b(?:mbg|makan(?:an)?\s+bergizi|bergizi\s+gratis|gizi\s+gratis|sppg|badan\s+gizi\s+nasional|program\s+gizi)\b",
    "MBG (akronim)": r"\bmbg\b",
    "Danantara": r"\bdanantara\b|sovereign\s+wealth",
    "Bencana (set alias)": r"karhutla|kebakaran\s+hutan|kabut\s+asap|titik\s+api|\bbnpb\b|\bbmkg\b|gempa|banjir|longsor|erupsi|bencana|kekeringan",
    "Bencana (kata persis)": r"\bbencana\b",
    "Banjir (kata persis)": r"\bbanjir\b",
    "Korupsi/kebocoran": r"\bkorupsi|koruptor|\bmaling\b|mencuri|dicuri|kebocoran|\bbocor\b|mark.?up",
    "Swasembada": r"\bswasembada\b",
    "Hilirisasi": r"\bhilirisasi\b|\bdi\s+hilir\b",
    "Koperasi desa": r"koperasi\s+(?:desa|merah\s+putih)|\bkopdes\b",
    "Sekolah Rakyat": r"sekolah\s+rakyat",
    "B50/biodiesel": r"\bb50\b|\bb40\b|biodiesel|bahan\s+bakar\s+nabati",
    "IKN": r"\bikn\b|ibu\s+kota\s+nusantara|ibu\s+kota\s+baru",
    "PLTS/surya": r"\bplts\b|tenaga\s+surya|panel\s+surya|energi\s+surya",
    "3 juta rumah": r"(?:3|tiga)\s+juta\s+rumah",
    "Freeport": r"\bfreeport\b",
    "BRICS": r"\bbrics\b",
    "DHE/devisa ekspor": r"\bdhe\b|devisa\s+hasil\s+ekspor",
    "Stunting": r"\bstunting\b",
    "Karhutla": r"karhutla|kebakaran\s+hutan|kabut\s+asap|titik\s+api",
    "Demo/unjuk rasa": r"\bdemo\b|demonstrasi|unjuk\s+rasa|aksi\s+demo",
    "Kekuatan asing/pengkhianat": r"antek|antek-antek|londo\s+ireng|kaki\s+tangan|pengkhianat|ditunggangi|dikendalikan\s+asing|kekuatan[\s-]kekuatan\s+asing|bangsa[\s-]bangsa\s+asing",
}

EVENT_PATTERNS = {
    # Judul adalah metadata arsip, bukan isi pidato. Karena itu hasilnya hanya
    # dipakai sebagai indikator jenis acara, bukan sebagai topik.
    "sidang kabinet/ratas": r"sidang\s+kabinet|rapat\s+kabinet|\bratas\b|rapat\s+terbatas",
    "panggung partai (sempit)": r"\bpartai\b|gerindra|golkar|demokrat|\bpks\b|\bpkb\b|\bpsi\b|\bpan\b|\bppp\b|nasdem",
}

EVENT_WINDOW_TERMS = {
    "demo": r"\bdemo\b|demonstrasi|unjuk\s+rasa|aksi\s+demo",
    "polisi/polri": r"\bpolisi\b|\bpolri\b|kepolisian",
    "keamanan": r"\bkeamanan\b|ketertiban|kerusuhan",
    "bencana": r"\bbencana\b",
    "banjir": r"\bbanjir\b",
    "bantuan": r"\bbantuan\b|bantuan-bantuan",
    "rakyat": r"\brakyat\b",
    "kami": r"\bkami\b",
    "kita": r"\bkita\b",
    "korupsi": r"\bkorupsi\b|koruptor",
    "hukum": r"\bhukum\b",
    "pemerintah": r"\bpemerintah\b",
    "negara": r"\bnegara\b",
    "damai": r"\bdamai\b|perdamaian",
}


def load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def source_text(row: dict) -> tuple[str, str]:
    official = row.get("transkrip_resmi")
    if isinstance(official, dict) and official.get("teks"):
        return str(official["teks"]), "official"
    caption = "\n".join(str(x.get("text", "")) for x in (row.get("transcript") or []))
    return caption, "caption"


def clean_text(row: dict) -> str:
    # This removal must precede both tokenization and topic matching.
    raw, _ = source_text(row)
    return STAGE_RE.sub(" ", raw).casefold()


def cleaned_tokens(row: dict) -> list[str]:
    return TOKEN_RE.findall(clean_text(row))


def is_base_candidate(row: dict) -> bool:
    speaker_kind = row.get("speaker_kind")
    return speaker_kind is None or speaker_kind in ("pidato_prabowo", "prabowo_bicara")


def is_text_eligible(row: dict) -> bool:
    return is_base_candidate(row) and row.get("transcript_language") != "en" and not row.get("tanpa_transkrip")


def quarter_key(date: str) -> tuple[int, int]:
    year = int(date[:4])
    month = int(date[5:7])
    return year, (month - 1) // 3 + 1


def quarter_label(key: tuple[int, int]) -> str:
    return f"Q{key[1]} {key[0]}"


def rate(count: int, tokens: int) -> float:
    return round(count / tokens * 1000, 3) if tokens else 0.0


def pct_change(old: float, new: float) -> float | None:
    return round((new / old - 1) * 100, 1) if old else None


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    return round(sum(x * y for x, y in zip(dx, dy)) / den, 4) if den else None


def quantile(values: list[int], q: float) -> float:
    # statistics.quantiles is deterministic and available in Python 3.10+.
    if len(values) < 2:
        return float(values[0]) if values else 0.0
    return statistics.quantiles(values, n=4, method="inclusive")[0 if q == 0.25 else 2]


def regression_slope(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    xs = list(range(len(values)))
    mx, my = sum(xs) / len(xs), sum(values) / len(values)
    den = sum((x - mx) ** 2 for x in xs)
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, values)) / den, 3) if den else None


def compile_boundary(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


def counts_for(rows: list[dict], rx: re.Pattern[str]) -> tuple[int, int]:
    mentions = sum(len(rx.findall(row["clean"])) for row in rows)
    docs = sum(bool(rx.search(row["clean"])) for row in rows)
    return mentions, docs


def main() -> int:
    profile = load_profile()
    files = sorted(SPEECH_DIR.glob("*.json"))
    all_rows = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    base = [row for row in all_rows if is_base_candidate(row)]
    english = [row for row in base if row.get("transcript_language") == "en"]
    no_transcript = [row for row in base if row.get("tanpa_transkrip")]
    eligible = [row for row in base if is_text_eligible(row)]
    era = [row for row in eligible if ERA_START <= row.get("date", "") <= ERA_END]

    for row in era:
        raw, source = source_text(row)
        row["clean"] = clean_text(row)
        row["tokens_clean"] = cleaned_tokens(row)
        row["token_count_clean"] = len(row["tokens_clean"])
        row["text_source_used"] = source
        row["stage_annotation_count"] = len(STAGE_RE.findall(raw))
        row["quarter"] = quarter_key(row["date"])

    # Same cleaned method for the full 390-record Indonesian-text set; this is
    # the corpus reconciliation number before the 2 pre-inauguration records
    # are removed for the 24-month analysis.
    for row in eligible:
        raw, _ = source_text(row)
        row["all_token_count_clean"] = len(TOKEN_RE.findall(STAGE_RE.sub(" ", raw).casefold()))

    quarter_keys = sorted({row["quarter"] for row in era})
    by_quarter = {
        q: [row for row in era if row["quarter"] == q] for q in quarter_keys
    }

    # ---------- broad lexical topic table ----------
    topic_regexes = {
        name: compile_boundary(r"\b(?:" + "|".join(re.escape(word) for word in words) + r")\b")
        for name, words in profile.get("topics", {}).items()
    }
    topic_table = []
    for q in quarter_keys:
        rows = by_quarter[q]
        tokens = sum(row["token_count_clean"] for row in rows)
        values = []
        for name, rx in topic_regexes.items():
            mentions, docs = counts_for(rows, rx)
            values.append({
                "topic": name,
                "mentions": mentions,
                "speeches": docs,
                "per_1000": rate(mentions, tokens),
            })
        values.sort(key=lambda item: (-item["per_1000"], item["topic"]))
        topic_table.append({
            "quarter": quarter_label(q),
            "quarter_key": list(q),
            "speeches": len(rows),
            "tokens": tokens,
            "top3": values[:3],
            "all_topics": values,
        })

    # ---------- named terms / programs ----------
    named_regexes = {name: compile_boundary(pattern) for name, pattern in NAMED_PATTERNS.items()}
    named_quarter = []
    for q in quarter_keys:
        rows = by_quarter[q]
        tokens = sum(row["token_count_clean"] for row in rows)
        terms = {}
        for name, rx in named_regexes.items():
            mentions, docs = counts_for(rows, rx)
            terms[name] = {"mentions": mentions, "speeches": docs, "per_1000": rate(mentions, tokens)}
        named_quarter.append({"quarter": quarter_label(q), "speeches": len(rows), "tokens": tokens, "terms": terms})

    # ---------- disappearance candidates, measured month-by-month ----------
    months = sorted({row["date"][:7] for row in era})
    disappearance = []
    for name, rx in named_regexes.items():
        series = []
        for month in months:
            rows = [row for row in era if row["date"][:7] == month]
            mentions, docs = counts_for(rows, rx)
            series.append({"month": month, "mentions": mentions, "speeches": docs})
        active = [item for item in series if item["mentions"]]
        if not active:
            continue
        total = sum(item["mentions"] for item in active)
        last = active[-1]["month"]
        future_empty_months = len([month for month in months if month > last])
        # Conservative: at least 2 mentions and no hit for >=3 observed months,
        # with last hit by June. This avoids calling a one-month gap "gone".
        if total >= 2 and last <= "2026-06" and future_empty_months >= 3:
            disappearance.append({
                "term": name,
                "first_month": active[0]["month"],
                "last_month": last,
                "total_mentions": total,
                "active_months": len(active),
                "months_without_hit_after_last": future_empty_months,
                "series": series,
            })

    # ---------- framing ----------
    framing_regexes = {
        word: compile_boundary(r"\b" + word + r"\b")
        for word in ("kami", "rakyat", "kita", "saya")
    }
    framing_quarter = []
    for q in quarter_keys:
        rows = by_quarter[q]
        tokens = sum(row["token_count_clean"] for row in rows)
        terms = {}
        for word, rx in framing_regexes.items():
            mentions, docs = counts_for(rows, rx)
            terms[word] = {"mentions": mentions, "speeches": docs, "per_1000": rate(mentions, tokens)}
        framing_quarter.append({"quarter": quarter_label(q), "speeches": len(rows), "tokens": tokens, "terms": terms})

    def framing_value(q_index: int, word: str) -> float:
        return framing_quarter[q_index]["terms"][word]["per_1000"]

    framing_comparison = {
        "Q4 2024_to_Q3 2026": {
            word: {"from": framing_value(0, word), "to": framing_value(-1, word), "pct_change": pct_change(framing_value(0, word), framing_value(-1, word))}
            for word in framing_regexes
        },
        "Q1 2025_to_Q3 2026": {
            word: {"from": framing_value(1, word), "to": framing_value(-1, word), "pct_change": pct_change(framing_value(1, word), framing_value(-1, word))}
            for word in framing_regexes
        },
    }

    # ---------- length ----------
    length_quarter = []
    for q in quarter_keys:
        values = sorted(row["token_count_clean"] for row in by_quarter[q])
        length_quarter.append({
            "quarter": quarter_label(q),
            "speeches": len(values),
            "mean_tokens": round(sum(values) / len(values), 1),
            "median_tokens": statistics.median(values),
            "p25_tokens": quantile(values, 0.25),
            "p75_tokens": quantile(values, 0.75),
            "min_tokens": values[0],
            "max_tokens": values[-1],
        })
    mean_series = [float(item["mean_tokens"]) for item in length_quarter]
    median_series = [float(item["median_tokens"]) for item in length_quarter]
    first_two = sorted(row["token_count_clean"] for row in era if row["quarter"] in quarter_keys[:2])
    last_two = sorted(row["token_count_clean"] for row in era if row["quarter"] in quarter_keys[-2:])
    length_summary = {
        "mean_slope_tokens_per_quarter": regression_slope(mean_series),
        "mean_pearson_index": pearson(list(range(len(mean_series))), mean_series),
        "median_slope_tokens_per_quarter": regression_slope(median_series),
        "median_pearson_index": pearson(list(range(len(median_series))), median_series),
        "first_two_quarters": {"n": len(first_two), "mean": round(sum(first_two) / len(first_two), 1), "median": statistics.median(first_two)},
        "last_two_quarters": {"n": len(last_two), "mean": round(sum(last_two) / len(last_two), 1), "median": statistics.median(last_two)},
        "first_to_last_two_median_pct": pct_change(statistics.median(first_two), statistics.median(last_two)),
        "threshold_150_sensitivity": [],
    }
    for q in quarter_keys:
        values = sorted(row["token_count_clean"] for row in by_quarter[q] if row["token_count_clean"] >= 150)
        length_summary["threshold_150_sensitivity"].append({
            "quarter": quarter_label(q), "n": len(values), "median": statistics.median(values) if values else None,
            "mean": round(sum(values) / len(values), 1) if values else None,
        })

    # ---------- event-window comparison ----------
    ordered = sorted(era, key=lambda row: (row["date"], row["title"], row["id"]))
    event_term_regexes = {name: compile_boundary(pattern) for name, pattern in EVENT_WINDOW_TERMS.items()}
    event_definitions = {
        "demo_agustus_2025": {
            "anchor_date": "2025-08-29",
            "definition": "tanggal pertama arsip memuat Pernyataan Presiden Prabowo (29 Agustus 2025); sisi sesudah mengambil 3 entri pertama pada/ setelah tanggal anchor",
        },
        "banjir_sumatra_desember_2025": {
            "anchor_date": "2025-12-01",
            "definition": "tanggal pertama arsip memuat kunjungan langsung ke wilayah terdampak di Sumatra/Aceh; sisi sesudah mengambil 3 entri pertama pada/ setelah tanggal anchor",
        },
    }
    event_windows = {}
    for event, definition in event_definitions.items():
        anchor = definition["anchor_date"]
        before = [row for row in ordered if row["date"] < anchor][-3:]
        after = [row for row in ordered if row["date"] >= anchor][:3]

        def summarize(group: list[dict]) -> dict:
            tokens = sum(row["token_count_clean"] for row in group)
            terms = {}
            for name, rx in event_term_regexes.items():
                mentions, docs = counts_for(group, rx)
                terms[name] = {"mentions": mentions, "speeches": docs, "per_1000": rate(mentions, tokens)}
            values = [row["token_count_clean"] for row in group]
            return {
                "n": len(group), "tokens": tokens, "mean_tokens": round(sum(values) / len(values), 1),
                "median_tokens": statistics.median(values), "terms": terms,
                "records": [{"date": row["date"], "id": row["id"], "title": row["title"], "tokens": row["token_count_clean"]} for row in group],
            }

        before_summary = summarize(before)
        after_summary = summarize(after)
        deltas = {}
        for name in event_term_regexes:
            b = before_summary["terms"][name]["per_1000"]
            a = after_summary["terms"][name]["per_1000"]
            deltas[name] = {"before_per_1000": b, "after_per_1000": a, "delta_per_1000": round(a - b, 3), "pct_change": pct_change(b, a)}
        event_windows[event] = {**definition, "before": before_summary, "after": after_summary, "deltas": deltas}

    # ---------- event type by period ----------
    event_type_regexes = {name: compile_boundary(pattern) for name, pattern in EVENT_PATTERNS.items()}
    event_type_quarter = []
    for q in quarter_keys:
        rows = by_quarter[q]
        indicators = {}
        for name, rx in event_type_regexes.items():
            count = sum(bool(rx.search(row["title"])) for row in rows)
            indicators[name] = {"count": count, "share_of_records_pct": round(count / len(rows) * 100, 1) if rows else 0.0}
        event_type_quarter.append({"quarter": quarter_label(q), "speeches": len(rows), "indicators": indicators})
    event_type_correlation = {}
    for name in event_type_regexes:
        rates = [item["indicators"][name]["share_of_records_pct"] for item in event_type_quarter]
        event_type_correlation[name] = {
            "quarterly_rates_pct": rates,
            "pearson_quarter_index": pearson(list(range(len(rates))), rates),
            "first_to_last_pct_change": pct_change(rates[0], rates[-1]),
        }

    # ---------- metadata and machine-readable output ----------
    all_clean_tokens = sum(row["all_token_count_clean"] for row in eligible)
    era_clean_tokens = sum(row["token_count_clean"] for row in era)
    raw_existing_tokens = sum(row.get("token_count") or 0 for row in eligible)
    source_counts = Counter(row["text_source_used"] for row in era)
    report = {
        "method": {
            "era_start": ERA_START,
            "era_end": ERA_END,
            "input_files": len(files),
            "base_speaker_candidates": len(base),
            "english_excluded": len(english),
            "no_transcript_excluded": len(no_transcript),
            "indonesian_text_records_all": len(eligible),
            "indonesian_clean_tokens_all_390": all_clean_tokens,
            "pre_inauguration_records_excluded_from_era": len(eligible) - len(era),
            "pre_inauguration_clean_tokens": all_clean_tokens - era_clean_tokens,
            "era_records": len(era),
            "era_clean_tokens": era_clean_tokens,
            "existing_token_count_sum_before_recount": raw_existing_tokens,
            "official_text_records_in_era": source_counts.get("official", 0),
            "caption_text_records_in_era": source_counts.get("caption", 0),
            "stage_annotation_matches_in_era": sum(row["stage_annotation_count"] for row in era),
            "fragment_flagged_records_in_era": sum(bool(row.get("is_fragment")) for row in era),
            "tokenizer": r"[a-z][a-z'-]+",
            "stage_regex": r"\[[^\]]{0,60}\]",
            "rate_formula": "mentions / cleaned_tokens * 1000",
            "quarter_definition": "calendar quarter; Q4 2024 and Q3 2026 are partial at the era boundaries",
        },
        "quarter_topics": topic_table,
        "named_terms": named_quarter,
        "disappearance_candidates": disappearance,
        "framing_quarter": framing_quarter,
        "framing_comparison": framing_comparison,
        "length_quarter": length_quarter,
        "length_summary": length_summary,
        "event_windows": event_windows,
        "event_type_quarter": event_type_quarter,
        "event_type_correlation": event_type_correlation,
        "records": [{
            "id": row["id"], "date": row["date"], "title": row["title"], "tokens_clean": row["token_count_clean"],
            "source": row["text_source_used"], "quarter": quarter_label(row["quarter"]), "is_fragment": row.get("is_fragment"),
        } for row in era],
        "english_brics_records_excluded": [{"date": row.get("date"), "title": row.get("title"), "tokens": row.get("token_count")} for row in english if re.search(r"\bbrics\b", row.get("title", ""), re.I)],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(f"OK {OUT_JSON.relative_to(ROOT)}")
    print(f"OK {OUT_MD.relative_to(ROOT)}")
    print(f"390-record clean tokens: {all_clean_tokens}")
    print(f"era records/tokens: {len(era)}/{era_clean_tokens}")
    print(f"quarter rows: {len(topic_table)}")
    print(f"disappearance candidates: {[item['term'] for item in disappearance]}")
    return 0


def fmt_int(value: int | float) -> str:
    return f"{int(value):,}".replace(",", ".")


def fmt_rate(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def render_markdown(report: dict) -> str:
    m = report["method"]
    lines = [
        "# Perubahan pesan Prabowo sepanjang 24 bulan",
        "",
        f"> Analisis reproducible atas **{m['era_records']}** record teks Indonesia dalam era {m['era_start']}–{m['era_end']}, **{fmt_int(m['era_clean_tokens'])}** token setelah anotasi panggung dibuang. Q4 2024 dan Q3 2026 parsial.",
        "",
        "## Ringkasan eksekutif",
        "",
        "- Fokus leksikal tetap nasional/identitas di semua kuartal; puncaknya **34,36/1.000** kata pada Q2 2026 dan **33,65/1.000** pada Q3 2026.",
        "- MBG (set alias: MBG, Makan/Makanan Bergizi, SPPG, BGN, dll.) mencapai **1,82/1.000** kata pada Q1 2026, lalu **0,49/1.000** pada Q3 2026: turun **72,9%** dari puncak.",
        "- Kata persis **bencana** naik dari **0,02/1.000** pada Q4 2024 dan **0,02** pada Q3 2025 menjadi **0,96** pada Q4 2025; turun ke **0,45** pada Q1 2026 dan **0** pada Q2 2026.",
        "- Median panjang record naik dari **433 token** (Q4 2024) ke **1.614 token** (Q3 2026). Ini sinyal memanjang dalam arsip, bukan bukti kausal karena komposisi acara/cakupan kuartal berubah.",
        "- Klaim ‘kami turun 70%’ hanya cocok untuk endpoint **Q1 2025 → Q3 2026** (4,63 → 1,48/1.000; **−67,7%**); dari Q4 2024 ke Q3 2026 penurunannya hanya **−29,2%**. ‘Rakyat naik 39%’ cocok untuk Q4 2024 → Q3 2026 (5,31 → 7,31; **+37,5%**, pembulatan).",
        "",
        "## Metode dan rekonsiliasi corpus",
        "",
        f"- `data/speeches/*.json`: {m['input_files']} berkas. Filter `speaker_kind` menghasilkan {m['base_speaker_candidates']} kandidat; dikeluarkan {m['english_excluded']} teks Inggris dan {m['no_transcript_excluded']} tanpa transkrip, sehingga **{m['indonesian_text_records_all']} record Indonesia berteks**.",
        f"- Dengan regex token yang sama setelah pembersihan, 390 record = **{fmt_int(m['indonesian_clean_tokens_all_390'])} token**. Dua record bertanggal sebelum pelantikan (20 Okt 2024) dikeluarkan dari analisis 24 bulan: **{m['era_records']} record / {fmt_int(m['era_clean_tokens'])} token**.",
        f"- Teks resmi `transkrip_resmi.teks` dipakai bila ada ({m['official_text_records_in_era']} record era); sisanya caption. Regex anotasi panggung yang dibuang sebelum hitung: `{m['stage_regex']}`; ditemukan {fmt_int(m['stage_annotation_matches_in_era'])} anotasi pada era.",
        f"- Rate = `jumlah kecocokan / token bersih × 1.000`. Topik memakai kosakata pada `profiles/prabowo.json`; ini **sinyal leksikal**, bukan klasifikasi makna. Record tetap dihitung satu per berkas kanonik, termasuk {m['fragment_flagged_records_in_era']} yang diberi `is_fragment`.",
        "",
        "## Tabel kuartal × topik",
        "",
        "| Kuartal | n | Token | Topik 1 | Topik 2 | Topik 3 |",
        "|---|---:|---:|---|---|---|",
    ]
    for item in report["quarter_topics"]:
        top = item["top3"]
        cells = [f"{x['topic']} {fmt_rate(x['per_1000'])}" for x in top]
        lines.append(f"| {item['quarter']} | {item['speeches']} | {fmt_int(item['tokens'])} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Angka di setiap sel adalah mention per 1.000 token; angka dalam sel tidak bisa dibandingkan sebagai proporsi record. `nasional_dan_identitas` memang memuat kata luas seperti *Indonesia, negara, rakyat, bangsa* sehingga harus dibaca sebagai intensitas kosakata identitas, bukan klaim bahwa semua isi pidato adalah identitas.",
        "",
        "### Pergeseran yang terlihat",
        "",
        "- Q4 2024–Q1 2025: identitas/nasional tetap nomor satu; ekonomi dan kesehatan/gizi mengisi posisi berikutnya.",
        "- Q2–Q3 2025: kesehatan/gizi dan ekonomi menguat; Q3 2025 ekonomi mencapai **8,62/1.000**, tertinggi dalam tabel. Ini beriringan dengan kemunculan lebih seringnya istilah MBG, Sekolah Rakyat, dan partai dalam korpus, tetapi tabel tidak membuktikan sebab.",
        "- Q4 2025: posisi kedua bergeser ke pendidikan (**8,45/1.000**) dan kesehatan/gizi (**7,82/1.000**); ini kuartal yang memuat respons bencana Sumatra/Aceh.",
        "- Q1–Q3 2026: ekonomi kembali tinggi (5,58; 8,73; 6,74), pangan berada 4,47–5,21, sementara MBG turun setelah puncak Q1.",
        "",
        "## Program dan istilah yang berubah",
        "",
        "| Kuartal | Bencana persis | Bencana set alias | MBG set alias | Danantara | Kami | Rakyat |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item, frame in zip(report["named_terms"], report["framing_quarter"]):
        t = item["terms"]
        f = frame["terms"]
        lines.append(
            f"| {item['quarter']} | {fmt_rate(t['Bencana (kata persis)']['per_1000'])} | {fmt_rate(t['Bencana (set alias)']['per_1000'])} | {fmt_rate(t['MBG (set alias)']['per_1000'])} | {fmt_rate(t['Danantara']['per_1000'])} | {fmt_rate(f['kami']['per_1000'])} | {fmt_rate(f['rakyat']['per_1000'])} |"
        )
    lines += [
        "",
        "- **Bencana:** angka awal 0,02 → 0,96/1.000 (Q3 2025 → Q4 2025) adalah kenaikan **41,6×** (selisih +0,935/1.000). Setelah itu kata persisnya 0,45 pada Q1 2026 dan 0 pada Q2 2026; Q3 2026 kembali 0,25. Set alias lebih luas memberi 1,69 pada Q4 2025 karena juga menangkap BNPB/BMKG/banjir/longsor, jadi definisi harus disebut.",
        "- **MBG:** set alias naik dari 0,43 (Q4 2024) ke puncak 1,82 (Q1 2026), lalu 0,73 (Q2) dan 0,49 (Q3). Penurunan puncak→Q3 = **−72,9%**. Ini tidak berarti program berhenti: Q3 masih muncul di 13 dari 35 record (lihat JSON).",
        "- **Danantara:** mulai 0,03 (Q4 2024), melonjak 0,64 (Q1 2025), dan masih 0,48 (Q3 2026); tidak memenuhi definisi ‘muncul lalu hilang’.",
        "",
        "## Topik yang muncul lalu tidak muncul lagi",
        "",
        """Definisi operasional: istilah punya ≥2 mention, mention terakhir paling lambat Juni 2026, dan tidak muncul pada ≥3 bulan pengamatan berikutnya sampai 16 Sep 2026. Ini berarti “tidak muncul lagi dalam corpus sampai batas observasi”, bukan bukti metafisik bahwa topik tidak pernah dibahas di luar corpus.""",
        "",
        "| Istilah | Pertama | Terakhir | Total mention | Bulan aktif | Bulan kosong setelah terakhir | Kekuatan |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for item in report["disappearance_candidates"]:
        strength = "sinyal lemah–menengah (volume kecil / definisi korpus)"
        lines.append(f"| {item['term']} | {item['first_month']} | {item['last_month']} | {item['total_mentions']} | {item['active_months']} | {item['months_without_hit_after_last']} | {strength} |")
    lines += [
        "",
        "- **Freeport** berhenti setelah 3 mention (November 2024 dan Maret 2025) dan tidak muncul lagi pada 18 bulan observasi berikutnya. Karena hanya 3 mention, ini sinyal, bukan temuan kuat tentang agenda.",
        "- **BRICS** terakhir muncul Agustus 2025 (11 mention total; 5 record aktif) dan tidak muncul dalam teks Indonesia sampai September 2026. Namun ada record **KTT BRICS 2026 India** berbahasa Inggris yang dikeluarkan dari denominator; jadi klaim yang sah hanya “menghilang dari teks Indonesia yang dianalisis”, bukan “Prabowo berhenti membahas BRICS”.",
        "",
        "## Apakah pidato makin panjang?",
        "",
        "| Kuartal | n | Mean token | Median | P25–P75 | Min–maks |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report["length_quarter"]:
        lines.append(f"| {item['quarter']} | {item['speeches']} | {fmt_int(item['mean_tokens'])} | {fmt_int(item['median_tokens'])} | {fmt_int(item['p25_tokens'])}–{fmt_int(item['p75_tokens'])} | {fmt_int(item['min_tokens'])}–{fmt_int(item['max_tokens'])} |")
    ls = report["length_summary"]
    lines += [
        "",
        f"Median kuartal berkorelasi positif dengan indeks waktu (**r={ls['median_pearson_index']}**, slope {ls['median_slope_tokens_per_quarter']} token/kuartal); mean lebih sensitif terhadap pidato panjang (**r={ls['mean_pearson_index']}**, slope {ls['mean_slope_tokens_per_quarter']}). Median dua kuartal awal = {fmt_int(ls['first_two_quarters']['median'])}, dua kuartal akhir = {fmt_int(ls['last_two_quarters']['median'])}, perubahan **{ls['first_to_last_two_median_pct']}%**. Ini bukti deskriptif yang cukup konsisten, tetapi README corpus sendiri memperingatkan distribusi waktu dipengaruhi artefak penemuan/cakupan.",
        "",
        "## Tiga record sebelum vs tiga record sesudah peristiwa",
        "",
        """Jendela dibuat deterministik: tiga record terakhir dengan tanggal `< anchor`, lalu tiga record pertama dengan tanggal `>= anchor`, diurutkan `(date, title, id)`. Karena respons hari-H masuk sisi “sesudah”, interpretasi yang aman adalah perubahan pada **reaksi awal**, bukan efek kausal.""",
    ]
    for event, data in report["event_windows"].items():
        lines += ["", f"### {event.replace('_', ' ').title()} — anchor {data['anchor_date']}", "", data["definition"], "", "**Sebelum:**"]
        for row in data["before"]["records"]:
            lines.append(f"- {row['date']} — {row['tokens']} token — {row['title']}")
        lines += ["", "**Sesudah/reaksi awal:**"]
        for row in data["after"]["records"]:
            lines.append(f"- {row['date']} — {row['tokens']} token — {row['title']}")
        lines += ["", "| Istilah | Sebelum /1.000 | Sesudah /1.000 | Δ /1.000 | Δ% |", "|---|---:|---:|---:|---:|"]
        interesting = sorted(data["deltas"].items(), key=lambda kv: -abs(kv[1]["delta_per_1000"]))
        for name, delta in interesting[:8]:
            pct = "—" if delta["pct_change"] is None else f"{delta['pct_change']:.1f}%"
            lines.append(f"| {name} | {fmt_rate(delta['before_per_1000'])} | {fmt_rate(delta['after_per_1000'])} | {fmt_rate(delta['delta_per_1000'])} | {pct} |")
        lines.append("")
    demo = report["event_windows"]["demo_agustus_2025"]
    flood = report["event_windows"]["banjir_sumatra_desember_2025"]

    def event_rate(event: dict, side: str, term: str) -> float:
        return event[side]["terms"][term]["per_1000"]

    lines += [
        "Interpretasi berbasis hitungan:",
        f"- Demo: tiga sebelum = {fmt_int(demo['before']['tokens'])} token; tiga pada/setelah anchor = {fmt_int(demo['after']['tokens'])} token. `demo` {fmt_rate(event_rate(demo, 'before', 'demo'))} → {fmt_rate(event_rate(demo, 'after', 'demo'))}/1.000; `polisi/polri` {fmt_rate(event_rate(demo, 'before', 'polisi/polri'))} → {fmt_rate(event_rate(demo, 'after', 'polisi/polri'))}; `hukum` {fmt_rate(event_rate(demo, 'before', 'hukum'))} → {fmt_rate(event_rate(demo, 'after', 'hukum'))}; `kita` {fmt_rate(event_rate(demo, 'before', 'kita'))} → {fmt_rate(event_rate(demo, 'after', 'kita'))}. `kami` {fmt_rate(event_rate(demo, 'before', 'kami'))} → {fmt_rate(event_rate(demo, 'after', 'kami'))}/1.000. Ini perubahan kosakata yang jelas pada jendela, tetapi n kecil dan genre berubah dari kunjungan/eksposisi ke pernyataan/kunjungan korban.",
        f"- Bencana Sumatra: tiga sebelum = {fmt_int(flood['before']['tokens'])} token; tiga kunjungan 1 Desember = {fmt_int(flood['after']['tokens'])} token. `bencana` {fmt_rate(event_rate(flood, 'before', 'bencana'))} → {fmt_rate(event_rate(flood, 'after', 'bencana'))}/1.000 dan `bantuan` {fmt_rate(event_rate(flood, 'before', 'bantuan'))} → {fmt_rate(event_rate(flood, 'after', 'bantuan'))}; `kita` {fmt_rate(event_rate(flood, 'before', 'kita'))} → {fmt_rate(event_rate(flood, 'after', 'kita'))}. Pemendekan mean/median terjadi karena tiga record sesudah adalah laporan/kunjungan pendek; jangan baca sebagai perubahan umum panjang pidato.",
        "",
        "## Jenis acara dan periode",
        "",
        """Indikator dihitung dari judul arsip, bukan klasifikasi manual isi. `sidang kabinet/ratas` mencari “sidang kabinet”, “rapat kabinet”, “ratas”, atau “rapat terbatas”. `panggung partai (sempit)` mencari nama/kata partai. Karena indikator judul dapat salah klasifikasi dan hit-nya sedikit, korelasi diberi label sinyal lemah.""",
        "",
        "| Kuartal | Sidang kabinet/ratas | Panggung partai (sempit) |",
        "|---|---:|---:|",
    ]
    for item in report["event_type_quarter"]:
        a = item["indicators"]
        lines.append(f"| {item['quarter']} | {a['sidang kabinet/ratas']['count']}/{item['speeches']} ({a['sidang kabinet/ratas']['share_of_records_pct']:.1f}%) | {a['panggung partai (sempit)']['count']}/{item['speeches']} ({a['panggung partai (sempit)']['share_of_records_pct']:.1f}%) |")
    corr = report["event_type_correlation"]
    lines += [
        "",
        f"- Sidang kabinet/ratas: 5/69 (7,2%) pada Q4 2024, 5/56 (8,9%) Q1 2025, nol pada Q2–Q3 2025, 3/44 (6,8%) Q4 2025, nol Q1–Q2 2026, 1/35 (2,9%) Q3 2026; r terhadap indeks kuartal = **{corr['sidang kabinet/ratas']['pearson_quarter_index']}**. Ada penurunan indikatif, bukan tren monoton.",
        f"- Panggung partai sempit: 0, 3, 0, 3, 1, 0, 0, 3 record per kuartal; r = **{corr['panggung partai (sempit)']['pearson_quarter_index']}**. Tidak mendukung klaim ‘makin jarang’ secara kuat; pada Q3 2026 justru 3/35 (8,6%).",
        "- Kesimpulan jenis acara: ada sinyal sidang kabinet/ratas lebih jarang setelah awal masa jabatan, tetapi bukti lemah karena hanya 14 judul match dan arsip bukan panel acara yang lengkap. Panggung partai tidak menunjukkan penurunan yang stabil.",
        "",
        "## Batas interpretasi",
        "",
        "- Caption otomatis dan transkrip resmi tidak identik; angka kata adalah ukuran bahasa, bukan validasi angka faktual yang diucapkan.",
        "- Kategori topik overlap dan generic (mis. `anak`, `rumah`, `Indonesia`); jangan menyamakan rate dengan porsi makna pidato.",
        "- Semua klaim absence dibatasi pada corpus, bahasa, dan tanggal pengamatan. Record tanpa transkrip/berbahasa Inggris tidak boleh dihitung sebagai nol mention.",
        "- Event-window n=3 per sisi adalah deskriptif. Perbedaan panjang/genre dan record yang berdekatan tanggal dapat mengubah rate; tidak ada uji kausal.",
        "",
        "## Reproduksi",
        "",
        "```bash",
        "cd /Users/mac/.hermes/workspace/prabowo-speech-log",
        "python3 analysis/prabowo_temporal_analysis.py",
        "```",
        "",
        "Script menghasilkan `analysis/temporal_analysis.json` (angka dan record window) serta file laporan ini.",
        "",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
