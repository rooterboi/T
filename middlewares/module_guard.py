from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

from config import config
from database import crud


class ModuleGuard(BaseMiddleware):
    """Router darajasida (inner) ishlaydi: admin o'chirib qo'ygan bo'lim handlerlarini to'xtatadi."""

    def __init__(self, module_key: str):
        self.key = module_key

    async def __call__(self, handler, event, data):
        user = data.get("user")
        if user and user.tg_id in config.admin_ids:
            return await handler(event, data)
        if await crud.module_enabled(data["session"], self.key):
            return await handler(event, data)
        text = "🚧 Bu bo'lim vaqtincha o'chirilgan. Keyinroq urinib ko'ring."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return None
