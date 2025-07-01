import logging
import os
from PIL import Image
import pytesseract

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from googletrans import Translator

# --- НАСТРОЙКИ ---

# Включаем логирование, чтобы видеть ошибки в терминале
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен бота из переменной окружения.
# Это безопасный способ хранения токена.
# Перед запуском нужно будет установить эту переменную в вашем терминале.
# Для Linux/macOS: export TELEGRAM_TOKEN="ВАШ_ТОКЕН"
# Для Windows: set TELEGRAM_TOKEN="ВАШ_ТОКЕН"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    # Если токен не найден, бот не запустится и выдаст ошибку
    raise ValueError("Не найден токен! Установите переменную окружения TELEGRAM_TOKEN")

# --- ВАЖНО для Windows ---
# Если Tesseract установлен не в стандартный путь, раскомментируйте и укажите путь к tesseract.exe
# Например:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Инициализируем переводчик один раз, чтобы не создавать его при каждом сообщении
translator = Translator()


# --- ФУНКЦИИ-ОБРАБОТЧИКИ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start. Отправляет приветственное сообщение."""
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\n\n"
        f"Я — бот-переводчик. Отправь мне текст, и я переведу его на русский или английский.\n\n"
        f"А если отправишь картинку с текстом, я распознаю его и тоже переведу!",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает и переводит текстовые сообщения."""
    user_text = update.message.text
    translated_text, src_lang, dest_lang = translate_text_logic(user_text)

    if src_lang != "error":
        await update.message.reply_text(
            f"Перевод ({src_lang} → {dest_lang}):\n\n{translated_text}"
        )
    else:
        # Если произошла ошибка при переводе
        await update.message.reply_text(translated_text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает фотографии, распознает текст и переводит его."""
    user_id = update.effective_user.id
    temp_photo_path = f"temp_photo_{user_id}.jpg"
    
    try:
        # Получаем файл фото самого высокого качества
        photo_file = await update.message.photo[-1].get_file()

        # Скачиваем фото во временный файл
        await photo_file.download_to_drive(temp_photo_path)
        
        await update.message.reply_text("Картинка получена. Начинаю распознавание...")

        # Распознаем текст с помощью Tesseract для русского и английского языков
        recognized_text = pytesseract.image_to_string(Image.open(temp_photo_path), lang='rus+eng')

        if not recognized_text.strip():
            await update.message.reply_text(
                "Не удалось распознать текст на картинке. Попробуйте другое изображение "
                "с более четким текстом."
            )
            return

        # Отправляем пользователю распознанный текст для проверки
        await update.message.reply_text(f"Распознанный текст:\n\n`{recognized_text}`", parse_mode='Markdown')
        
        # Переводим распознанный текст
        translated_text, src_lang, dest_lang = translate_text_logic(recognized_text)
        
        if src_lang != "error":
            await update.message.reply_text(
                f"Перевод ({src_lang} → {dest_lang}):\n\n{translated_text}"
            )
        else:
            await update.message.reply_text(translated_text)

    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await update.message.reply_text("Произошла ошибка при обработке изображения. Пожалуйста, попробуйте позже.")
    finally:
        # Удаляем временный файл после обработки, даже если была ошибка
        if os.path.exists(temp_photo_path):
            os.remove(temp_photo_path)


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def translate_text_logic(text: str) -> tuple[str, str, str]:
    """
    Основная логика перевода.
    Возвращает кортеж: (переведенный_текст, исходный_язык, язык_перевода).
    """
    if not text.strip():
        return "Нечего переводить. Пожалуйста, отправьте текст.", "none", "none"
        
    try:
        # Определяем исходный язык
        detected = translator.detect(text)
        src_lang = detected.lang
        
        # Логика переключения языка: если текст русский, переводим на английский.
        # В любом другом случае — переводим на русский.
        dest_lang = 'en' if src_lang == 'ru' else 'ru'
        
        translated = translator.translate(text, dest=dest_lang, src=src_lang)
        return translated.text, src_lang, dest_lang
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        return "Не удалось перевести текст. Возможно, проблема с API переводчика.", "error", "error"


# --- ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА БОТА ---

def main() -> None:
    """Запуск бота и настройка обработчиков."""
    # Создаем объект приложения с вашим токеном
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчики для разных типов сообщений
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Запускаем бота в режиме опроса (polling)
    logger.info("Бот запускается...")
    application.run_polling()
    logger.info("Бот остановлен.")


if __name__ == "__main__":
    main()
