import re
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton as B
from sqlalchemy import distinct, select

from database.models import Assignment, Book, User
from keyboards.inline import grid
from keyboards.reply import BTN_LIBRARY, BTN_TASKS
from middlewares.module_guard import ModuleGuard
from states.states import Study

router = Router()
tasks = Router()
tasks.message.middleware(ModuleGuard("tasks"))
library = Router()
library.message.middleware(ModuleGuard("library"))
library.callback_query.middleware(ModuleGuard("library"))


# ---------- TOPSHIRIQLAR ----------
@tasks.message(F.text == BTN_TASKS)
async def tasks_list(message: Message, state: FSMContext, session, user: User):
    rows = (await session.scalars(select(Assignment).where(Assignment.group_code == user.group_code)
                                  .order_by(Assignment.id.desc()).limit(10))).all()
    for a in rows:
        dl = f"\n⏰ Muddat: <b>{a.deadline:%d.%m.%Y %H:%M}</b>" if a.deadline else ""
        text = f"📝 <b>{a.title}</b>\n{a.description}{dl}"
        if a.file_id:
            await message.answer_document(a.file_id, caption=text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")
    if not rows:
        await message.answer("Hozircha topshiriqlar yo'q.")
    if user.is_teacher:
        await state.set_state(Study.task_add)
        await message.answer("➕ Yangi topshiriq: <code>Sarlavha | Tavsif | DD.MM.YYYY HH:MM</code> (muddat ixtiyoriy). "
                             "Fayl biriktirish uchun hujjatni shu matn bilan caption sifatida yuboring. "
                             "Bekor qilish: menyudan boshqa tugma.", parse_mode="HTML")


@tasks.message(Study.task_add, F.text | F.document)
async def task_save(message: Message, state: FSMContext, session, user: User):
    parts = [p.strip() for p in (message.text or message.caption or "").split("|")] + ["", ""]
    if not parts[0]:
        await message.answer("Sarlavha kerak.")
        return
    deadline = None
    if parts[2]:
        try:
            deadline = datetime.strptime(parts[2], "%d.%m.%Y %H:%M")
        except ValueError:
            await message.answer("Muddat formati: DD.MM.YYYY HH:MM")
            return
    session.add(Assignment(group_code=user.group_code, title=parts[0][:128], description=parts[1], deadline=deadline,
                           file_id=message.document.file_id if message.document else None))
    await session.commit()
    await state.clear()
    await message.answer("✅ Topshiriq qo'shildi. Guruh a'zolari «📝 Topshiriqlar» da ko'radi.")


# ---------- KUTUBXONA ----------
@library.message(F.text == BTN_LIBRARY)
async def lib_menu(message: Message, state: FSMContext, session, user: User):
    subjects = (await session.scalars(select(distinct(Book.subject)))).all()
    if subjects:
        await message.answer("📖 Fanni tanlang:", reply_markup=grid([B(text=s, callback_data=f"lib:{s[:40]}") for s in subjects], 2))
    else:
        await message.answer("Kutubxona hozircha bo'sh.")
    if user.is_teacher:
        await state.set_state(Study.book_add)
        await message.answer("➕ Kitob qo'shish: hujjatni caption bilan yuboring: <code>Fan | Kitob nomi</code>", parse_mode="HTML")


@library.callback_query(F.data.startswith("lib:"))
async def lib_subject(call: CallbackQuery, session):
    books = (await session.scalars(select(Book).where(Book.subject == call.data[4:]).limit(20))).all()
    for b in books:
        await call.message.answer_document(b.file_id, caption=f"📘 {b.title}")
    await call.answer()


@library.message(Study.book_add, F.document)
async def lib_add(message: Message, state: FSMContext, session):
    parts = [p.strip() for p in (message.caption or "").split("|")]
    if len(parts) < 2 or not all(parts[:2]):
        await message.answer("Caption: <code>Fan | Kitob nomi</code>", parse_mode="HTML")
        return
    session.add(Book(subject=parts[0][:40], title=parts[1][:128], file_id=message.document.file_id))
    await session.commit()
    await message.answer("✅ Kitob qo'shildi. Yana yuborishingiz mumkin yoki menyudan boshqa tugmani bosing.")


router.include_router(tasks)
router.include_router(library)
