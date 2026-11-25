import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN must be set in Railway Variables (get the token from @BotFather)."
    )

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        "Assalomu alaykum! Men 5-Million-Promter-Bot. Menga matn yuboring."
    )


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(
        "Mavjud buyruqlar:\n"
        "/start - botni ishga tushirish\n"
        "/help - yordam va buyruqlar ro'yxati\n\n"
        "Istalgan matn yuborsangiz, bot uni qaytarib yuboradi."
    )


@router.message(F.text)
async def handle_text(message: Message) -> None:
    # Placeholder logic: replace with real prompt handling.
    await message.answer(message.text, parse_mode=None)


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
