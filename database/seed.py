from sqlalchemy.ext.asyncio import AsyncSession

from database.models import HandwritingFont, ModuleStatus, Setting

DEFAULT_SETTINGS = {
    # narxlar (so'm)
    "vip_month_price": (49_000, "💎 VIP 1 oylik narxi (so'm)"),
    "vip_semester_price": (199_000, "💎 VIP 1 semestrlik narxi (so'm)"),
    "vip_month_days": (30, "VIP 1 oylik — kunlar soni"),
    "vip_semester_days": (150, "VIP semestrlik — kunlar soni"),
    "hw_price": (5_000, "✍️ Husnixat narxi (bir marta, so'm)"),
    "slide_price": (7_000, "📊 Slayd generatsiyasi narxi (so'm)"),
    "ai_price": (2_000, "🤖 Spargalka / Audio konspekt narxi (so'm)"),
    # bepul foydalanuvchi limitlari
    "free_hw_daily": (1, "Bepul: kunlik husnixat soni"),
    "free_slide_daily": (1, "Bepul: kunlik slayd soni"),
    "free_ai_daily": (3, "Bepul: kunlik AI so'rovlar soni"),
    "free_hw_max_pages": (3, "Bepul: husnixat max varoq"),
    "vip_hw_max_pages": (30, "VIP: husnixat max varoq"),
    # monetizatsiya
    "cashback_percent": (3, "Keshbek foizi (VIP xariddan)"),
    "ref_bonus_days": (3, "Referal: taklif qilgan odamga VIP kun"),
    "ref_bonus_money": (2_000, "Referal: taklif qilgan odamga balans (so'm)"),
    "stars_rate": (250, "1 ⭐ Stars = necha so'm (kurs)"),
}

DEFAULT_MODULES = {
    "handwriting": "✍️ Husnixat",
    "slides": "📊 AI Slayd",
    "ai_tools": "📚 Spargalka / 🎙 Audio konspekt",
    "schedule": "🗓 Dars jadvali",
    "tasks": "📝 Topshiriqlar",
    "library": "📖 Kutubxona",
    "payments": "💎 VIP / To'lov",
    "referral": "🎁 Referal",
}


async def seed(session: AsyncSession) -> None:
    from services.handwriting import STYLES

    for key, (value, title) in DEFAULT_SETTINGS.items():
        if await session.get(Setting, key) is None:
            session.add(Setting(key=key, value=value, title=title))
    for key, title in DEFAULT_MODULES.items():
        if await session.get(ModuleStatus, key) is None:
            session.add(ModuleStatus(key=key, title=title, enabled=True))
    from sqlalchemy import select

    existing = set((await session.scalars(select(HandwritingFont.key))).all())
    for s in STYLES:
        if s.key not in existing:
            session.add(HandwritingFont(key=s.key, title=s.title, file=s.font, size=s.size,
                                        jitter=s.jitter, rotation=s.rotation))
    await session.commit()
