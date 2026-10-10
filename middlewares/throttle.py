import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self, delay: float = 0.6):
        self.delay, self.last = delay, {}

    async def __call__(self, handler, event, data):
        tg = data.get("event_from_user")
        if tg:
            now = time.monotonic()
            if now - self.last.get(tg.id, 0) < self.delay:
                if isinstance(event, CallbackQuery):
                    await event.answer()
                return None
            self.last[tg.id] = now
            if len(self.last) > 50_000:
                self.last.clear()
        return await handler(event, data)
