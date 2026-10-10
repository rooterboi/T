from aiogram import BaseMiddleware

from database import crud
from database.base import SessionMaker


class DbMiddleware(BaseMiddleware):
    """Har bir update uchun session va user obyektini beradi; banlanganlarni to'xtatadi."""

    async def __call__(self, handler, event, data):
        async with SessionMaker() as session:
            data["session"] = session
            tg = data.get("event_from_user")
            if tg is None or tg.is_bot:
                return await handler(event, data)
            user = await crud.get_or_create_user(session, tg)
            if user.is_banned:
                return None
            data["user"] = user
            return await handler(event, data)
