#!/usr/bin/env bash
# sync.sh — tarik pidato baru, rapikan, bangun ulang, lalu tayangkan sendiri.
#
#   manual   : bash scripts/sync.sh [batch]
#   otomatis : LaunchAgent com.himanusia.prabowo-sync (harian 20:30 WIB)
#   uji aman : SYNC_COMMIT=0 SYNC_PUSH=0 SYNC_DEPLOY=0 bash scripts/sync.sh 3
#
# Gerbang opsional (default 1 = jalan):
#   SYNC_SETKAB=0  lewati transkrip resmi Setkab
#   SYNC_COLLECT=0 lewati tarikan panel YouTube
#   SYNC_COMMIT=0  jangan commit
#   SYNC_PUSH=0    jangan push
#   SYNC_DEPLOY=0  jangan deploy
#
# Aman diulang; satu jalan pada satu waktu (kunci data/.sync.lock).
# Kalau build gagal, deploy tidak dijalankan — situs versi lama tetap hidup.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
LOG="$ROOT/data/sync.log"
BATCH="${1:-40}"
PY=python3

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export GIT_TERMINAL_PROMPT=0

# --- kunci: jangan sampai dua sync jalan bersamaan ---
LOCK="$ROOT/data/.sync.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  UMUR=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || date +%s) ))
  if [ "$UMUR" -gt 21600 ]; then
    rmdir "$LOCK" 2>/dev/null
  fi
  mkdir "$LOCK" 2>/dev/null || { echo "[sync] masih berjalan, keluar."; exit 0; }
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# Token Cloudflare ada di ~/.hermes/.env, tidak pernah masuk repo.
if [ -f "$HOME/.hermes/.env" ]; then
  set -a; . "$HOME/.hermes/.env" || true; set +a
fi

say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

say "=== sync mulai (batch=$BATCH) ==="

# 1. daftar kanal resmi + daftar kerja
if [ "${SYNC_DISCOVERY:-1}" = "1" ]; then
  $PY scripts/enumerate_channel.py >>"$LOG" 2>&1 \
    && say "daftar kanal diperbarui" || say "enumerate gagal, pakai daftar lama"
  $PY scripts/worklist.py >>"$LOG" 2>&1 \
    && say "daftar kerja diperbarui" || say "worklist gagal, pakai daftar lama"
else
  say "penemuan video dilewati (SYNC_DISCOVERY=0)"
fi

# 2. transkrip yang belum ada (panel YouTube, tanpa suara)
if [ "${SYNC_COLLECT:-1}" = "1" ]; then
  $PY scripts/collect_panel.py --limit "$BATCH" >>"$LOG" 2>&1
  say "collector selesai rc=$?"
  $PY scripts/status.py >>"$LOG" 2>&1 || true
else
  say "collector dilewati (SYNC_COLLECT=0)"
fi

# 3. masukkan hasil panel ke arsip
$PY scripts/import_panels.py >>"$LOG" 2>&1 \
  && say "panel masuk arsip" || say "import_panels gagal"

# 4. transkrip resmi Sekretariat Kabinet
if [ "${SYNC_SETKAB:-1}" = "1" ]; then
  $PY scripts/fetch_setkab.py >>"$LOG" 2>&1 \
    && $PY scripts/import_setkab.py data/setkab-fetch.json --tulis >>"$LOG" 2>&1 \
    && say "setkab diperiksa" || say "setkab dilewati/gagal"
else
  say "setkab dilewati (SYNC_SETKAB=0)"
fi

# 5. rapikan + bangun ulang
$PY scripts/rapikan_judul.py --tulis >>"$LOG" 2>&1 || true
$PY scripts/build_momen.py >>"$LOG" 2>&1 || true
$PY scripts/aggregate.py >>"$LOG" 2>&1 || say "aggregate gagal"
$PY scripts/insight.py >>"$LOG" 2>&1 || say "insight gagal"
$PY scripts/refresh_meta.py >>"$LOG" 2>&1 || say "refresh_meta gagal"
if ! $PY scripts/build_site.py >>"$LOG" 2>&1; then
  say "build_site gagal — berhenti sebelum deploy"
  exit 1
fi
say "situs dibangun ulang"

# 6. simpan ke repo
if [ "${SYNC_COMMIT:-1}" = "1" ] && [ -n "$(git status --porcelain)" ]; then
  git add -A
  git reset -q -- engine 2>/dev/null || true
  git commit -q -m "sync otomatis $(date '+%Y-%m-%d %H:%M')" \
    && say "commit dibuat" || say "commit dilewati"
fi
if [ "${SYNC_PUSH:-1}" = "1" ] && [ "${SYNC_COMMIT:-1}" = "1" ]; then
  git push origin main >>"$LOG" 2>&1 \
    && say "repo tersinkron" || say "push gagal (lanjut, tidak menghalangi deploy)"
fi

# 7. tayangkan
if [ "${SYNC_DEPLOY:-1}" = "1" ]; then
  CF_TOKEN="${CLOUDFLARE_API_TOKEN:-${CLOUDFLARE_API_KEY:-}}"
  CF_AKUN="${CLOUDFLARE_ACCOUNT_ID_1:-${CLOUDFLARE_ACCOUNT_ID:-}}"
  if [ -z "$CF_TOKEN" ] || [ -z "$CF_AKUN" ]; then
    say "kredensial Cloudflare tidak lengkap — deploy dilewati"
  elif CLOUDFLARE_ACCOUNT_ID="$CF_AKUN" CLOUDFLARE_API_TOKEN="$CF_TOKEN" npx --yes wrangler pages deploy docs \
       --project-name=prabowo-speech-log --branch=main --commit-dirty=true >>"$LOG" 2>&1; then
    say "deploy sukses"
  else
    say "deploy gagal — situs versi lama tetap jalan"
  fi
else
  say "deploy dilewati (SYNC_DEPLOY=0)"
fi

say "=== sync selesai ==="
