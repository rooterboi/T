import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _ids(value: str) -> tuple[int, ...]:
    return tuple(int(x) for x in value.replace(" ", "").split(",") if x)


class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: tuple[int, ...] = _ids(os.getenv("ADMIN_IDS", ""))
    db_url: str = os.getenv("DB_URL", f"sqlite+aiosqlite:///{DATA_DIR / 'bot.db'}")
    click_token: str = os.getenv("CLICK_PROVIDER_TOKEN", "")
    payme_token: str = os.getenv("PAYME_PROVIDER_TOKEN", "")
    gemini_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    timezone: str = "Asia/Tashkent"


config = Config()
