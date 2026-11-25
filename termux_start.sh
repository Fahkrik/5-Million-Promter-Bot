#!/data/data/com.termux/files/usr/bin/bash
# OFFLINE botni ishga tushirish — pip kerak emas
set -euo pipefail

cd "$(dirname "$0")"

PYTHON=python
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Avval .env ni to'ldiring: nano .env"
  exit 1
fi

if ! grep -Eq '^BOT_TOKEN=.+' .env; then
  echo "Xatolik: .env ichida BOT_TOKEN bo'sh. Avval to'ldiring: nano .env"
  exit 1
fi

echo "=== TERMUX V3 | bot_offline.py (pip/aiogram kerak emas) ==="

termux-wake-lock >/dev/null 2>&1 || true

echo "OFFLINE bot ishga tushyapti... (to'xtatish: Ctrl+C)"
exec $PYTHON bot_offline.py
