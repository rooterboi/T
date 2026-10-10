from datetime import timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from config import config
from database.base import SessionMaker
from database.models import Schedule, User, utcnow

TZ = ZoneInfo(config.timezone)


async def lesson_reminders(bot: Bot) -> None:
    """Har daqiqada: 15 daqiqadan keyin boshlanadigan darslarni guruhga eslatadi."""
    from datetime import datetime

    target = datetime.now(TZ) + timedelta(minutes=15)
    async with SessionMaker() as session:
        lessons = (await session.scalars(select(Schedule).where(
            Schedule.weekday == target.weekday(), Schedule.start_time == target.strftime("%H:%M")))).all()
        for lesson in lessons:
            users = (await session.scalars(select(User).where(
                User.group_code == lesson.group_code, User.registered.is_(True), User.is_active.is_(True)))).all()
            text = (f"⏰ 15 daqiqadan keyin dars!\n📚 <b>{lesson.subject}</b>\n🕒 {lesson.start_time}"
                    + (f"\n🚪 Xona: {lesson.room}" if lesson.room else "")
                    + (f"\n👨‍🏫 {lesson.teacher_name}" if lesson.teacher_name else ""))
            for u in users:
                try:
                    await bot.send_message(u.tg_id, text, parse_mode="HTML")
                except Exception:
                    pass


async def vip_expiry_notices(bot: Bot) -> None:
    """Kuniga bir marta: VIP tugashiga 3 kun yoki kam qolganlarni ogohlantiradi."""
    now = utcnow()
    async with SessionMaker() as session:
        users = (await session.scalars(select(User).where(
            User.vip_until > now, User.vip_until <= now + timedelta(days=3),
            User.reminded_expiry.is_(False)))).all()
        for u in users:
            try:
                await bot.send_message(u.tg_id, f"⏳ VIP obunangiz {u.vip_until:%d.%m.%Y} da tugaydi. "
                                                "Uzilishsiz foydalanish uchun «💎 VIP / To'lov» bo'limidan uzaytiring.")
            except Exception:
                pass
            u.reminded_expiry = True
        await session.commit()


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    sch = AsyncIOScheduler(timezone=TZ)
    sch.add_job(lesson_reminders, "cron", minute="*", args=[bot], max_instances=1, coalesce=True)
    sch.add_job(vip_expiry_notices, "cron", hour=10, minute=0, args=[bot])
    return sch
