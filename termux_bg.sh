#!/data/data/com.termux/files/usr/bin/bash
# Fon rejimi: tmux bo'lsa tmux, bo'lmasa nohup ishlatadi
set -euo pipefail

cd "$(dirname "$0")"

echo "=== TERMUX V3 ==="

if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t promter 2>/dev/null; then
    echo "Bot allaqachon ishlamoqda. Loglar: tmux attach -t promter"
    exit 0
  fi
  termux-wake-lock >/dev/null 2>&1 || true
  tmux new-session -d -s promter "bash termux_start.sh"
  echo "Bot fon rejimida ishga tushirildi (tmux)."
  echo "Loglar:     tmux attach -t promter"
  echo "Chiqish:    Ctrl+B, keyin D"
  echo "To'xtatish: bash termux_stop.sh"
else
  echo "tmux topilmadi -> nohup rejimi ishlatiladi."
  bash termux_nohup.sh
fi
