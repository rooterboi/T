import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database.base import init_db
from handlers import admin, ai_tools, handwriting, payments, profile, schedule, start, tasks_library
from middlewares.db import DbMiddleware
from middlewares.forced_sub import ForcedSubMiddleware
from middlewares.menu_reset import MenuResetMiddleware
from middlewares.registered import RegisteredOnly
from middlewares.throttle import ThrottleMiddleware
from services.handwriting import ensure_previews
from services.scheduler import setup_scheduler


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.bot_token:
        raise SystemExit("BOT_TOKEN topilmadi (.env faylni tekshiring).")

    await init_db()
    await asyncio.to_thread(ensure_previews)

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())  # ko'p instansiya kerak bo'lsa RedisStorage ga o'ting

    # Middleware tartibi: Throttle -> DB(user) -> [Menu reset] -> Ro'yxatdan o'tganlik -> Majburiy obuna
    for observer in (dp.message, dp.callback_query, dp.pre_checkout_query):
        observer.outer_middleware(ThrottleMiddleware())
        observer.outer_middleware(DbMiddleware())
    dp.message.outer_middleware(MenuResetMiddleware())
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(RegisteredOnly())
        observer.outer_middleware(ForcedSubMiddleware())

    dp.include_routers(admin.router, payments.router, start.router, handwriting.router, ai_tools.router,
                       schedule.router, tasks_library.router, profile.router, profile.ref_router)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi: @%s", (await bot.me()).username)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
