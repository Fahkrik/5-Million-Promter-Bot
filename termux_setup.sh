#!/data/data/com.termux/files/usr/bin/bash
# 5 Million Promter — Termux OFFLINE o'rnatish
# HECH QANDAY pip / internet / pkg kerak emas.
set -euo pipefail

cd "$(dirname "$0")"

PYTHON=python
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Xatolik: Termuxda Python topilmadi."
  exit 1
fi

echo "Python topildi: $($PYTHON --version)"
echo "Diqqat: pip va internet talab qilinmaydi (offline rejim)."

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env yaratildi. Uni to'ldiring: nano .env"
else
  echo "OK: .env bor"
fi

# Agar DNS ishlamasa, Telegram API IP sini ham qo'shamiz (bot shuni ishlatadi)
echo "149.154.166.110 api.telegram.org" >> "$PREFIX/etc/hosts" 2>/dev/null || true

mkdir -p assets
[ -f assets/certificate_type_1.jpg ] || echo "Diqqat: certificate_type_1.jpg yo'q"
[ -f assets/certificate_type_2.jpg ] || echo "Diqqat: certificate_type_2.jpg yo'q"

echo ""
echo "=== TAYYOR ==="
echo "Ishga tushirish: bash termux_start.sh"
echo "Fon rejim:       bash termux_bg.sh"
echo "Loglar:          tmux attach -t promter"
echo "To'xtatish:      bash termux_stop.sh"
