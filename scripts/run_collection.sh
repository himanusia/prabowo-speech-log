#!/usr/bin/env bash
# run_collection.sh — tarik transkrip sampai habis, berhenti sendiri kalau kena batas.
#
# Tiap putaran: ambil satu batch, perbarui status, lalu putuskan lanjut atau berhenti.
# Keputusan berhenti diambil dari status.py (mendeteksi kegagalan berturut-turut),
# bukan dari tebakan. Semua yang belum terambil tetap tercatat di STATUS.md.
#
# Pakai:
#   bash scripts/run_collection.sh              # batch 60, sampai habis
#   bash scripts/run_collection.sh 30           # batch lebih kecil
#   CORPUS_ROOT=/path bash scripts/run_collection.sh

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
BATCH="${1:-60}"
PY=python3
LOG="$ROOT/data/collection-run.log"

echo "=== mulai $(date '+%Y-%m-%d %H:%M:%S') batch=$BATCH ===" | tee -a "$LOG"

round=0
while true; do
  round=$((round + 1))
  echo "" | tee -a "$LOG"
  echo "--- putaran $round $(date '+%H:%M:%S') ---" | tee -a "$LOG"

  # prioritas: pidato dulu, lalu keterangan pers, lalu ambigu, terakhir kunjungan
  $PY scripts/collect_panel.py --limit "$BATCH" >>"$LOG" 2>&1
  rc=$?

  $PY scripts/status.py | tee -a "$LOG" >/dev/null
  $PY scripts/status.py >/dev/null 2>&1

  remaining=$($PY - <<'EOF'
import json, pathlib
p = pathlib.Path("data/collection-state.json")
print(json.loads(p.read_text())["remaining"] if p.exists() else -1)
EOF
)
  blocked=$($PY - <<'EOF'
import json, pathlib
p = pathlib.Path("data/collection-state.json")
print("yes" if json.loads(p.read_text()).get("blocked_suspected") else "no") if p.exists() else print("no")
EOF
)

  echo "  sisa=$remaining  kena_batas=$blocked  rc=$rc" | tee -a "$LOG"

  if [ "$blocked" = "yes" ]; then
    echo "" | tee -a "$LOG"
    echo "BERHENTI: dugaan kena batas YouTube." | tee -a "$LOG"
    echo "  Yang belum terambil tetap tercatat di STATUS.md — tidak ada yang hilang." | tee -a "$LOG"
    echo "  Lanjutkan nanti dengan: bash scripts/run_collection.sh" | tee -a "$LOG"
    break
  fi

  if [ "$remaining" -le 0 ] 2>/dev/null; then
    echo "" | tee -a "$LOG"
    echo "SELESAI: tidak ada sisa yang bisa ditarik." | tee -a "$LOG"
    break
  fi

  # kalau batch ini tidak menghasilkan apa-apa dan tidak terdeteksi blok,
  # berhenti juga supaya tidak berputar tanpa hasil
  if [ "$rc" -ne 0 ]; then
    echo "BERHENTI: collector keluar dengan kode $rc" | tee -a "$LOG"
    break
  fi

  sleep 20
done

echo "" | tee -a "$LOG"
echo "=== selesai $(date '+%Y-%m-%d %H:%M:%S') setelah $round putaran ===" | tee -a "$LOG"
$PY scripts/status.py | tee -a "$LOG"
