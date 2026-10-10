import re
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton as B
from sqlalchemy import select

from database.models import Schedule, User
from keyboards.inline import kb
from keyboards.reply import BTN_SCHEDULE
from middlewares.module_guard import ModuleGuard
from services.scheduler import TZ
from states.states import Study

router = Router()
router.message.middleware(ModuleGuard("schedule"))
router.callback_query.middleware(ModuleGuard("schedule"))

DAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


def _menu(user: User):
    rows = [[B(text="📅 Bugun", callback_data="sch:today"), B(text="📅 Ertaga", callback_data="sch:tomorrow")],
            [B(text="🗓 Haftalik", callback_data="sch:week")]]
    if user.is_teacher:
        rows.append([B(text="➕ Dars qo'shish", callback_data="sch:add"), B(text="🗑 O'chirish", callback_data="sch:del")])
    return kb(rows)


@router.message(F.text == BTN_SCHEDULE)
async def schedule_menu(message: Message, user: User):
    if not user.group_code:
        await message.answer("Guruh kodingiz yo'q.")
        return
    await message.answer(f"🗓 Guruh: <b>{user.group_code}</b>", parse_mode="HTML", reply_markup=_menu(user))


async def _lessons(session, group: str, weekday: int | None = None):
    q = select(Schedule).where(Schedule.group_code == group)
    if weekday is not None:
        q = q.where(Schedule.weekday == weekday)
    return (await session.scalars(q.order_by(Schedule.weekday, Schedule.start_time))).all()


def _fmt(l: Schedule) -> str:
    return f"🕒 {l.start_time} — <b>{l.subject}</b>" + (f" ({l.room})" if l.room else "") + (f" • {l.teacher_name}" if l.teacher_name else "")


@router.callback_query(F.data.in_({"sch:today", "sch:tomorrow"}))
async def show_day(call: CallbackQuery, session, user: User):
    wd = datetime.now(TZ).weekday()
    if call.data == "sch:tomorrow":
        wd = (wd + 1) % 7
    rows = await _lessons(session, user.group_code, wd)
    body = "\n".join(_fmt(r) for r in rows) or "Darslar yo'q 🎉"
    await call.message.answer(f"📅 <b>{DAYS[wd]}</b>\n{body}", parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "sch:week")
async def show_week(call: CallbackQuery, session, user: User):
    rows = await _lessons(session, user.group_code)
    out = []
    for wd in range(7):
        day = [r for r in rows if r.weekday == wd]
        if day:
            out.append(f"<b>{DAYS[wd]}</b>\n" + "\n".join(_fmt(r) for r in day))
    await call.message.answer("\n\n".join(out) or "Jadval hali kiritilmagan.", parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "sch:add")
async def add_start(call: CallbackQuery, state: FSMContext, user: User):
    if not user.is_teacher:
        return await call.answer()
    await state.set_state(Study.schedule_add)
    await call.message.answer("Darslarni har qatorga bittadan yozing:\n<code>kun HH:MM Fan | xona | o'qituvchi</code>\n"
                              "Masalan:\n<code>Dushanba 09:00 Matematika | 305 | Karimov A.</code>\n"
                              "<code>Juma 14:30 Fizika</code>", parse_mode="HTML")
    await call.answer()


@router.message(Study.schedule_add, F.text)
async def add_save(message: Message, state: FSMContext, session, user: User):
    added, bad = 0, []
    for line in message.text.splitlines():
        m = re.match(r"^\s*(\S+)\s+(\d{1,2}):(\d{2})\s+(.+)$", line)
        wd = next((i for i, d in enumerate(DAYS) if m and d.lower().startswith(m.group(1).lower()[:3])), None)
        if not m or wd is None:
            bad.append(line)
            continue
        parts = [p.strip() for p in m.group(4).split("|")] + ["", ""]
        session.add(Schedule(group_code=user.group_code, weekday=wd, start_time=f"{int(m.group(2)):02d}:{m.group(3)}",
                             subject=parts[0][:96], room=parts[1][:32], teacher_name=parts[2][:64]))
        added += 1
    await session.commit()
    await state.clear()
    await message.answer(f"✅ Qo'shildi: {added}" + (f"\n❌ O'qib bo'lmadi:\n" + "\n".join(bad) if bad else ""))


@router.callback_query(F.data == "sch:del")
async def del_list(call: CallbackQuery, session, user: User):
    if not user.is_teacher:
        return await call.answer()
    rows = await _lessons(session, user.group_code)
    buttons = [[B(text=f"🗑 {DAYS[r.weekday][:3]} {r.start_time} {r.subject}", callback_data=f"sch:rm:{r.id}")] for r in rows[:40]]
    await call.message.answer("O'chirish uchun tanlang:" if buttons else "Jadval bo'sh.", reply_markup=kb(buttons) if buttons else None)
    await call.answer()


@router.callback_query(F.data.startswith("sch:rm:"))
async def del_one(call: CallbackQuery, session, user: User):
    row = await session.get(Schedule, int(call.data.split(":")[2]))
    if row and user.is_teacher and row.group_code == user.group_code:
        await session.delete(row)
        await session.commit()
        await call.message.delete()
    await call.answer("O'chirildi")
