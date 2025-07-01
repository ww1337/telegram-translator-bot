import logging
import os
from PIL import Image
import pytesseract

from telegram import Update
# Обратите внимание на эту строку импорта - здесь нет 'Application'
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from googletrans import Translator

# --- НАСТРОЙКИ ---

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменной окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("Не найден токен! Установите переменную окружения TELEGRAM_TOKEN")

# Инициализируем переводчик
translator = Translator()

# --- ФУНКЦИИ-ОБРАБОТЧИКИ (синтаксис для v13) ---

def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    update.message.reply_html(
        f"Привет, {user.mention_html()}!\n\n"
        f"Я — бот-переводчик. Отправь мне текст, и я переведу его на русский или английский.\n\n"
        f"А если отправишь картинку с текстом, я распознаю его и тоже переведу!",
    )

def handle_text(update: Update, context: CallbackContext) -> None:
    """Обрабатывает и переводит текстовые сообщения."""
    user_text = update.message.text
    translated_text, src_lang, dest_lang = translate_text_logic(user_text)

    if src_lang != "error":
        update.message.reply_text(
            f"Перевод ({src_lang} → {dest_lang}):\n\n{translated_text}"
        )
    else:
        update.message.reply_text(translated_text)

def handle_photo(update: Update, context: CallbackContext) -> None:
    """Обрабатывает фотографии, распознает текст и переводит его."""
    user_id = update.effective_user.id
    temp_photo_path = f"temp_photo_{user_id}.jpg"
    
    try:
        # Для v13 используется .download() вместо .download_to_drive()
        photo_file = update.message.photo[-1].get_file()
        photo_file.download(temp_photo_path)
        
        update.message.reply_text("Картинка получена. Начинаю распознавание...")

        recognized_text = pytesseract.image_to_string(Image.open(temp_photo_path), lang='rus+eng')

        if not recognized_text.strip():
            update.message.reply_text(
                "Не удалось распознать текст на картинке. Попробуйте другое изображение."
            )
            return

        update.message.reply_text(f"Распознанный текст:\n\n`{recognized_text}`", parse_mode='Markdown')
        
        translated_text, src_lang, dest_lang = translate_text_logic(recognized_text)
        
        if src_lang != "error":
            update.message.reply_text(
                f"Перевод ({src_lang} → {dest_lang}):\n\n{translated_text}"
            )
        else:
            update.message.reply_text(translated_text)

    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        update.message.reply_text("Произошла ошибка при обработке изображения.")
    finally:
        if os.path.exists(temp_photo_path):
            os.remove(temp_photo_path)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def translate_text_logic(text: str) -> tuple[str, str, str]:
    """Основная логика перевода."""
    if not text.strip():
        return "Нечего переводить.", "none", "none"
        
    try:
        detected = translator.detect(text)
        src_lang = detected.lang
        dest_lang = 'en' if src_lang == 'ru' else 'ru'
        translated = translator.translate(text, dest=dest_lang, src=src_lang)
        return translated.text, src_lang, dest_lang
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        return "Не удалось перевести текст.", "error", "error"

# --- ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА БОТА ---

def main() -> None:
    """Запуск бота."""
    # Используем Updater и Dispatcher
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    # Добавляем обработчики
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo))

    # Запускаем бота
    logger.info("Бот запускается...")
    updater.start_polling()
    updater.idle()
    logger.info("Бот остановлен.")

if __name__ == '__main__':
    main()
