from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_HW = "✍️ Husnixat"
BTN_SLIDE = "📊 AI Slayd"
BTN_SPARG = "📚 Spargalka"
BTN_VOICE = "🎙 Audio konspekt"
BTN_SCHEDULE = "🗓 Dars jadvali"
BTN_TASKS = "📝 Topshiriqlar"
BTN_LIBRARY = "📖 Kutubxona"
BTN_PROFILE = "👤 Profil"
BTN_VIP = "💎 VIP / To'lov"
BTN_REF = "🎁 Referal"
BTN_ADMIN = "🛠 Admin panel"

MENU_BUTTONS = {BTN_HW, BTN_SLIDE, BTN_SPARG, BTN_VOICE, BTN_SCHEDULE, BTN_TASKS,
                BTN_LIBRARY, BTN_PROFILE, BTN_VIP, BTN_REF, BTN_ADMIN}


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_HW), KeyboardButton(text=BTN_SLIDE)],
        [KeyboardButton(text=BTN_SPARG), KeyboardButton(text=BTN_VOICE)],
        [KeyboardButton(text=BTN_SCHEDULE), KeyboardButton(text=BTN_TASKS)],
        [KeyboardButton(text=BTN_LIBRARY), KeyboardButton(text=BTN_PROFILE)],
        [KeyboardButton(text=BTN_VIP), KeyboardButton(text=BTN_REF)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
