#!/usr/bin/env python3
"""5 Million Promter / Dasturchi — VS Code / PC uchun asosiy ishga tushirish.

Faqat Python standart kutubxonasi ishlatiladi: pip, aiogram yoki internet
kutubxonalari kerak emas. To'liq bot kodi bot_offline.py da.

VS Code: F5 (yoki yuqori o'ngdagi ▶ Run) -> "▶ Run Bot (offline)".
Terminal: python main.py
"""
from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().with_name("bot_offline.py")), run_name="__main__")
