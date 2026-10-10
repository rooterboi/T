"""Mahsulotlar, narx hisoblash va to'lovni yakunlash (fulfill)."""
import math
import uuid

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database.models import Payment, User
from services.promo import consume_promo

VIP_PRODUCTS = {"vip_month": ("vip_month_price", "vip_month_days", "💎 VIP — 1 oy"),
                "vip_semester": ("vip_semester_price", "vip_semester_days", "💎 VIP — 1 semestr")}


async def product_price(session: AsyncSession, product: str, topup_amount: int = 0) -> int:
    if product in VIP_PRODUCTS:
        return await crud.get_setting(session, VIP_PRODUCTS[product][0])
    return topup_amount


def product_title(product: str) -> str:
    return VIP_PRODUCTS[product][2] if product in VIP_PRODUCTS else "➕ Balansni to'ldirish"


async def create_payment(session: AsyncSession, user: User, provider: str, product: str, amount_uzs: int,
                         promo_code: str | None) -> tuple[Payment, int]:
    """Pending to'lov yaratadi. Qaytaradi: (payment, provider valyutasidagi summa)."""
    if provider == "stars":
        rate = max(1, await crud.get_setting(session, "stars_rate"))
        paid, cur = max(1, math.ceil(amount_uzs / rate)), "XTR"
    else:
        paid, cur = amount_uzs * 100, "UZS"  # tiyin
    pay = Payment(tg_id=user.tg_id, provider=provider, product=product, amount_uzs=amount_uzs,
                  amount_paid=paid, currency=cur, payload=f"{product}:{uuid.uuid4().hex[:16]}", promo_code=promo_code)
    session.add(pay)
    await session.commit()
    return pay, paid


async def fulfill(session: AsyncSession, bot: Bot, pay: Payment, charge_id: str | None = None) -> str:
    """To'lovni yakunlaydi: VIP/balans, keshbek, promokod, referal bonusi. Idempotent."""
    if pay.status == "paid":
        return "allaqachon"
    user = await session.scalar(select(User).where(User.tg_id == pay.tg_id))
    pay.status, pay.charge_id = "paid", charge_id
    msg = ""
    if pay.product in VIP_PRODUCTS:
        days = await crud.get_setting(session, VIP_PRODUCTS[pay.product][1])
        await crud.extend_vip(session, user, days)
        cashback = pay.amount_uzs * await crud.get_setting(session, "cashback_percent") // 100
        if cashback and pay.provider != "balance":
            user.balance += cashback
        msg = (f"✅ VIP faollashdi: {user.vip_until:%d.%m.%Y} gacha."
               + (f"\n🎁 Keshbek: +{cashback:,} so'm balansga." if cashback and pay.provider != "balance" else ""))
    else:
        user.balance += pay.amount_uzs
        msg = f"✅ Balans {pay.amount_uzs:,} so'mga to'ldirildi. Hozirgi balans: {user.balance:,} so'm."
    await consume_promo(session, pay.promo_code, user.tg_id)
    await session.commit()
    await _reward_referrer(session, bot, user)
    return msg


async def _reward_referrer(session: AsyncSession, bot: Bot, user: User) -> None:
    if not user.referrer_id or user.ref_rewarded:
        return
    ref = await session.scalar(select(User).where(User.tg_id == user.referrer_id))
    user.ref_rewarded = True
    if ref:
        days = await crud.get_setting(session, "ref_bonus_days")
        money = await crud.get_setting(session, "ref_bonus_money")
        if days:
            await crud.extend_vip(session, ref, days)
        ref.balance += money
        try:
            await bot.send_message(ref.tg_id, f"🎉 Taklif qilgan do'stingiz xarid qildi! Bonus: +{days} kun VIP, +{money:,} so'm.")
        except Exception:
            pass
    await session.commit()
