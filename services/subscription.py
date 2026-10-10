from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud


async def missing_channels(bot: Bot, session: AsyncSession, tg_id: int) -> list:
    missing = []
    for ch in await crud.list_channels(session):
        try:
            member = await bot.get_chat_member(ch.chat_id, tg_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:  # bot kanalda admin emas / kanal topilmadi — o'tkazib yuboramiz
            continue
    return missing
