#!/data/data/com.termux/files/usr/bin/bash
# tmux'siz fon rejimi (eng ishonchli)
set -euo pipefail

cd "$(dirname "$0")"

echo "=== TERMUX V3 | nohup rejimi ==="

PYTHON=python
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3

if [ -f bot.pid ] && kill -0 "$(cat bot.pid)" 2>/dev/null; then
  echo "Bot allaqachon ishlamoqda, PID=$(cat bot.pid)"
  echo "Log: tail -f bot.log"
  exit 0
fi

termux-wake-lock >/dev/null 2>&1 || true
nohup $PYTHON bot_offline.py > bot.log 2>&1 &
echo $! > bot.pid

echo "Bot fon rejimida ishga tushirildi."
echo "PID: $(cat bot.pid)"
echo "Log ko'rish: tail -f bot.log"
echo "To'xtatish:  bash termux_stop_nohup.sh"
