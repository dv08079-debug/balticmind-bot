#!/usr/bin/env python3
"""
BalticMind AI Telegram Bot
Умный ассистент который отвечает клиентам на LV/EN/RU
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional

# pip install python-telegram-bot anthropic
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

# ── НАСТРОЙКИ ──
TELEGRAM_TOKEN = "8331411241:AAGJpj7iny8GTNs15RWS1yW3Q5bgQGQTvZA"
ANTHROPIC_KEY  = "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"
MANAGER_CHAT_ID = "8411091757"  # Куда пересылать горячие лиды

# ── СИСТЕМНЫЙ ПРОМПТ ──
SYSTEM_PROMPT = """Ты — AI-ассистент компании BalticMind. 
Ты помогаешь клиентам узнать об услугах компании и записаться на консультацию.

О КОМПАНИИ:
- BalticMind — AI-автоматизация для бизнеса в Латвии, Эстонии и Литве
- Три направления: автоматизация бизнес-процессов, виртуальные ассистенты/чат-боты, консалтинг по цифровой трансформации
- Работаем на латышском, русском, английском, эстонском, литовском языках
- Пилотный проект запускаем за 4-6 недель
- Бесплатный экспресс-аудит для новых клиентов
- Сайт: balticmind.lv
- Email: hello@balticmind.lv

ЦЕНЫ (ориентировочно):
- Бесплатный аудит: 0€ (2 часа, без обязательств)
- Пилотный проект: от 4900€
- Масштабирование: по договорённости

ПРАВИЛА ОБЩЕНИЯ:
1. Определи язык клиента и отвечай на том же языке (LV/EN/RU)
2. Будь дружелюбным, профессиональным, кратким
3. Если клиент хочет записаться — спроси имя, компанию, email, удобное время
4. Если вопрос очень сложный или технический — скажи что передашь специалисту
5. Никогда не придумывай цены или факты которых не знаешь
6. Заканчивай разговор предложением записаться на бесплатный аудит

ВАЖНО: Ты представляешь реальную компанию. Будь точным и честным."""

# ── ХРАНИЛИЩЕ ДИАЛОГОВ ──
conversations = {}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


def get_conversation(user_id: int) -> list:
    """Получить историю диалога пользователя"""
    if user_id not in conversations:
        conversations[user_id] = []
    return conversations[user_id]


def add_message(user_id: int, role: str, content: str):
    """Добавить сообщение в историю"""
    conv = get_conversation(user_id)
    conv.append({"role": role, "content": content})
    # Храним последние 20 сообщений
    if len(conv) > 20:
        conversations[user_id] = conv[-20:]


async def get_ai_response(user_id: int, user_message: str) -> str:
    """Получить ответ от Claude"""
    add_message(user_id, "user", user_message)
    
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=get_conversation(user_id)
        )
        
        ai_reply = response.content[0].text
        add_message(user_id, "assistant", ai_reply)
        return ai_reply
        
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return "Извините, произошла техническая ошибка. Пожалуйста, напишите нам напрямую: hello@balticmind.lv"


async def notify_manager(bot, user_info: dict, message: str):
    """Уведомить менеджера о горячем лиде"""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    text = (
        f"🔥 *Горячий лид в Telegram!*\n\n"
        f"👤 Имя: {user_info.get('name', '—')}\n"
        f"🆔 Username: @{user_info.get('username', '—')}\n"
        f"💬 Сообщение: _{message}_\n"
        f"⏰ Время: {now}\n\n"
        f"📱 Chat ID: `{user_info.get('id')}`"
    )
    try:
        await bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Manager notify error: {e}")


# ── ОБРАБОТЧИКИ ──

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_id = user.id
    
    # Сбросить историю
    conversations[user_id] = []
    
    # Приветствие
    welcome = (
        f"👋 Sveiki / Hello / Здравствуйте!\n\n"
        f"Я AI-ассистент компании *BalticMind* 🤖\n\n"
        f"Помогу вам узнать об автоматизации бизнеса с помощью ИИ, "
        f"расскажу о наших услугах и запишу на бесплатную консультацию.\n\n"
        f"Пишите на любом языке — латышском 🇱🇻, английском 🇬🇧 или русском 🇷🇺\n\n"
        f"Чем могу помочь?"
    )
    
    await update.message.reply_text(welcome, parse_mode='Markdown')
    
    # Уведомить менеджера о новом пользователе
    await notify_manager(context.bot, {
        'name': user.full_name,
        'username': user.username or 'нет',
        'id': user.id
    }, "🆕 Новый пользователь начал диалог")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /reset — сбросить диалог"""
    user_id = update.effective_user.id
    conversations[user_id] = []
    await update.message.reply_text(
        "✅ Диалог сброшен. Начнём сначала!\n\nЧем могу помочь?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных сообщений"""
    user = update.effective_user
    user_message = update.message.text
    
    # Показать что бот печатает
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )
    
    # Проверить на горячие слова
    hot_keywords = [
        'записаться', 'консультация', 'хочу', 'интересует', 'цена', 'стоимость',
        'appointment', 'interested', 'price', 'cost', 'contact',
        'pierakstīties', 'interesē', 'cena', 'vēlos'
    ]
    is_hot = any(kw in user_message.lower() for kw in hot_keywords)
    
    # Получить ответ AI
    response = await get_ai_response(user.id, user_message)
    
    # Отправить ответ
    await update.message.reply_text(response)
    
    # Уведомить менеджера если горячий лид
    if is_hot:
        await notify_manager(context.bot, {
            'name': user.full_name,
            'username': user.username or 'нет',
            'id': user.id
        }, user_message)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(f"Error: {context.error}")


# ── ЗАПУСК ──

def main():
    print("🚀 BalticMind AI Bot запускается...")
    print(f"📱 Telegram Token: {TELEGRAM_TOKEN[:20]}...")
    print(f"🤖 Claude API: подключён")
    print(f"👤 Manager ID: {MANAGER_CHAT_ID}")
    print("─" * 40)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    
    # Сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Ошибки
    app.add_error_handler(error_handler)
    
    print("✅ Бот запущен! Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
