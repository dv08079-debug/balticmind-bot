#!/usr/bin/env python3

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, List

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import anthropic
from dotenv import load_dotenv

# ────────────── ЗАГРУЗКА ENV ──────────────
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID")

if not TELEGRAM_TOKEN or not ANTHROPIC_KEY:
    raise ValueError("❌ TELEGRAM_TOKEN или ANTHROPIC_API_KEY не заданы!")

# ────────────── ЛОГИ ──────────────
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ────────────── CLAUDE CLIENT ──────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

MODEL = "claude-3-5-haiku-20241022"

SYSTEM_PROMPT = """Ты — AI-ассистент компании BalticMind.
Отвечай кратко, профессионально и на языке клиента.
Всегда предлагай бесплатный аудит.
"""

conversations: Dict[int, List[dict]] = {}


def get_conversation(user_id: int):
    if user_id not in conversations:
        conversations[user_id] = []
    return conversations[user_id]


async def get_ai_response(user_id: int, user_message: str):
    get_conversation(user_id).append({"role": "user", "content": user_message})

    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model=MODEL,
            max_tokens=700,
            system=SYSTEM_PROMPT,
            messages=get_conversation(user_id),
        )

        reply = response.content[0].text
        conversations[user_id].append({"role": "assistant", "content": reply})

        # хранить последние 20 сообщений
        conversations[user_id] = conversations[user_id][-20:]

        return reply

    except Exception as e:
        logger.error(f"Claude error: {e}")
        return "Произошла техническая ошибка. Напишите нам: hello@balticmind.lv"


# ────────────── TELEGRAM HANDLERS ──────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []

    await update.message.reply_text(
        "👋 Привет! Я AI-ассистент BalticMind.\n\n"
        "Расскажу про автоматизацию бизнеса и запишу на аудит.\n\n"
        "Чем могу помочь?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing",
    )

    reply = await get_ai_response(user.id, text)
    await update.message.reply_text(reply)

    # уведомление менеджера если горячий лид
    hot_words = ["цена", "стоимость", "консультация", "interested", "price"]
    if any(word in text.lower() for word in hot_words):
        await notify_manager(context.bot, user, text)


async def notify_manager(bot, user, message):
    if not MANAGER_CHAT_ID:
        return

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    text = (
        f"🔥 Горячий лид!\n\n"
        f"Имя: {user.full_name}\n"
        f"Username: @{user.username}\n"
        f"Сообщение: {message}\n"
        f"Время: {now}"
    )

    try:
        await bot.send_message(chat_id=MANAGER_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"Manager notify error: {e}")


async def error_handler(update, context):
    logger.error(f"Telegram error: {context.error}")


# ────────────── MAIN ──────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("🚀 BalticMind bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
