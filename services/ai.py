"""Gemini REST orqali AI (slayd, spargalka, audio konspekt). Kalit: GEMINI_API_KEY."""
import base64
import json
import re

import httpx

from config import config


class AIError(Exception):
    pass


async def ask(prompt: str, audio: bytes | None = None, mime: str = "audio/ogg") -> str:
    if not config.gemini_key:
        raise AIError("AI sozlanmagan (GEMINI_API_KEY yo'q).")
    parts: list[dict] = [{"text": prompt}]
    if audio:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(audio).decode()}})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.gemini_model}:generateContent"
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, params={"key": config.gemini_key}, json={"contents": [{"parts": parts}]})
    if r.status_code != 200:
        raise AIError(f"AI xatosi: {r.status_code}")
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        raise AIError("AI javob bermadi.")


async def slide_outline(topic: str, count: int = 8) -> dict:
    prompt = (f"'{topic}' mavzusida {count} ta slaydli taqdimot tuz. Til: o'zbek (lotin). "
              'FAQAT JSON qaytar: {"title": str, "slides": [{"title": str, "bullets": [str, ...3-5 ta]}]}')
    raw = await ask(prompt)
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise AIError("AI noto'g'ri formatda javob berdi, qayta urinib ko'ring.")
