from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class RegisteredOnly(BaseMiddleware):
    """Ro'yxatdan o'tmagan foydalanuvchini /start ga yo'naltiradi."""

    async def __call__(self, handler, event, data):
        user = data.get("user")
        if user is None or user.registered:
            return await handler(event, data)
        if isinstance(event, Message):
            if (event.text or "").startswith("/start") or (data.get("raw_state") or "").startswith("Reg:"):
                return await handler(event, data)
            await event.answer("Avval /start ni bosib ro'yxatdan o'ting.")
            return None
        if isinstance(event, CallbackQuery) and (event.data or "").split(":")[0] in ("role", "check_sub"):
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            await event.answer("Avval /start orqali ro'yxatdan o'ting.", show_alert=True)
        return None
