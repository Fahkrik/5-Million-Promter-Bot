#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

termux-wake-unlock >/dev/null 2>&1 || true

if [ -f bot.pid ]; then
  PID=$(cat bot.pid)
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Bot to'xtatildi (PID=$PID)."
  else
    echo "Bot allaqachon to'xtagan."
  fi
  rm -f bot.pid
else
  echo "bot.pid topilmadi."
fi
