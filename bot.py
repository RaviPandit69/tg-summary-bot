import os
import re
import json
import asyncio
import logging
import sqlite3
import datetime as dt

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI
from dotenv import load_dotenv

# ---------- базовая настройка ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN пуст. Проверь .env")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID пуст. Проверь .env")
CHAT_ID = int(CHAT_ID)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")

DB_PATH = "messages.sqlite"

# ---------- регулярки ----------
CASHTAG = re.compile(r'(?<!\w)\$[A-Z0-9]{2,10}(?!\w)')
URL = re.compile(r'https?://\S+')
ETH = re.compile(r'0x[a-fA-F0-9]{40}')
SOL = re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}')

# ---------- база ----------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS msgs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            text TEXT,
            ts INTEGER
        )"""
    )
    return conn

# ---------- утилиты ----------
def extract_entities(text: str):
    tickers = list({t.strip("$") for t in CASHTAG.findall(text)})
    urls = list(set(URL.findall(text)))
    contracts = list(set(ETH.findall(text) + [s for s in SOL.findall(text) if len(s) >= 36]))
    return {"tickers": tickers[:6], "urls": urls[:6], "contracts": contracts[:6]}

def build_prompt(items):
    lines = []
    for it in items:
        tag = it["username"] or it["full_name"] or f"id:{it['user_id']}"
        ents = extract_entities(it["text"])
        meta = []
        if ents["tickers"]:
            meta.append("Tickers=" + ",".join(ents["tickers"]))
        if ents["urls"]:
            meta.append("Links=" + ",".join(ents["urls"]))
        if ents["contracts"]:
            meta.append("Contracts=" + ",".join(ents["contracts"]))
        meta_s = f" | {' | '.join(meta)}" if meta else ""
        lines.append(f"- {tag}: {it['text']}{meta_s}")

    system = (
        "You are a crypto chat summarizer. Output ONLY JSON.\n"
        "Return key actionable ideas from the last 24h. Merge duplicates.\n"
        "Schema:\n"
        "{\n"
        '  "summary_window_hours": 24,\n'
        '  "items": [\n'
        '    {"author":"@username|full_name|id:123","idea":"concise","tickers":["APT"],"links":["https://"],"contracts":["0x..."]}\n'
        "  ]\n"
        "}\n"
        "Keep ideas to max 20 words. Tickers uppercase without $. Prefer earliest author for duplicates."
    )
    user = "Source messages:\n" + "\n".join(lines)
    return system, user

async def summarize_and_post():
    if not client:
        await bot.send_message(CHAT_ID, "⚠️ OPENAI_API_KEY не задан. Саммари недоступно")
        return

    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    day_ago = now - 24 * 3600

    conn = db()
    cur = conn.execute(
        "SELECT user_id, username, full_name, text, ts FROM msgs WHERE ts>=? AND chat_id=? ORDER BY ts ASC",
        (day_ago, CHAT_ID),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await bot.send_message(CHAT_ID, "🧾 24h Summary\nНет сообщений за последние 24 часа")
        return

    items = []
    for uid, username, full_name, text, ts in rows:
        if not text:
            continue
        if len(text.strip()) < 8:
            continue
        items.append(
            {"user_id": uid, "username": username, "full_name": full_name, "text": text.strip(), "ts": ts}
        )

    if not items:
        await bot.send_message(CHAT_ID, "🧾 24h Summary\nПолезных сообщений не найдено")
        return

    system, user = build_prompt(items)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
    except Exception as e:
        logging.exception("Суммаризация упала")
        await bot.send_message(CHAT_ID, f"⚠️ Ошибка суммаризации: {e}")
        return

    out = ["🧾 <b>24h Summary</b>"]
    for it in data.get("items", [])[:12]:
        author = it.get("author", "@unknown")
        idea = it.get("idea", "").strip()
        tickers = it.get("tickers", []) or []
        links = it.get("links", []) or []
        contracts = it.get("contracts", []) or []

        parts = []
        if tickers:
            parts.append("[" + ",".join(tickers) + "]")
        if contracts:
            parts.append(" | ".join(contracts))
        if links:
            parts.append(" | ".join(links))
        tail = f" — {' — '.join(parts)}" if parts else ""
        out.append(f"• <b>{author}</b>: {idea}{tail}")

    if len(out) == 1:
        out.append("• Нет идей за сутки")

    await bot.send_message(CHAT_ID, "\n".join(out))

# ---------- хендлеры ----------
@dp.message(Command("ping"))
async def ping(msg: Message):
    await msg.reply("pong")

@dp.message(Command("id"))
async def get_id(msg: Message):
    await msg.reply(f"chat_id: {msg.chat.id}")

@dp.message(Command("summary_now"))
async def summary_now(msg: Message):
    await summarize_and_post()

@dp.message(F.chat.type.in_({ChatType.SUPERGROUP, ChatType.GROUP}))
async def capture(message: Message):
    if not message.text:
        return
    try:
        conn = db()
        conn.execute(
            "INSERT INTO msgs(chat_id,user_id,username,full_name,text,ts) VALUES(?,?,?,?,?,?)",
            (
                message.chat.id,
                message.from_user.id if message.from_user else None,
                f"@{message.from_user.username}" if message.from_user and message.from_user.username else None,
                f"{message.from_user.full_name}" if message.from_user else None,
                message.text.strip(),
                int(message.date.timestamp()),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        logging.exception("Ошибка записи сообщения в БД")

# ---------- запуск ----------
async def main():
    logging.info(f"Старт бота. CHAT_ID={CHAT_ID}")
    scheduler.add_job(summarize_and_post, trigger="cron", hour=9, minute=0)
    scheduler.start()
    try:
        await bot.send_message(CHAT_ID, "✅ Бот запущен. Команды: /ping /id /summary_now")
    except Exception as e:
        logging.error(f"Не удалось отправить стартовое сообщение в CHAT_ID. Причина: {e}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
