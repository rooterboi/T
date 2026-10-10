"""Limit va narx nazorati: VIP -> cheksiz; bepul -> kunlik limit; keyin balansdan to'lov."""
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database.models import User

LIMIT_KEY = {"handwriting": "free_hw_daily", "slide": "free_slide_daily", "ai": "free_ai_daily"}
PRICE_KEY = {"handwriting": "hw_price", "slide": "slide_price", "ai": "ai_price"}


async def try_consume(session: AsyncSession, user: User, feature: str) -> tuple[bool, str, int]:
    """Qaytaradi: (ruxsat, rejim: vip|free|balance|denied, narx)."""
    if user.is_vip:
        return True, "vip", 0
    limit = await crud.get_setting(session, LIMIT_KEY[feature])
    if await crud.usage_today(session, user.tg_id, feature) < limit:
        await crud.add_usage(session, user.tg_id, feature)
        return True, "free", 0
    price = await crud.get_setting(session, PRICE_KEY[feature])
    if price <= 0:
        return True, "free", 0
    if user.balance >= price:
        user.balance -= price
        await session.commit()
        return True, "balance", price
    return False, "denied", price


async def refund(session: AsyncSession, user: User, feature: str, mode: str, price: int) -> None:
    if mode == "free":
        await crud.add_usage(session, user.tg_id, feature, -1)
    elif mode == "balance":
        user.balance += price
        await session.commit()


DENIED_TEXT = ("⚠️ Bepul kunlik limit tugadi.\nBu xizmat narxi: <b>{price:,} so'm</b>, balansingiz: <b>{bal:,} so'm</b>.\n"
               "Balansni to'ldiring yoki 💎 VIP oling (cheksiz foydalanish).")
