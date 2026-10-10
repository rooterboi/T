from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from config import config
from database.models import User
from keyboards.inline import role_kb
from keyboards.reply import main_menu
from services.subscription import missing_channels
from keyboards.inline import sub_kb
from states.states import Reg

router = Router()


def menu_for(user: User):
    return main_menu(user.tg_id in config.admin_ids)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, session, user: User):
    await state.clear()
    if command.args and command.args.startswith("ref_") and not user.registered and user.referrer_id is None:
        try:
            ref_id = int(command.args[4:])
        except ValueError:
            ref_id = 0
        if ref_id and ref_id != user.tg_id and await session.scalar(select(User.id).where(User.tg_id == ref_id)):
            user.referrer_id = ref_id
            await session.commit()
    if user.registered:
        await message.answer(f"Xush kelibsiz, {user.full_name}! 👋", reply_markup=menu_for(user))
        return
    await state.set_state(Reg.name)
    await message.answer("👋 Assalomu alaykum! Ro'yxatdan o'tamiz.\n\nIsm-familiyangizni yozing:")


@router.message(Reg.name, F.text)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()[:100]
    if len(name) < 3:
        await message.answer("Iltimos, ism-familiyangizni to'liq yozing.")
        return
    await state.update_data(name=name)
    await state.set_state(Reg.role)
    await message.answer("Siz kimsiz?", reply_markup=role_kb())


@router.callback_query(Reg.role, F.data.startswith("role:"))
async def reg_role(call: CallbackQuery, state: FSMContext):
    role = call.data.split(":")[1]
    await state.update_data(role=role)
    await state.set_state(Reg.group)
    hint = ("Guruh kodini o'ylab toping (masalan: IT-21). Talabalaringiz shu kodni kiritadi:" if role == "teacher"
            else "Guruh kodingizni kiriting (o'qituvchi/sardor bergan kod, masalan: IT-21):")
    await call.message.edit_text(hint)
    await call.answer()


@router.message(Reg.group, F.text)
async def reg_group(message: Message, state: FSMContext, session, user: User):
    data = await state.get_data()
    user.full_name = data["name"]
    user.role = "admin" if user.tg_id in config.admin_ids else data.get("role", "student")
    user.group_code = message.text.strip().upper()[:32]
    user.registered = True
    await session.commit()
    await state.clear()
    await message.answer("✅ Ro'yxatdan o'tdingiz! Asosiy menyu:", reply_markup=menu_for(user))


@router.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery, bot: Bot, session, user: User):
    missing = await missing_channels(bot, session, user.tg_id)
    if missing:
        await call.answer("Hali hamma kanallarga a'zo bo'lmadingiz ❌", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=sub_kb(missing))
        return
    await call.message.delete()
    await call.message.answer("✅ Rahmat! Davom etamiz. /start ni bosing.", reply_markup=menu_for(user))
    await call.answer()
