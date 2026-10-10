from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    name = State()
    role = State()
    group = State()


class HW(StatesGroup):
    text = State()
    pages = State()
    style = State()


class Pay(StatesGroup):
    topup_amount = State()
    promo = State()


class Admin(StatesGroup):
    price_value = State()
    promo_code = State()
    promo_kind = State()
    promo_value = State()
    promo_uses = State()
    channel_add = State()
    broadcast = State()
    broadcast_confirm = State()
    vip = State()
    ban = State()


class AI(StatesGroup):
    slide_topic = State()
    sparg_text = State()
    voice = State()


class Study(StatesGroup):
    schedule_add = State()
    task_add = State()
    book_add = State()
