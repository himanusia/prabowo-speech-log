#!/usr/bin/env python3
"""refresh_meta.py — segarkan data/index.json, data/coverage.json, data/meta.json
dari arsip terkini (data/speeches/*.json).

Kenapa ada: ketiganya dulu ikut ditulis build_log.py, yang hanya jalan saat
korpus engine dibangun ulang. Setelah arsip bertambah lewat impor panel dan
transkrip Setkab, angka cakupan jadi basi di halaman Cakupan dan grafik
kelengkapan. Skrip ini menulis ulang ketiganya dari kondisi arsip sekarang.

Pakai:
    python3 scripts/refresh_meta.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WIB = timezone(timedelta(hours=7))

sys.path.insert(0, str(ROOT / "scripts"))
from build_log import build_coverage  # fungsi yang sama dengan build mesin


def terbit(d: dict) -> bool:
    if d.get("pra_era"):
        return False
    k = d.get("speaker_kind")
    return True if k is None else k in ("pidato_prabowo", "prabowo_bicara")


def engine_commit() -> str:
    try:
        out = subprocess.run(["git", "-C", str(ROOT / "engine"), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main() -> int:
    semua = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted((DATA / "speeches").glob("*.json"))]
    speeches = sorted((d for d in semua if terbit(d)),
                      key=lambda d: (d.get("date") or "", d.get("id") or ""))
    if not speeches:
        print("tidak ada pidato")
        return 1

    index = [{
        "id": s["id"], "date": s.get("date"), "title": s.get("title"),
        "channel": s.get("channel"), "video_id": s.get("video_id"),
        "youtube_url": s.get("youtube_url"), "duration_s": s.get("duration_s"),
        "duration_hms": s.get("duration_hms"), "token_count": s.get("token_count"),
        "unique_word_count": s.get("unique_word_count"),
        "source_tier": s.get("source_tier"), "fetch_method": s.get("fetch_method"),
        "upload_count": len(s.get("uploads") or []),
        "duplicate_count": s.get("duplicate_count", 0),
        "para_count": len(s.get("transcript") or []),
        "topics": s.get("topics"),
    } for s in speeches]
    (DATA / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                     encoding="utf-8")

    coverage = build_coverage(speeches)
    (DATA / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=1),
                                        encoding="utf-8")

    era = 894
    try:
        cs = json.loads((DATA / "collection-state.json").read_text(encoding="utf-8"))
        era = int(cs.get("era_total") or era)
    except Exception:
        pass

    meta = {
        "built_at": datetime.now(WIB).isoformat(timespec="seconds"),
        "engine_commit": engine_commit(),
        "engine_repo": "https://github.com/himanusia/youtube-speech-corpus",
        "event_count": len(speeches),
        "upload_count": sum(len(s.get("uploads") or []) for s in speeches),
        "token_count": sum(s.get("token_count") or 0 for s in speeches),
        "date_first": speeches[0].get("date"),
        "date_last": speeches[-1].get("date"),
        "generated_captions": sum(1 for s in speeches
                                  if (s.get("fetch_method") or "") in ("caption_api", "transcript_panel")),
        "era_videos": era,
    }
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print(f"OK  index {len(index)} pidato · coverage {len(coverage['months'])} bulan · era {era}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
