from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import config
from keyboards.inline import sub_kb
from services.subscription import missing_channels


class ForcedSubMiddleware(BaseMiddleware):
    """Majburiy obuna: a'zo bo'lmaganlarga kanal ro'yxati chiqadi, handler ishlamaydi."""

    async def __call__(self, handler, event, data):
        user = data.get("user")
        if user is None or user.tg_id in config.admin_ids:
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)
        missing = await missing_channels(data["bot"], data["session"], user.tg_id)
        if not missing:
            return await handler(event, data)
        text = "📢 Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling, so'ng «Tekshirish» ni bosing:"
        if isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.answer(text, reply_markup=sub_kb(missing))
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=sub_kb(missing))
        return None
