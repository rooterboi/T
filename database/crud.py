from datetime import timedelta

from aiogram.types import User as TgUser
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import (ForcedChannel, ModuleStatus, Setting, UsageLog, User, utcnow)


async def get_or_create_user(session: AsyncSession, tg: TgUser) -> User:
    user = await session.scalar(select(User).where(User.tg_id == tg.id))
    if user is None:
        user = User(tg_id=tg.id, full_name=tg.full_name, username=tg.username,
                    role="admin" if tg.id in config.admin_ids else "student")
        session.add(user)
        await session.commit()
    else:
        changed = False
        if user.username != tg.username:
            user.username, changed = tg.username, True
        if not user.is_active:
            user.is_active, changed = True, True
        if tg.id in config.admin_ids and user.role != "admin":
            user.role, changed = "admin", True
        if changed:
            await session.commit()
    return user


async def get_setting(session: AsyncSession, key: str) -> int:
    row = await session.get(Setting, key)
    return row.value if row else 0


async def set_setting(session: AsyncSession, key: str, value: int) -> None:
    row = await session.get(Setting, key)
    if row:
        row.value = value
        await session.commit()


async def module_enabled(session: AsyncSession, key: str) -> bool:
    row = await session.get(ModuleStatus, key)
    return True if row is None else row.enabled


async def toggle_module(session: AsyncSession, key: str) -> bool:
    row = await session.get(ModuleStatus, key)
    row.enabled = not row.enabled
    await session.commit()
    return row.enabled


async def list_channels(session: AsyncSession) -> list[ForcedChannel]:
    return list((await session.scalars(select(ForcedChannel))).all())


async def remove_channel(session: AsyncSession, channel_id: int) -> None:
    await session.execute(delete(ForcedChannel).where(ForcedChannel.id == channel_id))
    await session.commit()


async def usage_today(session: AsyncSession, tg_id: int, feature: str) -> int:
    day = utcnow().strftime("%Y-%m-%d")
    row = await session.scalar(select(UsageLog).where(
        UsageLog.tg_id == tg_id, UsageLog.feature == feature, UsageLog.day == day))
    return row.count if row else 0


async def add_usage(session: AsyncSession, tg_id: int, feature: str, delta: int = 1) -> None:
    day = utcnow().strftime("%Y-%m-%d")
    row = await session.scalar(select(UsageLog).where(
        UsageLog.tg_id == tg_id, UsageLog.feature == feature, UsageLog.day == day))
    if row is None:
        row = UsageLog(tg_id=tg_id, feature=feature, day=day, count=0)
        session.add(row)
    row.count = max(0, row.count + delta)
    await session.commit()


async def extend_vip(session: AsyncSession, user: User, days: int) -> None:
    base = user.vip_until if user.is_vip else utcnow()
    user.vip_until = base + timedelta(days=days)
    user.reminded_expiry = False
    await session.commit()


async def stats(session: AsyncSession) -> dict:
    from database.models import Payment

    now = utcnow()
    total = await session.scalar(select(func.count(User.id)))
    reg = await session.scalar(select(func.count(User.id)).where(User.registered.is_(True)))
    vip = await session.scalar(select(func.count(User.id)).where(User.vip_until > now))
    today = await session.scalar(select(func.count(User.id)).where(User.created_at >= now.replace(hour=0, minute=0, second=0)))
    revenue = await session.scalar(select(func.coalesce(func.sum(Payment.amount_uzs), 0)).where(
        Payment.status == "paid", Payment.provider != "balance", Payment.product != "balance"))
    return {"total": total, "registered": reg, "vip": vip, "today": today, "revenue": revenue}
