import os
import asyncio
import logging
from io import BytesIO

import google.generativeai as genai
from PIL import Image
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- НАСТРОЙКА ---
# Загрузите ваши ключи из переменных окружения для безопасности
# В терминале перед запуском выполните:
# export TELEGRAM_TOKEN="ВАШ_ТЕЛЕГРАМ_ТОКЕН"
# export GEMINI_API_KEY="ВАШ_GEMINI_API_КЛЮЧ"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка логирования для отладки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ЛОГИКА GEMINI ---

async def get_gemini_response(prompt_text: str, image: Image.Image = None) -> str:
    """
    Получает ответ от модели Gemini. Может обрабатывать как текст, так и текст с изображением.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Для распознавания текста с картинки используем мультимодальную модель
        if image:
            model = genai.GenerativeModel('gemini-1.5-pro-latest')
            response = await model.generate_content_async([prompt_text, image])
        # Для простого перевода текста можно использовать более быструю модель
        else:
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            response = await model.generate_content_async(prompt_text)
            
        return response.text

    except Exception as e:
        logger.error(f"Ошибка при обращении к Gemini API: {e}")
        return "Произошла ошибка при обращении к искусственному интеллекту. Попробуйте позже."

# --- ОБРАБОТЧИКИ КОМАНД TELEGRAM ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user_name = update.message.from_user.first_name
    await update.message.reply_text(
        f"Привет, {user_name}!\n\n"
        "Я бот-переводчик на базе Gemini.\n\n"
        "➡️ Просто отправь мне любой текст, и я переведу его на русский.\n\n"
        "🖼️ Или отправь картинку с текстом, и я распознаю его и тоже переведу."
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения для перевода."""
    user_text = update.message.text
    chat_id = update.message.chat_id
    
    # Показываем статус "печатает..."
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    prompt = f"Переведи следующий текст на русский язык:\n\n\"{user_text}\""
    
    translation = await get_gemini_response(prompt)
    await update.message.reply_text(translation)

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщения с фотографиями для распознавания и перевода текста."""
    chat_id = update.message.chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    try:
        # Получаем фото лучшего качества
        photo_file = await update.message.photo[-1].get_file()
        
        # Скачиваем фото в память
        photo_stream = BytesIO()
        await photo_file.download_to_memory(photo_stream)
        photo_stream.seek(0)
        
        # Открываем изображение с помощью Pillow
        image = Image.open(photo_stream)
        
        prompt = "Распознай весь текст на этом изображении и переведи его на русский язык. Если текста нет, так и напиши."
        
        ocr_translation = await get_gemini_response(prompt, image)
        await update.message.reply_text(ocr_translation)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await update.message.reply_text("Не удалось обработать изображение. Пожалуйста, попробуйте другое.")

# --- ОСНОВНАЯ ЧАСТЬ ЗАПУСКА БОТА ---

async def post_init(application: Application):
    """Действия после инициализации бота (установка команд меню)."""
    await application.bot.set_my_commands([
        BotCommand("start", "🚀 Перезапустить бота")
    ])

def main():
    """Основная функция для запуска бота."""
    if not TELEGRAM_TOKEN:
        logger.error("Токен Telegram не найден! Установите переменную окружения TELEGRAM_TOKEN.")
        return
    if not GEMINI_API_KEY:
        logger.error("Ключ Gemini API не найден! Установите переменную окружения GEMINI_API_KEY.")
        return

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()
