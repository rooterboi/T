from aiogram import BaseMiddleware
from aiogram.types import Message

from keyboards.reply import MENU_BUTTONS


class MenuResetMiddleware(BaseMiddleware):
    """Menyu tugmasi bosilsa, joriy FSM holatini bekor qiladi (holatda qolib ketmaslik uchun)."""

    async def __call__(self, handler, event: Message, data):
        if event.text in MENU_BUTTONS and data.get("state"):
            await data["state"].clear()
            data["raw_state"] = None
        return await handler(event, data)
