import os, re, json, asyncio, logging, sqlite3, datetime as dt
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI
from dotenv import load_dotenv

# --- базовая настройка ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN пуст — проверь .env")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

DB_PATH = "messages.sqlite"
scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")

# --- регулярки ---
CASHTAG = re.compile(r'(?<!\w)\$[A-Z0-9]{2,10}(?!\w)')
URL = re.compile(r'https?://\S+')
ETH = re.compile(r'0x[a-fA-F0-9]{40}')
SOL = re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}')

# --- БД ---
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS msgs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        text TEXT,
        ts INTEGER
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS chats(
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        enabled INTEGER DEFAULT 1,
        hour INTEGER DEFAULT 9,     -- локально 09:00 Europe/Kyiv
        tz TEXT DEFAULT 'Europe/Kyiv'
    )""")
    return conn

# --- утилиты ---
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
        if ents["tickers"]: meta.append("Tickers=" + ",".join(ents["tickers"]))
        if ents["urls"]: meta.append("Links=" + ",".join(ents["urls"]))
        if ents["contracts"]: meta.append("Contracts=" + ",".join(ents["contracts"]))
        meta_s = f" | {' | '.join(meta)}" if meta else ""
        lines.append(f"- {tag}: {it['text']}{meta_s}")

    system = (
        "You are a crypto chat summarizer. Output ONLY JSON.\n"
        "Return key actionable ideas from the last 24h. Merge duplicates.\n"
        "Schema:{\"summary_window_hours\":24,\"items\":[{\"author\":\"@user|full_name|id:123\",\"idea\":\"concise\","
        "\"tickers\":[\"APT\"],\"links\":[\"https://\"],\"contracts\":[\"0x...\"]}]}\n"
        "Keep each idea <=20 words. Tickers uppercase without $. Prefer earliest author for duplicates."
    )
    user = "Source messages:\n" + "\n".join(lines)
    return system, user

async def summarize_and_post_for_chat(chat_id: int):
    if not client:
        await bot.send_message(chat_id, "⚠️ OPENAI_API_KEY не задан — саммари отключено"); return

    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    day_ago = now - 24*3600

    conn = db()
    cur = conn.execute(
        "SELECT user_id, username, full_name, text, ts FROM msgs WHERE ts>=? AND chat_id=? ORDER BY ts ASC",
        (day_ago, chat_id))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await bot.send_message(chat_id, "🧾 24h Summary\nНет сообщений за последние 24 часа"); return

    items = []
    for uid, username, full_name, text, ts in rows:
        if text and len(text.strip()) >= 8:
            items.append({"user_id": uid, "username": username, "full_name": full_name, "text": text.strip(), "ts": ts})

    if not items:
        await bot.send_message(chat_id, "🧾 24h Summary\nПолезных сообщений не найдено"); return

    system, user = build_prompt(items)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=0.2, response_format={"type":"json_object"})
        data = json.loads(resp.choices[0].message.content)
    except Exception as e:
        logging.exception("LLM error")
        await bot.send_message(chat_id, f"⚠️ Ошибка суммаризации: {e}"); return

    out = ["🧾 <b>24h Summary</b>"]
    for it in data.get("items", [])[:12]:
        author = it.get("author","@unknown"); idea = it.get("idea","").strip()
        t, l, c = it.get("tickers",[]) or [], it.get("links",[]) or [], it.get("contracts",[]) or []
        parts=[]
        if t: parts.append("[" + ",".join(t) + "]")
        if c: parts.append(" | ".join(c))
        if l: parts.append(" | ".join(l))
        tail = (" — " + " — ".join(parts)) if parts else ""
        out.append(f"• <b>{author}</b>: {idea}{tail}")
    if len(out)==1: out.append("• Нет идей за сутки")

    await bot.send_message(chat_id, "\n".join(out))

# --- планировщик: один job, обходит все включённые чаты ---
async def daily_summaries_job():
    conn = db()
    chats = conn.execute("SELECT chat_id, hour, tz FROM chats WHERE enabled=1").fetchall()
    conn.close()
    if not chats: return
    now_kiev = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=3)))  # приблизительно
    hour_now = now_kiev.hour
    for chat_id, hour, _tz in chats:
        if hour == hour_now:
            try:
                await summarize_and_post_for_chat(chat_id)
            except Exception:
                logging.exception(f"Ошибка сводки для чата {chat_id}")

# --- хендлеры команд ---
@dp.message(Command("ping"))
async def ping(msg: Message):
    await msg.reply("pong")

@dp.message(Command("id"))
async def chat_id_cmd(msg: Message):
    await msg.reply(f"chat_id: {msg.chat.id}")

@dp.message(Command("subscribe"))
async def subscribe(msg: Message):
    if msg.chat.type not in (ChatType.SUPERGROUP, ChatType.GROUP):
        await msg.reply("Добавь меня в группу/супергруппу и запусти /subscribe там."); return
    conn = db()
    conn.execute("INSERT OR REPLACE INTO chats(chat_id, title, enabled) VALUES(?,?,1)",
                 (msg.chat.id, msg.chat.title or str(msg.chat.id)))
    conn.commit(); conn.close()
    await msg.reply("✅ Чат подписан. Ежедневная сводка будет приходить в 09:00 (Europe/Kyiv). Команда: /summary_now")

@dp.message(Command("unsubscribe"))
async def unsubscribe(msg: Message):
    conn = db()
    conn.execute("UPDATE chats SET enabled=0 WHERE chat_id=?", (msg.chat.id,))
    conn.commit(); conn.close()
    await msg.reply("⏸️ Сводка для этого чата отключена.")

@dp.message(Command("sethour"))
async def sethour(msg: Message):
    # пример: /sethour 10
    try:
        h = int((msg.text or "").split()[1])
        if h<0 or h>23: raise ValueError
    except Exception:
        await msg.reply("Использование: <code>/sethour 10</code> (0..23, время Europe/Kyiv)"); return
    conn = db()
    conn.execute("UPDATE chats SET hour=? WHERE chat_id=?", (h, msg.chat.id))
    conn.commit(); conn.close()
    await msg.reply(f"🕘 Час ежедневной сводки установлен: {h:02d}:00 (Europe/Kyiv)")

@dp.message(Command("summary_now"))
async def summary_now(msg: Message):
    await summarize_and_post_for_chat(msg.chat.id)

# --- сбор сообщений из всех чатов ---
@dp.message(F.chat.type.in_({ChatType.SUPERGROUP, ChatType.GROUP}))
async def capture(message: Message):
    if not message.text: return
    try:
        conn = db()
        conn.execute("INSERT INTO msgs(chat_id,user_id,username,full_name,text,ts) VALUES(?,?,?,?,?,?)",
            (message.chat.id,
             message.from_user.id if message.from_user else None,
             f"@{message.from_user.username}" if message.from_user and message.from_user.username else None,
             message.from_user.full_name if message.from_user else None,
             message.text.strip(),
             int(message.date.timestamp())))
        conn.commit(); conn.close()
    except Exception:
        logging.exception("DB insert error")

# --- запуск ---
async def main():
    logging.info("Старт многочатового бота")
    # раз в 10 минут проверяем «наступил ли час» для каждого чата (просто и надёжно)
    scheduler.add_job(daily_summaries_job, trigger="cron", minute="*/10")
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
