# Termux / stdlib-only fallback:
# aiogram o'rnatilmagan bo'lsa (pip yo'q/internet yo'q), xatolik berish o'rniga
# to'liq ishlaydigan bot_offline.py ga o'tamiz. Shunda qaysi faylni ishga
# tushirsangiz ham (bot.py yoki bot_offline.py) bot ishlaydi.
try:
    import aiogram  # noqa: F401
except ImportError:
    import runpy
    import sys
    from pathlib import Path

    print("aiogram topilmadi -> bot_offline.py (stdlib rejimi) ishga tushirilyapti...")
    runpy.run_path(str(Path(__file__).resolve().with_name("bot_offline.py")), run_name="__main__")
    sys.exit(0)

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_settings
from database.database import Database
from handlers import start, registration, payment, admin
from middlewares.admin_middleware import AdminOnlyMiddleware
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)

    db = Database(settings.database_url)
    await db.init_models()
    logger.info("Database initialized (%s)", db.async_url)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Dependency injection
    dp["db"] = db
    dp["settings"] = settings

    # Middleware
    dp.update.outer_middleware(AdminOnlyMiddleware())

    # Routers (order matters)
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(payment.router)
    dp.include_router(admin.router)

    # Fallback router (must be last)
    fallback_router = Router()

    @fallback_router.message()
    async def fallback(message):
        text = (message.text or "").strip()
        if text.startswith("/"):
            await message.answer(
                "Kechirasiz, buyruq tushunilmadi. Buyurtmani boshlash uchun /start, bekor qilish uchun /cancel yuboring."
            )
            return
        await message.answer(
            "Kechirasiz, xabar tushunilmadi. Buyurtmani boshlash uchun /start, bekor qilish uchun /cancel yuboring."
        )

    dp.include_router(fallback_router)

    try:
        logger.info("Bot started")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.dispose()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
