from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup as M
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb(rows: list[list[B]]) -> M:
    return M(inline_keyboard=rows)


def sub_kb(channels) -> M:
    rows = [[B(text=f"📢 {c.title}", url=c.link)] for c in channels]
    rows.append([B(text="✅ Tekshirish", callback_data="check_sub")])
    return kb(rows)


def role_kb() -> M:
    return kb([[B(text="🎓 Talaba", callback_data="role:student"),
                B(text="👨‍🏫 O'qituvchi / Sardor", callback_data="role:teacher")]])


def topup_hint_kb() -> M:
    return kb([[B(text="➕ Balansni to'ldirish", callback_data="buy:topup")],
               [B(text="💎 VIP olish", callback_data="vip:menu")]])


def grid(buttons: list[B], per_row: int = 2) -> M:
    b = InlineKeyboardBuilder()
    for x in buttons:
        b.add(x)
    b.adjust(per_row)
    return b.as_markup()
