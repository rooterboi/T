from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import PromoUse, Promocode, utcnow


async def validate_promo(session: AsyncSession, code: str, tg_id: int) -> tuple[Promocode | None, str]:
    promo = await session.scalar(select(Promocode).where(Promocode.code == code.strip().upper()))
    if promo is None or not promo.active:
        return None, "Bunday promokod topilmadi."
    if promo.expires_at and promo.expires_at < utcnow():
        return None, "Promokod muddati tugagan."
    if promo.max_uses and promo.used_count >= promo.max_uses:
        return None, "Promokod limiti tugagan."
    used = await session.scalar(select(PromoUse).where(PromoUse.promo_id == promo.id, PromoUse.tg_id == tg_id))
    if used:
        return None, "Siz bu promokoddan foydalanib bo'lgansiz."
    return promo, ""


def apply_promo(price: int, promo: Promocode | None) -> int:
    if promo is None:
        return price
    if promo.kind == "percent":
        return max(0, price - price * promo.value // 100)
    return max(0, price - promo.value)


async def consume_promo(session: AsyncSession, code: str | None, tg_id: int) -> None:
    if not code:
        return
    promo = await session.scalar(select(Promocode).where(Promocode.code == code))
    if promo is None:
        return
    session.add(PromoUse(promo_id=promo.id, tg_id=tg_id))
    promo.used_count += 1
    await session.commit()
