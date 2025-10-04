<p align="center">
  <img src="https://raw.githubusercontent.com/dant1k/tg-summary-bot/main/assets/preview.png" width="640" alt="TG Summary Bot preview (coming soon)">
</p>

<h1 align="center">🧩 TG Crypto Chat Summarizer Bot</h1>
<p align="center">
  <b>AI-powered Telegram bot for summarizing crypto chats with $tickers, links, and daily reports directly to your DM.</b><br>
  Built with <a href="https://github.com/aiogram/aiogram">Aiogram</a> + <a href="https://platform.openai.com/">OpenAI</a>
</p>

### 🤖 Overview
This Telegram bot automatically collects messages from crypto-related group chats and generates **daily summaries** with key ideas, tokens, and links.

It’s built to analyze discussion activity, extract $tickers, and deliver a clean daily report directly to your DM.  
The bot can be connected to multiple chats, runs autonomously, and doesn’t need admin rights.

---

## ⚙️ Features
- 🧠 **Smart aggregation** — groups messages by user and combines their ideas  
- 💬 **Ticker detection** — highlights tokens like `$APT`, `$SOL`, `$PYTH`  
- 🔗 **Link recognition** — includes pump.fun / dex links or any mentioned URLs  
- 📆 **Automatic daily summaries** — runs every morning at 09:00  
- 🕹️ **Manual trigger** — request a summary any time with `/summary_now <chat_id>`  
- 💌 **Private delivery** — reports are sent directly to your DM, not into the group  
- 🧩 **Multi-chat mode** — supports multiple Telegram groups at once  

---

## 🧭 Commands (available only in DM)
| Command | Description |
|----------|--------------|
| `/start` | Show main menu and help |
| `/list` | List all active chats |
| `/subscribe <chat_id>` | Enable message collection from a chat |
| `/unsubscribe <chat_id>` | Disable collection from a chat |
| `/summary_now <chat_id>` | Generate a 24-hour digest right now |
| `/auto_on` | Enable daily summaries (09:00) |
| `/auto_off` | Disable auto summaries |

💡 **Note:** Add the bot as a member (not admin) to the chat.  
Then manage everything privately via DM.

---

## 🧰 Installation

```bash
# clone and enter project
git clone https://github.com/dant1k/tg-summary-bot.git
cd tg-summary-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# create .env
touch .env
.env example:

ini
Копировать код
BOT_TOKEN=1234567890:ABCDEFxxxxxxxxxxxx
USER_ID=1219407635
OPENAI_API_KEY=sk-xxxx
🔄 Update — October 2025
🧠 Version: DM Summaries Mode
Description:
Bot now sends all daily and manual summaries directly to your DM, instead of posting them in group chats.
He quietly collects messages in groups where he is a member — no admin rights required.

Changes:

All /commands work only in private chat with the bot

/summary_now <chat_id> sends a 24-hour digest in DM

/auto_on enables daily digest at 09:00

/auto_off disables automation

Supports grouping by user, tickers ($APT, $SOL), and links

Cleaner message formatting for easier reading

How to update (already done for you):

bash
Копировать код
git pull origin main
launchctl kickstart -k gui/$UID/com.tgsummary.bot
<<<<<<< HEAD
```

🚀 Coming next
=======
🚀 Coming Next
🧩 User-mode watcher (Telethon) — read closed chats where only your main account is a member
>>>>>>> 8d2b9d5 (docs: english version of README)

🧰 Web dashboard — visualize chat activity and top tokens

📊 Analytics graphs — daily message stats, sentiment, and engagement

🧑‍💻 Author
Maintained by @dant1k
Telegram: @chat1k_summarizer_bot


✅ Status: Stable and running via launchd on macOS.
Summaries delivered privately, logs in bot.log, configs in .env.
