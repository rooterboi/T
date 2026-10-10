import io
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from database.models import User
from keyboards.inline import topup_hint_kb
from keyboards.reply import BTN_SLIDE, BTN_SPARG, BTN_VOICE
from middlewares.module_guard import ModuleGuard
from services import ai
from services.access import DENIED_TEXT, refund, try_consume
from services.slides import build_pptx
from states.states import AI

log = logging.getLogger(__name__)
router = Router()
slides_router = Router()
slides_router.message.middleware(ModuleGuard("slides"))
tools_router = Router()
tools_router.message.middleware(ModuleGuard("ai_tools"))


async def _split_send(message: Message, text: str):
    for i in range(0, len(text), 4000):
        await message.answer(text[i:i + 4000])


async def _gate(message: Message, session, user: User, feature: str):
    ok, mode, price = await try_consume(session, user, feature)
    if not ok:
        await message.answer(DENIED_TEXT.format(price=price, bal=user.balance), parse_mode="HTML",
                             reply_markup=topup_hint_kb())
    return ok, mode, price


# ---------- AI SLAYD ----------
@slides_router.message(F.text == BTN_SLIDE)
async def slide_start(message: Message, state: FSMContext):
    await state.set_state(AI.slide_topic)
    await message.answer("📊 Slayd mavzusini yozing (masalan: «Sun'iy intellekt asoslari»):")


@slides_router.message(AI.slide_topic, F.text)
async def slide_make(message: Message, state: FSMContext, session, user: User):
    await state.clear()
    ok, mode, price = await _gate(message, session, user, "slide")
    if not ok:
        return
    status = await message.answer("⏳ Slayd tayyorlanmoqda...")
    try:
        outline = await ai.slide_outline(message.text.strip()[:200])
        path = await build_pptx(outline)
        await message.answer_document(FSInputFile(path, filename=f"{outline.get('title', 'slayd')[:40]}.pptx"),
                                      caption="✅ Tayyor PowerPoint fayl")
        path.unlink(missing_ok=True)
    except ai.AIError as e:
        await refund(session, user, "slide", mode, price)
        await message.answer(f"❌ {e}")
    except Exception:
        log.exception("Slayd xatosi")
        await refund(session, user, "slide", mode, price)
        await message.answer("❌ Xatolik yuz berdi, limit qaytarildi.")
    finally:
        await status.delete()


# ---------- SPARGALKA ----------
@tools_router.message(F.text == BTN_SPARG)
async def sparg_start(message: Message, state: FSMContext):
    await state.set_state(AI.sparg_text)
    await message.answer("📚 Darslik/ma'ruza matnini yuboring — imtihon uchun ixcham savol-javob (shporga) tayyorlayman:")


@tools_router.message(AI.sparg_text, F.text)
async def sparg_make(message: Message, state: FSMContext, session, user: User):
    await state.clear()
    ok, mode, price = await _gate(message, session, user, "ai")
    if not ok:
        return
    try:
        res = await ai.ask("Quyidagi matndan imtihonga tayyorlanish uchun ixcham SAVOL-JAVOB varaqasi (spargalka) tuz. "
                           "10-20 ta qisqa savol va 1-2 gaplik javob. O'zbek tilida, oddiy matn formatida:\n\n"
                           + message.text[:15000])
        await _split_send(message, res)
    except ai.AIError as e:
        await refund(session, user, "ai", mode, price)
        await message.answer(f"❌ {e}")


# ---------- AUDIO KONSPEKT ----------
@tools_router.message(F.text == BTN_VOICE)
async def voice_start(message: Message, state: FSMContext):
    await state.set_state(AI.voice)
    await message.answer("🎙 Ma'ruza audiosini yuboring (voice yoki audio fayl, maks. 20 MB):")


@tools_router.message(AI.voice, F.voice | F.audio)
async def voice_make(message: Message, state: FSMContext, bot: Bot, session, user: User):
    media = message.voice or message.audio
    if media.file_size and media.file_size > 20 * 1024 * 1024:
        await message.answer("Fayl 20 MB dan katta.")
        return
    await state.clear()
    ok, mode, price = await _gate(message, session, user, "ai")
    if not ok:
        return
    status = await message.answer("⏳ Audio matnga aylantirilmoqda...")
    try:
        buf = io.BytesIO()
        await bot.download(media, destination=buf)
        mime = getattr(media, "mime_type", None) or "audio/ogg"
        res = await ai.ask("Bu audio ma'ruzani avval to'liq matnga aylantir (🗒 MATN), so'ng qisqa konspekt yoz "
                           "(📌 KONSPEKT, bandlar bilan). Til: audiodagi til yoki o'zbek.", audio=buf.getvalue(), mime=mime)
        await _split_send(message, res)
    except ai.AIError as e:
        await refund(session, user, "ai", mode, price)
        await message.answer(f"❌ {e}")
    finally:
        await status.delete()


router.include_router(slides_router)
router.include_router(tools_router)
