# 🧠 TG Summary Bot

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)  
[![Aiogram](https://img.shields.io/badge/aiogram-3.22-brightgreen)](https://docs.aiogram.dev/)  
[![OpenAI](https://img.shields.io/badge/OpenAI-API-orange)](https://platform.openai.com/)  
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**TG Summary Bot** — это Telegram-бот, который ежедневно собирает обсуждения из крипто-чатов и формирует краткое саммари.  
Он выделяет **авторов идей**, **тикеры**, **контракты**, **ссылки** и помогает быстро понять, что обсуждали за последние 24 часа.

##  ⚙️ Основные возможности

- 🕒 Автоматическое саммари каждые 24 часа (по Киеву в 09:00)
- 💬 Команда `/summary_now` — мгновенная генерация обзора за сутки
- 🙋‍♂️ Показывает автора, тикеры, контракты и ссылки
- 💾 Хранит историю сообщений в SQLite
- 🤖 Использует OpenAI (`gpt-4o-mini`) для анализа
- ⚡ Простая установка и минимальные зависимости

## 🚀 Быстрый старт

### 1️⃣ Клонируй репозиторий
```bash
git clone https://github.com/dant1k/tg-summary-bot.git
cd tg-summary-bot
```
### 2️⃣ Создай и активируй виртуальное окружение
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3️⃣ Установи зависимости
```bash
pip install -r requirements.txt
```
### 4️⃣ Настрой файл .env

Создай файл .env в корне проекта и заполни его своими данными:
```bash
BOT_TOKEN=твой_бот_токен_из_BotFather
OPENAI_API_KEY=твой_openai_api_key
CHAT_ID=-100XXXXXXXXXX
```
⚠️ Для работы в группах нужно отключить Privacy Mode у бота:
@BotFather → Bot Settings → Group Privacy → Turn OFF

### 💬 Команды
| Команда           | Описание                           |
| ----------------- | ---------------------------------- |
| `/ping`           | Проверить, что бот работает        |
| `/id`             | Узнать `chat_id` чата              |
| `/summary_now`    | Создать саммари вручную            |
| *(автоматически)* | Ежедневная сводка в 09:00 по Киеву |

### 📊 Пример вывода
```bash
🧾 24h Summary

• @cryptokos: LayerZero Airdrop активен — [L0]
• @alphauser: Новый DePIN-тестнет на Solana — 0xA12b...
• @analyst42: Фарм через Kamino даёт 40% APR — [SOL,APT]
```
### 📁 Структура проекта
```bash
tg-summary-bot/
│
├── bot.py              # основной код бота
├── .env.example        # пример конфигурации
├── .gitignore          # игнорируемые файлы
├── requirements.txt    # зависимости
└── README.md           # описание проекта
```
### 📁 Требования

- Python 3.11+

- Aiogram 3.22+

- OpenAI SDK 2.1.0+

- APScheduler 3.11.0+

- SQLite (входит в стандартную библиотеку)

### 🧩 Пример .env.example
```bash
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
CHAT_ID=-1001234567890
```

### 🧑‍💻 Автор

https://github.com/dant1k

Telegram: https://t.me/chat1k_summarizer_bot


### 🪪 Лицензия

MIT License © 2025 dant1k

## 🔄 Update — October 2025

### 🧠 Version: DM Summaries Mode
**Description:**  
Bot now sends all daily and manual summaries **directly to your DM**, instead of posting them in group chats.  
He quietly collects messages in groups where he is a member — no admin rights required.

**Changes:**
- All `/commands` work **only in private chat** with the bot  
- `/summary_now <chat_id>` sends a 24-hour digest in DM  
- `/auto_on` enables daily digest at 09:00  
- `/auto_off` disables automation  
- Supports grouping by user, tickers (`$APT`, `$SOL`), and links  
- Cleaner message formatting for easier reading  

**How to update (already done for you):**
```bash
git pull origin main
launchctl kickstart -k gui/$UID/com.tgsummary.bot
```

🚀 Coming next

🧩 User-mode watcher (Telethon) — to read closed chats where only your personal account is a member

🧰 Web dashboard for chat analytics

📊 Inline graphs of activity per token / user
