import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.types import InlineKeyboardButton as B
from sqlalchemy import select

from config import config
from database import crud
from database.models import Payment, User
from keyboards.inline import grid, kb
from keyboards.reply import BTN_VIP
from middlewares.module_guard import ModuleGuard
from services import payments as svc
from services.promo import apply_promo, validate_promo
from states.states import Pay

log = logging.getLogger(__name__)
router = Router()
guarded = Router()  # faqat "payments" moduli yoqilgan bo'lsa ishlaydi (menyu/tanlov); to'lov tasdig'i guard'siz
guarded.message.middleware(ModuleGuard("payments"))
guarded.callback_query.middleware(ModuleGuard("payments"))

TOPUP_OPTIONS = (10_000, 25_000, 50_000, 100_000)


async def _vip_menu(session, user: User) -> tuple[str, object]:
    m, s = (await crud.get_setting(session, "vip_month_price"), await crud.get_setting(session, "vip_semester_price"))
    status = f"💎 VIP: {user.vip_until:%d.%m.%Y} gacha" if user.is_vip else "🆓 Bepul tarif"
    text = (f"{status}\n💰 Balans: <b>{user.balance:,} so'm</b>\n\n<b>VIP imkoniyatlari:</b> cheksiz AI, tayyor husnixat "
            f"va slaydlar, ko'p varoqli husnixat.\n\n• 1 oy — <b>{m:,} so'm</b>\n• 1 semestr — <b>{s:,} so'm</b>")
    return text, kb([
        [B(text=f"💎 1 oy — {m:,}", callback_data="buy:vip_month")],
        [B(text=f"💎 1 semestr — {s:,}", callback_data="buy:vip_semester")],
        [B(text="➕ Balansni to'ldirish", callback_data="buy:topup")],
        [B(text="🏷 Promokod kiritish", callback_data="promo:enter")],
    ])


@guarded.message(F.text == BTN_VIP)
async def vip_menu(message: Message, session, user: User):
    text, markup = await _vip_menu(session, user)
    await message.answer(text, parse_mode="HTML", reply_markup=markup)


@guarded.callback_query(F.data == "vip:menu")
async def vip_menu_cb(call: CallbackQuery, session, user: User):
    text, markup = await _vip_menu(session, user)
    await call.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await call.answer()


# ---- promokod ----
@guarded.callback_query(F.data == "promo:enter")
async def promo_enter(call: CallbackQuery, state: FSMContext):
    await state.set_state(Pay.promo)
    await call.message.answer("🏷 Promokodni yuboring:")
    await call.answer()


@guarded.message(Pay.promo, F.text)
async def promo_check(message: Message, state: FSMContext, session, user: User):
    promo, err = await validate_promo(session, message.text, user.tg_id)
    await state.set_state(None)
    if err:
        await message.answer(f"❌ {err}")
        return
    await state.update_data(promo=promo.code)
    off = f"{promo.value}%" if promo.kind == "percent" else f"{promo.value:,} so'm"
    await message.answer(f"✅ Promokod qabul qilindi: <b>-{off}</b>. Keyingi VIP xaridingizda qo'llanadi.", parse_mode="HTML")


# ---- mahsulot tanlash ----
@guarded.callback_query(F.data.startswith("buy:"))
async def buy(call: CallbackQuery, state: FSMContext, session, user: User):
    product = call.data.split(":")[1]
    await call.answer()
    if product == "topup":
        rows = [[B(text=f"{a:,} so'm", callback_data=f"topup:{a}")] for a in TOPUP_OPTIONS]
        rows.append([B(text="✏️ Boshqa summa", callback_data="topup:custom")])
        await call.message.answer("Qancha to'ldirasiz?", reply_markup=kb(rows))
        return
    if product in svc.VIP_PRODUCTS:
        await _choose_method(call.message, state, session, user, product, 0)


@guarded.callback_query(F.data.startswith("topup:"))
async def topup_amount_cb(call: CallbackQuery, state: FSMContext, session, user: User):
    val = call.data.split(":")[1]
    await call.answer()
    if val == "custom":
        await state.set_state(Pay.topup_amount)
        await call.message.answer("Summani so'mda yozing (min 5 000):")
        return
    await _choose_method(call.message, state, session, user, "topup", int(val))


@guarded.message(Pay.topup_amount, F.text.regexp(r"^\d[\d\s]*$"))
async def topup_custom(message: Message, state: FSMContext, session, user: User):
    amount = int(message.text.replace(" ", ""))
    if not 5_000 <= amount <= 5_000_000:
        await message.answer("Summa 5 000 dan 5 000 000 so'mgacha bo'lsin.")
        return
    await state.set_state(None)
    await _choose_method(message, state, session, user, "topup", amount)


async def _choose_method(msg: Message, state: FSMContext, session, user: User, product: str, topup: int):
    data = await state.get_data()
    price = await svc.product_price(session, product, topup)
    promo_code = data.get("promo") if product in svc.VIP_PRODUCTS else None
    promo = None
    if promo_code:
        promo, _ = await validate_promo(session, promo_code, user.tg_id)
        if promo is None:
            promo_code = None
    final = apply_promo(price, promo)
    await state.update_data(order={"product": product, "amount": final, "promo": promo_code})
    rows = []
    if config.click_token:
        rows.append([B(text="💳 Click", callback_data="pay:click")])
    if config.payme_token:
        rows.append([B(text="💳 Payme", callback_data="pay:payme")])
    rows.append([B(text="⭐ Telegram Stars", callback_data="pay:stars")])
    if product != "topup":
        rows.append([B(text=f"💰 Balansdan ({user.balance:,})", callback_data="pay:balance")])
    disc = f" (promokod bilan, asl narx {price:,})" if promo else ""
    await msg.answer(f"{svc.product_title(product)}\nTo'lov summasi: <b>{final:,} so'm</b>{disc}\n\nTo'lov usulini tanlang:",
                     parse_mode="HTML", reply_markup=kb(rows))


@guarded.callback_query(F.data.startswith("pay:"))
async def pay_method(call: CallbackQuery, state: FSMContext, bot: Bot, session, user: User):
    method = call.data.split(":")[1]
    order = (await state.get_data()).get("order")
    if not order:
        await call.answer("Buyurtma eskirdi, qaytadan boshlang.", show_alert=True)
        return
    await call.answer()
    product, amount, promo = order["product"], order["amount"], order["promo"]

    if method == "balance":
        if user.balance < amount:
            await call.message.answer("❌ Balans yetarli emas.")
            return
        user.balance -= amount
        pay, _ = await svc.create_payment(session, user, "balance", product, amount, promo)
        await call.message.answer(await svc.fulfill(session, bot, pay))
        await state.update_data(order=None, promo=None)
        return

    if method in ("click", "payme") and amount < 1000:
        await call.message.answer("Bu summani karta orqali to'lab bo'lmaydi. Stars yoki balansdan foydalaning.")
        return
    pay, paid = await svc.create_payment(session, user, method, product, amount, promo)
    label = svc.product_title(product)
    if method == "stars":
        await bot.send_invoice(call.message.chat.id, title=label, description=f"{amount:,} so'm", payload=pay.payload,
                               provider_token="", currency="XTR", prices=[LabeledPrice(label=label, amount=paid)])
    else:
        token = config.click_token if method == "click" else config.payme_token
        await bot.send_invoice(call.message.chat.id, title=label, description=f"Buyurtma: {label}", payload=pay.payload,
                               provider_token=token, currency="UZS", prices=[LabeledPrice(label=label, amount=paid)])


# ---- Telegram to'lov hodisalari (guard'siz: pul olingan bo'lsa, doim yakunlansin) ----
@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session):
    pay = await session.scalar(select(Payment).where(Payment.payload == query.invoice_payload))
    if pay is None or pay.status != "pending" or pay.tg_id != query.from_user.id \
            or pay.amount_paid != query.total_amount or pay.currency != query.currency:
        await query.answer(ok=False, error_message="To'lov ma'lumotlari mos kelmadi, qaytadan urinib ko'ring.")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def paid(message: Message, bot: Bot, session):
    sp = message.successful_payment
    pay = await session.scalar(select(Payment).where(Payment.payload == sp.invoice_payload))
    if pay is None:
        log.error("Noma'lum to'lov: %s", sp.invoice_payload)
        await message.answer("To'lov qabul qilindi, lekin buyurtma topilmadi. Admin bilan bog'laning.")
        return
    text = await svc.fulfill(session, bot, pay, sp.provider_payment_charge_id)
    await message.answer(text)
    for admin in config.admin_ids:
        try:
            await bot.send_message(admin, f"💰 Yangi to'lov: {pay.amount_uzs:,} so'm ({pay.provider}, {pay.product}) — {pay.tg_id}")
        except Exception:
            pass


router.include_router(guarded)
