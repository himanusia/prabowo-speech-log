#!/usr/bin/env python3
"""
status.py — keadaan pengumpulan: mana yang sudah, mana yang belum, kenapa.

Ini satu-satunya tempat yang menjawab "apa yang belum ditarik". Dipakai
sesudah tiap batch, dan aman dipanggil kapan saja.

Masukan : data/worklist.json + data/panel-progress.jsonl + data/speeches/*.json
Keluaran: data/collection-state.json + STATUS.md di akar repo

Status per video:
  ada_di_arsip   transkripnya sudah masuk arsip lewat korpus
  ok             berhasil diambil batch ini
  menunggu       belum pernah dicoba
  tanpa_track    tidak ada caption Indonesia (mentok permanen)
  tanpa_panel    panel transkrip tidak muncul (bisa dicoba lagi)
  panel_kosong   panel muncul tapi isinya kosong (bisa dicoba lagi)
  error          gagal teknis (bisa dicoba lagi)

Ringkasan juga menandai "blocked": beberapa kegagalan berturut-turut di
ujung log, yang biasanya berarti sedang kena batas, bukan videonya bermasalah.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WIB = timezone(timedelta(hours=7))

BLOCK_SIGNS = ("tanpa_panel", "panel_kosong", "error")
BLOCK_WINDOW = 8          # berapa kegagalan terakhir yang diperiksa
BLOCK_THRESHOLD = 5       # sebanyak ini berturut-turut = dugaan kena batas


def load_progress() -> list[dict]:
    p = DATA / "panel-progress.jsonl"
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def main() -> int:
    wl = json.loads((DATA / "worklist.json").read_text(encoding="utf-8"))
    todo = wl["todo"]
    progress = load_progress()

    archive_ids = set()
    for f in (DATA / "speeches").glob("*.json"):
        s = json.loads(f.read_text(encoding="utf-8"))
        archive_ids.add(s["video_id"])
        for u in s.get("uploads", []):
            archive_ids.add(u["video_id"])

    # status terakhir per video (baris terakhir menang)
    last: dict[str, dict] = {}
    for r in progress:
        last[r["id"]] = r

    rows = []
    for item in todo:
        vid = item["video_id"]
        if vid in archive_ids:
            state, detail = "ada_di_arsip", ""
        elif vid in last:
            st = last[vid].get("status")
            state = {"ok": "ok", "no_indonesian_track": "tanpa_track",
                     "no_panel": "tanpa_panel", "empty_panel": "panel_kosong",
                     "error": "error"}.get(st, "menunggu")
            detail = (last[vid].get("error") or "")[:120]
            if state == "ok":
                state = "ok_belum_masuk_arsip"
        else:
            state, detail = "menunggu", ""
        rows.append({
            "video_id": item["video_id"],
            "title": item["title"],
            "kind": item["kind"],
            "date": item.get("date"),
            "state": state,
            "detail": detail,
        })

    c = Counter(r["state"] for r in rows)
    by_kind = defaultdict(Counter)
    for r in rows:
        by_kind[r["kind"]][r["state"]] += 1

    # dugaan kena batas: lihat ekor log
    tail = [r.get("status") for r in progress[-BLOCK_WINDOW:]]
    bad_tail = sum(1 for s in tail if s in ("no_panel", "empty_panel", "error"))
    blocked = bad_tail >= BLOCK_THRESHOLD

    remaining = [r for r in rows if r["state"] in
                 ("menunggu", "tanpa_panel", "panel_kosong", "error", "ok_belum_masuk_arsip")]

    state = {
        "generated_at": datetime.now(WIB).isoformat(timespec="seconds"),
        "channel_total": wl.get("channel_total"),
        "era_total": wl.get("era_total"),
        "worklist_total": len(todo),
        "counts": dict(c),
        "by_kind": {k: dict(v) for k, v in by_kind.items()},
        "remaining": len(remaining),
        "blocked_suspected": blocked,
        "block_tail": tail,
    }
    (DATA / "collection-state.json").write_text(
        json.dumps({**state, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- STATUS.md ---
    lines = [
        "# Status pengumpulan",
        "",
        f"Diperbarui: {state['generated_at']}",
        "",
        "## Ringkasan",
        "",
        "| Keadaan | Jumlah |",
        "|---|---:|",
    ]
    for k in ("ada_di_arsip", "ok_belum_masuk_arsip", "menunggu", "tanpa_panel",
              "panel_kosong", "error", "tanpa_track"):
        if c.get(k):
            lines.append(f"| {k} | {c[k]} |")
    lines += [
        "",
        f"**Sisa yang masih bisa ditarik: {len(remaining)}** dari {len(todo)} video era presiden.",
        "",
    ]
    if blocked:
        lines += [
            "> ⚠ **Dugaan sedang kena batas.** "
            f"{bad_tail} dari {BLOCK_WINDOW} percobaan terakhir gagal "
            f"({', '.join(str(x) for x in tail)}).",
            "> Hentikan dulu, tunggu, lalu lanjutkan dengan `collect_panel.py`.",
            "> Yang gagal tetap tercatat sebagai sisa, jadi tidak ada yang hilang.",
            "",
        ]

    lines += ["## Per jenis", "", "| Jenis | Total | Sudah | Sisa |", "|---|---:|---:|---:|"]
    for kind, counter in sorted(by_kind.items()):
        total = sum(counter.values())
        done = counter.get("ada_di_arsip", 0) + counter.get("ok_belum_masuk_arsip", 0)
        lines.append(f"| {kind} | {total} | {done} | {total - done} |")

    lines += ["", "## Yang belum ditarik", ""]
    for kind in ("pidato", "keterangan_pers", "ambigu", "kunjungan"):
        sub = [r for r in remaining if r["kind"] == kind]
        if not sub:
            continue
        lines.append(f"### {kind} — {len(sub)} video")
        lines.append("")
        for r in sub[:40]:
            mark = {"menunggu": "·", "tanpa_panel": "P", "panel_kosong": "K",
                    "error": "E", "ok_belum_masuk_arsip": "A"}.get(r["state"], "?")
            lines.append(f"- `{mark}` {r['date'] or '??'} `{r['video_id']}` {r['title'][:78]}")
        if len(sub) > 40:
            lines.append(f"- … dan {len(sub)-40} lagi (lihat data/collection-state.json)")
        lines.append("")

    lines += [
        "## Arti tanda",
        "",
        "| Tanda | Arti | Bisa ditarik lagi? |",
        "|---|---|---|",
        "| `·` | belum pernah dicoba | ya |",
        "| `P` | panel transkrip tidak muncul | ya, coba lagi nanti |",
        "| `K` | panel muncul tapi kosong | ya, coba lagi nanti |",
        "| `E` | gagal teknis | ya |",
        "| `A` | transkrip sudah ada, tinggal masuk arsip | ya |",
        "| (tanpa tanda) | tidak ada caption Indonesia | tidak, mentok |",
        "",
    ]
    (ROOT / "STATUS.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"=== STATUS PENGUMPULAN ===")
    print(f"  era presiden            : {wl.get('era_total'):,} video")
    print(f"  masuk daftar kerja      : {len(todo):,}")
    for k, n in c.most_common():
        print(f"    {k:22} {n:>4}")
    print(f"  SISA BISA DITARIK       : {len(remaining):,}")
    print(f"  dugaan kena batas       : {'YA' if blocked else 'tidak'}")
    print(f"\n  STATUS.md + data/collection-state.json ditulis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
