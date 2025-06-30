import os
import logging
from io import BytesIO

import pytesseract
from googletrans import Translator
from PIL import Image

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- НАСТРОЙКА ---
# Теперь нужен только токен от Telegram
# Не забудьте установить его через: export TELEGRAM_TOKEN="ВАШ_ТЕЛЕГРАМ_ТОКЕН"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Настройка логирования для отладки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ЛОГИКА ПЕРЕВОДА И РАСПОЗНАВАНИЯ ---

def translate_text(text: str, dest_lang: str = 'ru') -> str:
    """
    Переводит текст с помощью Google Translate.
    """
    if not text or not text.strip():
        return "Нечего переводить."
    try:
        translator = Translator()
        # Определяем язык оригинала и переводим
        detected = translator.detect(text)
        translation = translator.translate(text, dest=dest_lang, src=detected.lang)
        return translation.text
    except Exception as e:
        logger.error(f"Ошибка во время перевода: {e}")
        return "Произошла ошибка при обращении к сервису перевода."

def ocr_and_translate_image(image: Image.Image) -> str:
    """
    Распознает текст на изображении с помощью Tesseract и переводит его.
    """
    try:
        # Распознаем текст, используя английский и русский языки
        extracted_text = pytesseract.image_to_string(image, lang='rus+eng')

        if not extracted_text or not extracted_text.strip():
            return "Не удалось распознать текст на изображении."

        # Переводим распознанный текст
        translated_text = translate_text(extracted_text)

        # Возвращаем и оригинал, и перевод для удобства
        return f"**Распознанный текст:**\n`{extracted_text.strip()}`\n\n**Перевод:**\n`{translated_text}`"

    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract не установлен или не найден в системном PATH.")
        return ("Критическая ошибка: Программа Tesseract OCR не установлена на сервере. "
                "Выполните команду: sudo apt install tesseract-ocr")
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        return "Произошла непредвиденная ошибка при обработке изображения."

# --- ОБРАБОТЧИКИ КОМАНД TELEGRAM ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user_name = update.message.from_user.first_name
    await update.message.reply_text(
        f"Привет, {user_name}!\n\n"
        "Я бот-переводчик на базе Google Translate.\n\n"
        "➡️ Отправь мне любой текст, и я переведу его на русский.\n\n"
        "🖼️ Отправь картинку с текстом, и я распознаю его и тоже переведу."
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения для перевода."""
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action='typing')

    translation = translate_text(user_text)
    # Отправляем с форматированием Markdown для красоты
    await update.message.reply_text(translation, parse_mode='Markdown')

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщения с фотографиями для распознавания и перевода текста."""
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action='typing')

    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_stream = BytesIO()
        await photo_file.download_to_memory(photo_stream)
        photo_stream.seek(0)

        image = Image.open(photo_stream)
        
        ocr_result = ocr_and_translate_image(image)
        await update.message.reply_text(ocr_result, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при получении фото: {e}")
        await update.message.reply_text("Не удалось загрузить или обработать изображение.")

# --- ОСНОВНАЯ ЧАСТЬ ЗАПУСКА БОТА ---

async def post_init(application: Application):
    """Установка команд меню после запуска."""
    await application.bot.set_my_commands([
        BotCommand("start", "🚀 Перезапустить бота")
    ])

def main():
    """Основная функция для запуска бота."""
    if not TELEGRAM_TOKEN:
        logger.error("Токен Telegram не найден! Установите переменную окружения TELEGRAM_TOKEN.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()
