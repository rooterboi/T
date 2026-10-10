import logging
import shutil

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, InputMediaPhoto, Message
from aiogram.types import InlineKeyboardButton as B
from aiogram.utils.media_group import MediaGroupBuilder

from database import crud
from database.models import User
from keyboards.inline import grid, topup_hint_kb
from keyboards.reply import BTN_HW
from middlewares.module_guard import ModuleGuard
from services import handwriting as hw
from services.access import DENIED_TEXT, refund, try_consume
from states.states import HW

log = logging.getLogger(__name__)
router = Router()
router.message.middleware(ModuleGuard("handwriting"))
router.callback_query.middleware(ModuleGuard("handwriting"))

MAX_CHARS = 20_000
_preview_ids: dict[str, str] = {}  # style_key -> telegram file_id (keshlash)


@router.message(F.text == BTN_HW)
async def hw_start(message: Message, state: FSMContext):
    await state.set_state(HW.text)
    await message.answer("✍️ <b>Husnixat generatori</b>\n\nKo'chiriladigan matnni yuboring "
                         f"(maks. {MAX_CHARS:,} belgi):", parse_mode="HTML")


@router.message(HW.text, F.text)
async def hw_text(message: Message, state: FSMContext, session, user: User):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Matn juda qisqa.")
        return
    if len(text) > MAX_CHARS:
        await message.answer(f"Matn juda uzun ({len(text):,} belgi). {MAX_CHARS:,} dan oshmasin.")
        return
    max_pages = await crud.get_setting(session, "vip_hw_max_pages" if user.is_vip else "free_hw_max_pages")
    await state.update_data(text=text, max_pages=max_pages)
    await state.set_state(HW.pages)
    opts = [n for n in (1, 2, 3, 5, 10, 15, 20, 30) if n <= max_pages] or [1]
    await message.answer(
        f"📄 Necha varoq bo'lsin? (maks. {max_pages})\nTugmani bosing yoki raqam yozing.",
        reply_markup=grid([B(text=str(n), callback_data=f"hwp:{n}") for n in opts], 4))


async def _show_styles(target: Message, bot: Bot, state: FSMContext, pages: int):
    await state.update_data(pages=pages)
    await state.set_state(HW.style)
    previews = hw.ensure_previews()
    keys = [s.key for s in hw.STYLES]
    for chunk_start in range(0, len(keys), 10):
        chunk = keys[chunk_start:chunk_start + 10]
        mg = MediaGroupBuilder()
        for k in chunk:
            n = keys.index(k) + 1
            media = _preview_ids.get(k) or FSInputFile(previews[k])
            mg.add_photo(media=media, caption=f"{n}. {hw.STYLE_MAP[k].title}")
        sent = await bot.send_media_group(target.chat.id, mg.build())
        for k, m in zip(chunk, sent):
            _preview_ids[k] = m.photo[-1].file_id
    buttons = [B(text=f"{i}. {s.title}", callback_data=f"hws:{s.key}") for i, s in enumerate(hw.STYLES, 1)]
    await target.answer("🎨 Yoqqan husnixatni tanlang:", reply_markup=grid(buttons, 2))


@router.callback_query(HW.pages, F.data.startswith("hwp:"))
async def hw_pages_cb(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    await call.message.edit_reply_markup()
    await _show_styles(call.message, bot, state, int(call.data.split(":")[1]))


@router.message(HW.pages, F.text.regexp(r"^\d{1,2}$"))
async def hw_pages_msg(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    n = int(message.text)
    if not 1 <= n <= data["max_pages"]:
        await message.answer(f"1 dan {data['max_pages']} gacha raqam kiriting. (Ko'proq uchun 💎 VIP)")
        return
    await _show_styles(message, bot, state, n)


@router.callback_query(HW.style, F.data.startswith("hws:"))
async def hw_generate(call: CallbackQuery, state: FSMContext, bot: Bot, session, user: User):
    key = call.data.split(":")[1]
    if key not in hw.STYLE_MAP:
        await call.answer("Noma'lum variant", show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    await call.answer()
    ok, mode, price = await try_consume(session, user, "handwriting")
    if not ok:
        await call.message.answer(DENIED_TEXT.format(price=price, bal=user.balance), parse_mode="HTML",
                                  reply_markup=topup_hint_kb())
        return
    status = await call.message.answer("⏳ Yozilmoqda, biroz kuting...")
    jpgs = []
    try:
        jpgs, pdf = await hw.generate(data["text"], key, data["pages"])
        for i in range(0, len(jpgs), 10):
            part = jpgs[i:i + 10]
            if len(part) == 1:
                await call.message.answer_photo(FSInputFile(part[0]))
            else:
                mg = MediaGroupBuilder()
                for p in part:
                    mg.add_photo(media=FSInputFile(p))
                await bot.send_media_group(call.message.chat.id, mg.build())
        await call.message.answer_document(FSInputFile(pdf), caption=f"📄 PDF • {len(jpgs)} varoq • {hw.STYLE_MAP[key].title}")
        note = f"\n💰 Balansdan {price:,} so'm yechildi." if mode == "balance" else ""
        if len(jpgs) > data["pages"]:
            note += f"\nℹ️ Matn sig'magani uchun varoqlar {len(jpgs)} taga ko'paydi."
        if note:
            await call.message.answer(note.strip())
    except Exception:
        log.exception("Husnixat xatosi")
        await refund(session, user, "handwriting", mode, price)
        await call.message.answer("❌ Xatolik yuz berdi. Limitingiz qaytarildi, qayta urinib ko'ring.")
    finally:
        await status.delete()
        if jpgs:
            hw.cleanup(jpgs)
