import os
import re
import asyncio
import logging
import sqlite3
import datetime as dt
from collections import defaultdict

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# =================== ЛОГИ ===================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("tg-summary-auto")

# =================== КОНФИГ ===================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("USER_ID", "0"))  # твой Telegram ID (кому писать в личку)
if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN или USER_ID не указан в .env")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")

DB_PATH = "messages.sqlite"

# =================== РЕГУЛЯРКИ ===================
CASHTAG = re.compile(r"\$?[A-Z0-9]{2,10}")
URL = re.compile(r"https?://\S+")

# =================== БАЗА ДАННЫХ ===================
def ensure_schema(conn: sqlite3.Connection):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS msgs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            chat_title TEXT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            text TEXT,
            ts INTEGER,
            message_id INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS chats(
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            enabled INTEGER DEFAULT 1
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )"""
    )

def db():
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    return conn

# =================== ВСПОМОГАТЕЛЬНЫЕ ===================
def make_link(chat_id: int, message_id: int | None) -> str:
    if not message_id:
        return ""
    s = str(chat_id)
    if s.startswith("-100"):
        s = s[4:]
    return f"https://t.me/c/{s}/{message_id}"

def is_auto_enabled() -> bool:
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key='auto_summaries'").fetchone()
    conn.close()
    return bool(row and row[0] == "on")

def set_auto_mode(mode: str):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES('auto_summaries',?)",
        (mode,),
    )
    conn.commit()
    conn.close()

# =================== СБОР СООБЩЕНИЙ (молча в группах) ===================
@dp.message(F.chat.type.in_({ChatType.SUPERGROUP, ChatType.GROUP}))
async def capture(message: Message):
    if not message.text:
        return
    text = message.text.strip()
    if len(text) < 3:
        return
    try:
        conn = db()
        conn.execute(
            "INSERT INTO msgs(chat_id,chat_title,user_id,username,full_name,text,ts,message_id) VALUES(?,?,?,?,?,?,?,?)",
            (
                message.chat.id,
                message.chat.title or "NoTitle",
                message.from_user.id if message.from_user else None,
                f"@{message.from_user.username}" if (message.from_user and message.from_user.username) else None,
                message.from_user.full_name if message.from_user else None,
                text,
                int(message.date.timestamp()),
                message.message_id,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.exception(f"Ошибка при записи сообщения: {e}")

# =================== САММАРИ ===================
async def summarize_chat(chat_id: int, title: str) -> str:
    """Оффлайн-саммари за 24 часа: группируем по авторам, даём $тикеры, ссылки и пермалинки."""
    since = int(dt.datetime.now().timestamp()) - 24 * 3600
    conn = db()
    rows = conn.execute(
        "SELECT user_id, username, full_name, text, message_id FROM msgs WHERE chat_id=? AND ts>?",
        (chat_id, since),
    ).fetchall()
    conn.close()

    if not rows:
        return f"🧾 <b>{title}</b>\nНет сообщений за последние 24 часа.\n"

    grouped: dict[str, list[tuple[str, int | None]]] = defaultdict(list)
    for uid, uname, full, text, mid in rows:
        author = full or uname or f"id:{uid}" or "Без имени"
        grouped[author].append((text, mid))

    lines = [f"🧾 <b>Чат:</b> {title}"]
    for author, msgs in grouped.items():
        # собрать тикеры по всем сообщениям автора
        tickers = {t.lstrip("$").upper() for t in CASHTAG.findall(" ".join([m[0] for m in msgs]))}
        tickers_fmt = f" [{', '.join(f'${t}' for t in sorted(tickers))}]" if tickers else ""
        # первая найденная ссылка автора — в шапку (опционально)
        first_link = ""
        for txt, _ in msgs:
            m = URL.search(txt)
            if m:
                first_link = m.group(0)
                break
        tail = f" {first_link}" if first_link else ""
        lines.append(f"• {author}{tickers_fmt}{tail}")

        # подпункты-идеи (первые 3 по умолчанию)
        for text, mid in msgs[:3]:
            link = make_link(chat_id, mid)
            preview = text[:150] + ("…" if len(text) > 150 else "")
            lines.append(f"  — {preview} {link}")

    return "\n".join(lines) + "\n"

async def summarize_all_chats():
    conn = db()
    chats = conn.execute("SELECT chat_id,title FROM chats WHERE enabled=1").fetchall()
    conn.close()
    if not chats:
        await bot.send_message(ADMIN_ID, "Нет активных чатов для авто-сводки.")
        return
    await bot.send_message(ADMIN_ID, "📬 Ежедневная сводка:")
    for chat_id, title in chats:
        try:
            report = await summarize_chat(chat_id, title or str(chat_id))
            await bot.send_message(ADMIN_ID, report)
            await asyncio.sleep(1.5)
        except Exception as e:
            log.exception(f"Ошибка сводки для {chat_id}: {e}")

# =================== КОМАНДЫ (только в личке) ===================
@dp.message(Command("start"))
async def start_cmd(msg: Message):
    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [KeyboardButton(text="/list")],
            [KeyboardButton(text="/auto_on"), KeyboardButton(text="/auto_off")],
        ],
    )
    text = (
        "👋 Привет! Я молча собираю сообщения из групп и присылаю тебе саммари в личку.\n\n"
        "<b>Команды:</b>\n"
        "• /list — список активных чатов\n"
        "• /subscribe &lt;chat_id&gt; — подключить чат\n"
        "• /unsubscribe &lt;chat_id&gt; — отключить чат\n"
        "• /summary_now &lt;chat_id&gt; — сводка за 24ч сейчас\n"
        "• /auto_on — включить авто-сводки (09:00)\n"
        "• /auto_off — выключить авто-сводки\n\n"
        "<i>Добавь бота участником в группу, узнай её chat_id и управляй из лички.</i>"
    )
    await msg.answer(text, reply_markup=kb)

@dp.message(Command("list"))
async def list_cmd(msg: Message):
    conn = db()
    rows = conn.execute("SELECT chat_id, title FROM chats WHERE enabled=1").fetchall()
    conn.close()
    if not rows:
        await msg.answer("Нет активных чатов.")
        return
    text = "\n".join([f"{r[1]} — <code>{r[0]}</code>" for r in rows])
    await msg.answer(f"📋 Активные чаты:\n{text}")

@dp.message(Command("subscribe"))
async def subscribe_cmd(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    try:
        chat_id = int(msg.text.split()[1])
    except Exception:
        await msg.answer("Использование: /subscribe <chat_id>")
        return
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO chats(chat_id, title, enabled) VALUES(?,?,1)",
        (chat_id, str(chat_id)),
    )
    conn.commit()
    conn.close()
    await msg.answer(f"✅ Чат {chat_id} добавлен для сбора.")

@dp.message(Command("unsubscribe"))
async def unsubscribe_cmd(msg: Message):
    try:
        chat_id = int(msg.text.split()[1])
    except Exception:
        await msg.answer("Использование: /unsubscribe <chat_id>")
        return
    conn = db()
    conn.execute("UPDATE chats SET enabled=0 WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()
    await msg.answer(f"⏸️ Чат {chat_id} выключен.")

@dp.message(Command("summary_now"))
async def summary_now_cmd(msg: Message):
    try:
        chat_id = int(msg.text.split()[1])
    except Exception:
        await msg.answer("Использование: /summary_now <chat_id>")
        return
    # получить заголовок если есть
    conn = db()
    row = conn.execute("SELECT title FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
    conn.close()
    title = (row[0] if row else None) or str(chat_id)
    report = await summarize_chat(chat_id, title)
    await bot.send_message(ADMIN_ID, report)
    await msg.answer("📬 Сводка отправлена в личку.")

@dp.message(Command("auto_on"))
async def auto_on_cmd(msg: Message):
    set_auto_mode("on")
    scheduler.add_job(
        summarize_all_chats, "cron", hour=9, minute=0, id="daily_summary", replace_existing=True
    )
    await msg.answer("✅ Авто-сводки включены (ежедневно в 09:00).")

@dp.message(Command("auto_off"))
async def auto_off_cmd(msg: Message):
    set_auto_mode("off")
    try:
        scheduler.remove_job("daily_summary")
    except Exception:
        pass
    await msg.answer("🛑 Авто-сводки выключены.")

# =================== РЕГИСТРАЦИЯ КОМАНД В UI ===================
async def setup_commands():
    cmds = [
        BotCommand(command="start",        description="Показать меню и команды"),
        BotCommand(command="list",         description="Список активных чатов"),
        BotCommand(command="subscribe",    description="Подключить чат: /subscribe <chat_id>"),
        BotCommand(command="unsubscribe",  description="Отключить чат: /unsubscribe <chat_id>"),
        BotCommand(command="summary_now",  description="Сводка сейчас: /summary_now <chat_id>"),
        BotCommand(command="auto_on",      description="Включить авто-сводки"),
        BotCommand(command="auto_off",     description="Выключить авто-сводки"),
    ]
    await bot.set_my_commands(cmds, scope=BotCommandScopeAllPrivateChats())

# =================== ЗАПУСК ===================
async def main():
    log.info("Старт бота (авто-сводки, личные команды)")
    if is_auto_enabled():
        scheduler.add_job(
            summarize_all_chats, "cron", hour=9, minute=0, id="daily_summary", replace_existing=True
        )
    scheduler.start()
    await setup_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
