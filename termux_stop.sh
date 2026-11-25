#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

termux-wake-unlock >/dev/null 2>&1 || true

if tmux has-session -t promter 2>/dev/null; then
  tmux kill-session -t promter
  echo "Bot to'xtatildi (tmux session o'chirildi)."
else
  echo "Ishlayotgan tmux session topilmadi."
fi
