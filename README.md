# Talaba Bot — Telegram (aiogram 3, SQLAlchemy async, SQLite)

## Ishga tushirish
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # BOT_TOKEN, ADMIN_IDS ni to'ldiring
# fonts/ papkasiga TTF shriftlarni joylang (fonts/README.md)
python main.py
```
Docker: `docker build -t talaba-bot . && docker run --env-file .env -v $(pwd)/data:/app/data talaba-bot`

## Struktura
```
main.py                 kirish nuqtasi, middleware va routerlar
config.py               .env sozlamalari
database/               base.py (engine), models.py, crud.py, seed.py (default narx/modul/shrift)
middlewares/            db (user+session), throttle, menu_reset, registered, forced_sub, module_guard
handlers/               start (FSM ro'yxat), profile, handwriting, payments, admin, ai_tools, schedule, tasks_library
services/               handwriting (PIL+ReportLab), payments, promo, access (limit/narx), ai, slides, scheduler
keyboards/ states/      reply/inline klaviaturalar, FSM holatlari
```

## Muhim tushunchalar
- **Narx va limitlar** `settings_prices` jadvalida; admin: /admin → 💰 Narx va limitlar.
- **Modullarni o'chirish**: /admin → 🧩 Modullar (har bir router `ModuleGuard` bilan o'ralgan).
- **To'lov**: Click va Payme — BotFather → Payments orqali olingan *provider token* bilan Telegram invoice
  (`CLICK_PROVIDER_TOKEN`, `PAYME_PROVIDER_TOKEN`). Stars — `XTR` valyutasi, kurs `stars_rate` sozlamasida.
  Bevosita Click/Payme Merchant API (webhook) ulash kerak bo'lsa, `services/payments.py` dagi `fulfill()` ni chaqirish kifoya.
- **Limit mantig'i** (`services/access.py`): VIP → cheksiz; bepul → kunlik limit; tugasa → balansdan yechiladi.
- **AI** (slayd, spargalka, audio): `GEMINI_API_KEY` kerak. Model nomini `GEMINI_MODEL` bilan almashtiring.
- Eslatmalar (APScheduler): dars boshlanishiga 15 daqiqa qolganda; VIP tugashiga 3 kun qolganda (10:00 da).

## Eslatma
Kod sandbox'da to'liq sinalmagan bo'lishi mumkin: husnixat moduli ishga tushirib tekshirilgan, qolgan qismlar
sintaksis darajasida. Birinchi ishga tushirishda `python main.py` loglarini kuzating.
