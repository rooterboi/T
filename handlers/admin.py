import asyncio
import logging
import secrets

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MessageOriginChannel
from aiogram.types import InlineKeyboardButton as B
from sqlalchemy import select

from config import config
from database import crud
from database.models import ForcedChannel, ModuleStatus, Promocode, Setting, User
from keyboards.inline import kb
from keyboards.reply import BTN_ADMIN
from states.states import Admin

log = logging.getLogger(__name__)


class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        u = getattr(event, "from_user", None)
        return bool(u and u.id in config.admin_ids)


router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

HOME_KB = kb([
    [B(text="💰 Narx va limitlar", callback_data="adm:prices"), B(text="🧩 Modullar", callback_data="adm:modules")],
    [B(text="🏷 Promokodlar", callback_data="adm:promos"), B(text="📢 Majburiy obuna", callback_data="adm:channels")],
    [B(text="📨 Broadcast", callback_data="adm:broadcast"), B(text="💎 VIP berish/olish", callback_data="adm:vip")],
    [B(text="🚫 Ban/Unban", callback_data="adm:ban"), B(text="📊 Statistika", callback_data="adm:stats")],
])
BACK = [B(text="⬅️ Admin menyu", callback_data="adm:home")]


@router.message(Command("admin"))
@router.message(F.text == BTN_ADMIN)
async def admin_home(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 <b>Admin panel</b>", parse_mode="HTML", reply_markup=HOME_KB)


@router.callback_query(F.data == "adm:home")
async def admin_home_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🛠 <b>Admin panel</b>", parse_mode="HTML", reply_markup=HOME_KB)
    await call.answer()


# ================= NARXLAR VA LIMITLAR =================
@router.callback_query(F.data == "adm:prices")
async def prices(call: CallbackQuery, session):
    rows = (await session.scalars(select(Setting).order_by(Setting.key))).all()
    buttons = [[B(text=f"{r.title}: {r.value:,}", callback_data=f"adm:price:{r.key}")] for r in rows]
    buttons.append(BACK)
    await call.message.edit_text("💰 O'zgartirmoqchi bo'lgan qiymatni tanlang:", reply_markup=kb(buttons))
    await call.answer()


@router.callback_query(F.data.startswith("adm:price:"))
async def price_pick(call: CallbackQuery, state: FSMContext, session):
    key = call.data.split(":", 2)[2]
    row = await session.get(Setting, key)
    await state.set_state(Admin.price_value)
    await state.update_data(key=key)
    await call.message.answer(f"<b>{row.title}</b>\nHozirgi qiymat: <code>{row.value}</code>\n\nYangi qiymatni (butun son) yuboring:",
                              parse_mode="HTML")
    await call.answer()


@router.message(Admin.price_value, F.text.regexp(r"^\d[\d\s]*$"))
async def price_set(message: Message, state: FSMContext, session):
    key = (await state.get_data())["key"]
    await crud.set_setting(session, key, int(message.text.replace(" ", "")))
    await state.clear()
    await message.answer("✅ Saqlandi.", reply_markup=kb([[B(text="💰 Yana o'zgartirish", callback_data="adm:prices")], BACK]))


# ================= MODULLAR =================
def _modules_kb(rows):
    b = [[B(text=f"{'✅' if m.enabled else '❌'} {m.title}", callback_data=f"adm:mod:{m.key}")] for m in rows]
    b.append(BACK)
    return kb(b)


@router.callback_query(F.data == "adm:modules")
async def modules(call: CallbackQuery, session):
    rows = (await session.scalars(select(ModuleStatus))).all()
    await call.message.edit_text("🧩 Bo'limni yoqish/o'chirish uchun bosing:", reply_markup=_modules_kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("adm:mod:"))
async def module_toggle(call: CallbackQuery, session):
    state_now = await crud.toggle_module(session, call.data.split(":", 2)[2])
    rows = (await session.scalars(select(ModuleStatus))).all()
    await call.message.edit_reply_markup(reply_markup=_modules_kb(rows))
    await call.answer("Yoqildi ✅" if state_now else "O'chirildi ❌")


# ================= PROMOKODLAR =================
@router.callback_query(F.data == "adm:promos")
async def promos(call: CallbackQuery, session):
    rows = (await session.scalars(select(Promocode).order_by(Promocode.id.desc()).limit(20))).all()
    buttons = []
    for p in rows:
        off = f"{p.value}%" if p.kind == "percent" else f"{p.value:,}"
        buttons.append([B(text=f"🗑 {p.code} (-{off}) {p.used_count}/{p.max_uses or '∞'}", callback_data=f"adm:pdel:{p.id}")])
    buttons.append([B(text="➕ Yangi promokod", callback_data="adm:pnew")])
    buttons.append(BACK)
    await call.message.edit_text("🏷 Promokodlar (o'chirish uchun bosing):", reply_markup=kb(buttons))
    await call.answer()


@router.callback_query(F.data.startswith("adm:pdel:"))
async def promo_del(call: CallbackQuery, session):
    p = await session.get(Promocode, int(call.data.split(":")[2]))
    if p:
        await session.delete(p)
        await session.commit()
    await promos(call, session)


@router.callback_query(F.data == "adm:pnew")
async def promo_new(call: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.promo_code)
    await call.message.answer("Promokod matnini yuboring (yoki «auto» — avtomatik yaratish):")
    await call.answer()


@router.message(Admin.promo_code, F.text)
async def promo_code(message: Message, state: FSMContext, session):
    code = secrets.token_hex(3).upper() if message.text.lower() == "auto" else message.text.strip().upper()
    if await session.scalar(select(Promocode).where(Promocode.code == code)):
        await message.answer("Bunday kod bor, boshqasini yuboring.")
        return
    await state.update_data(code=code)
    await state.set_state(Admin.promo_kind)
    await message.answer("Turi?", reply_markup=kb([[B(text="% Foiz", callback_data="pk:percent"),
                                                    B(text="So'm summa", callback_data="pk:amount")]]))


@router.callback_query(Admin.promo_kind, F.data.startswith("pk:"))
async def promo_kind(call: CallbackQuery, state: FSMContext):
    await state.update_data(kind=call.data.split(":")[1])
    await state.set_state(Admin.promo_value)
    await call.message.answer("Qiymatni yuboring (foiz yoki so'm):")
    await call.answer()


@router.message(Admin.promo_value, F.text.regexp(r"^\d+$"))
async def promo_value(message: Message, state: FSMContext):
    v = int(message.text)
    if (await state.get_data())["kind"] == "percent" and not 1 <= v <= 100:
        await message.answer("Foiz 1..100 oralig'ida bo'lsin.")
        return
    await state.update_data(value=v)
    await state.set_state(Admin.promo_uses)
    await message.answer("Necha marta ishlatilsin? (0 = cheksiz)")


@router.message(Admin.promo_uses, F.text.regexp(r"^\d+$"))
async def promo_uses(message: Message, state: FSMContext, session):
    d = await state.get_data()
    session.add(Promocode(code=d["code"], kind=d["kind"], value=d["value"], max_uses=int(message.text)))
    await session.commit()
    await state.clear()
    await message.answer(f"✅ Promokod yaratildi: <code>{d['code']}</code>", parse_mode="HTML",
                         reply_markup=kb([BACK]))


# ================= MAJBURIY OBUNA =================
@router.callback_query(F.data == "adm:channels")
async def channels(call: CallbackQuery, session):
    rows = await crud.list_channels(session)
    buttons = [[B(text=f"🗑 {c.title}", callback_data=f"adm:chdel:{c.id}")] for c in rows]
    buttons += [[B(text="➕ Kanal qo'shish", callback_data="adm:chadd")], BACK]
    await call.message.edit_text("📢 Majburiy obuna kanallari (bot kanalda ADMIN bo'lishi shart):", reply_markup=kb(buttons))
    await call.answer()


@router.callback_query(F.data.startswith("adm:chdel:"))
async def channel_del(call: CallbackQuery, session):
    await crud.remove_channel(session, int(call.data.split(":")[2]))
    await channels(call, session)


@router.callback_query(F.data == "adm:chadd")
async def channel_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.channel_add)
    await call.message.answer("Kanaldan biror xabarni forward qiling yoki @username / -100... ID yuboring:")
    await call.answer()


@router.message(Admin.channel_add)
async def channel_save(message: Message, state: FSMContext, bot: Bot, session):
    try:
        if isinstance(message.forward_origin, MessageOriginChannel):
            chat = await bot.get_chat(message.forward_origin.chat.id)
        else:
            ref = (message.text or "").strip()
            chat = await bot.get_chat(int(ref) if ref.lstrip("-").isdigit() else ref)
        link = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or await bot.export_chat_invite_link(chat.id))
    except Exception as e:
        await message.answer(f"❌ Kanal topilmadi yoki bot admin emas: {e}")
        return
    if not await session.scalar(select(ForcedChannel).where(ForcedChannel.chat_id == chat.id)):
        session.add(ForcedChannel(chat_id=chat.id, title=chat.title or str(chat.id), link=link))
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Qo'shildi: {chat.title}", reply_markup=kb([BACK]))


# ================= BROADCAST (anti-flood) =================
@router.callback_query(F.data == "adm:broadcast")
async def bc_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.broadcast)
    await call.message.answer("📨 Yuboriladigan xabarni jo'nating (matn / rasm / video — caption bilan).")
    await call.answer()


@router.message(Admin.broadcast)
async def bc_preview(message: Message, state: FSMContext):
    await state.update_data(src_chat=message.chat.id, src_msg=message.message_id)
    await state.set_state(Admin.broadcast_confirm)
    await message.answer("Yuqoridagi xabar hammaga yuborilsinmi?",
                         reply_markup=kb([[B(text="✅ Yuborish", callback_data="bc:go"), B(text="❌ Bekor", callback_data="adm:home")]]))


@router.callback_query(Admin.broadcast_confirm, F.data == "bc:go")
async def bc_go(call: CallbackQuery, state: FSMContext, bot: Bot, session):
    d = await state.get_data()
    await state.clear()
    ids = list((await session.scalars(select(User.tg_id).where(User.is_active.is_(True), User.is_banned.is_(False)))).all())
    await call.message.edit_text(f"🚀 Yuborish boshlandi: {len(ids)} ta foydalanuvchi.")
    asyncio.create_task(_broadcast(bot, call.from_user.id, d["src_chat"], d["src_msg"], ids))
    await call.answer()


async def _broadcast(bot: Bot, admin_id: int, src_chat: int, src_msg: int, ids: list[int]) -> None:
    from database.base import SessionMaker

    ok = fail = 0
    dead: list[int] = []
    for uid in ids:
        for _ in range(3):
            try:
                await bot.copy_message(uid, src_chat, src_msg)
                ok += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError:
                dead.append(uid)
                fail += 1
                break
            except Exception:
                fail += 1
                break
        await asyncio.sleep(0.05)  # ~20 xabar/soniya — Telegram limitidan past
    if dead:
        async with SessionMaker() as s:
            for u in (await s.scalars(select(User).where(User.tg_id.in_(dead)))).all():
                u.is_active = False
            await s.commit()
    await bot.send_message(admin_id, f"📨 Broadcast tugadi.\n✅ Yetkazildi: {ok}\n❌ Xato/bloklagan: {fail}")


# ================= VIP berish/olish, BAN =================
@router.callback_query(F.data == "adm:vip")
async def vip_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.vip)
    await call.message.answer("💎 Format: <code>TG_ID KUN</code>\nMasalan <code>123456789 30</code> — 30 kun VIP berish.\n"
                              "<code>123456789 0</code> — VIP ni olib tashlash.", parse_mode="HTML")
    await call.answer()


@router.message(Admin.vip, F.text.regexp(r"^\d+\s+\d+$"))
async def vip_apply(message: Message, state: FSMContext, session, bot: Bot):
    uid, days = (int(x) for x in message.text.split())
    u = await session.scalar(select(User).where(User.tg_id == uid))
    if not u:
        await message.answer("Foydalanuvchi topilmadi.")
        return
    if days == 0:
        u.vip_until = None
        await session.commit()
        text = "VIP olib tashlandi."
    else:
        await crud.extend_vip(session, u, days)
        text = f"{days} kun VIP berildi (→ {u.vip_until:%d.%m.%Y})."
        try:
            await bot.send_message(uid, f"🎁 Sizga admin tomonidan {days} kun VIP berildi!")
        except Exception:
            pass
    await state.clear()
    await message.answer(f"✅ {text}", reply_markup=kb([BACK]))


@router.callback_query(F.data == "adm:ban")
async def ban_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.ban)
    await call.message.answer("Ban/unban qilish uchun foydalanuvchi TG ID sini yuboring (holatini almashtiradi):")
    await call.answer()


@router.message(Admin.ban, F.text.regexp(r"^\d+$"))
async def ban_toggle(message: Message, state: FSMContext, session):
    u = await session.scalar(select(User).where(User.tg_id == int(message.text)))
    if not u or u.tg_id in config.admin_ids:
        await message.answer("Topilmadi yoki admin.")
        return
    u.is_banned = not u.is_banned
    await session.commit()
    await state.clear()
    await message.answer("🚫 Banlandi." if u.is_banned else "✅ Ban olib tashlandi.", reply_markup=kb([BACK]))


# ================= STATISTIKA =================
@router.callback_query(F.data == "adm:stats")
async def stats(call: CallbackQuery, session):
    s = await crud.stats(session)
    await call.message.edit_text(
        f"📊 <b>Statistika</b>\n👥 Jami: {s['total']}\n✅ Ro'yxatdan o'tgan: {s['registered']}\n"
        f"🆕 Bugun: {s['today']}\n💎 Faol VIP: {s['vip']}\n💰 Tushum (karta/Stars): {s['revenue']:,} so'm",
        parse_mode="HTML", reply_markup=kb([BACK]))
    await call.answer()
