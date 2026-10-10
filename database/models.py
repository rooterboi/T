from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


def utcnow() -> datetime:
    """Naive UTC (SQLite bilan qulay)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="student")  # student | teacher | admin
    group_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)  # so'm
    vip_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ref_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    registered: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # bot bloklanmaganmi
    reminded_expiry: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def is_vip(self) -> bool:
        return bool(self.vip_until and self.vip_until > utcnow())

    @property
    def is_teacher(self) -> bool:
        return self.role in ("teacher", "admin")


class Setting(Base):
    """settings_prices: narxlar va limitlar (admin bot ichidan o'zgartiradi)."""
    __tablename__ = "settings_prices"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))


class ModuleStatus(Base):
    __tablename__ = "modules_status"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Promocode(Base):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(8))  # percent | amount
    value: Mapped[int] = mapped_column(Integer)
    max_uses: Mapped[int] = mapped_column(Integer, default=0)  # 0 = cheksiz
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PromoUse(Base):
    __tablename__ = "promo_uses"
    __table_args__ = (UniqueConstraint("promo_id", "tg_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    promo_id: Mapped[int] = mapped_column(ForeignKey("promocodes.id"))
    tg_id: Mapped[int] = mapped_column(BigInteger)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    provider: Mapped[str] = mapped_column(String(12))  # click | payme | stars | balance
    product: Mapped[str] = mapped_column(String(32))  # vip_month | vip_semester | topup
    amount_uzs: Mapped[int] = mapped_column(Integer)  # yakuniy narx (so'm)
    amount_paid: Mapped[int] = mapped_column(Integer)  # provider valyutasida (tiyin / stars)
    currency: Mapped[str] = mapped_column(String(4), default="UZS")
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | paid
    payload: Mapped[str] = mapped_column(String(64), unique=True)
    promo_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    charge_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class HandwritingFont(Base):
    __tablename__ = "handwriting_fonts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(64))
    file: Mapped[str] = mapped_column(String(64))  # fonts/ papkasidagi TTF
    size: Mapped[int] = mapped_column(Integer, default=44)
    jitter: Mapped[float] = mapped_column(Float, default=1.0)
    rotation: Mapped[float] = mapped_column(Float, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_code: Mapped[str] = mapped_column(String(32), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = dushanba
    start_time: Mapped[str] = mapped_column(String(5))  # HH:MM
    subject: Mapped[str] = mapped_column(String(96))
    room: Mapped[str] = mapped_column(String(32), default="")
    teacher_name: Mapped[str] = mapped_column(String(64), default="")


class ForcedChannel(Base):
    __tablename__ = "forced_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(128))
    link: Mapped[str] = mapped_column(String(256))


class UsageLog(Base):
    __tablename__ = "usage_log"
    __table_args__ = (UniqueConstraint("tg_id", "feature", "day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    feature: Mapped[str] = mapped_column(String(24))
    day: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    count: Mapped[int] = mapped_column(Integer, default=0)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_code: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Book(Base):
    __tablename__ = "library_books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(128))
    file_id: Mapped[str] = mapped_column(String(256))
