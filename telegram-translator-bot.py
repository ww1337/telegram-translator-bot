import logging
import os
from PIL import Image
import pytesseract
import cv2 # Добавляем импорт OpenCV

from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from googletrans import Translator

# --- НАСТРОЙКИ ---

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("Не найден токен! Установите переменную окружения TELEGRAM_TOKEN")

translator = Translator()

# --- ФУНКЦИИ-ОБРАБОТЧИКИ ---

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    update.message.reply_html(
        f"Привет, {user.mention_html()}!\n\n"
        f"Я — бот-переводчик. Отправь мне текст, и я переведу его на русский или английский.\n\n"
        f"А если отправишь картинку с текстом, я распознаю его и тоже переведу!",
    )

def handle_text(update: Update, context: CallbackContext) -> None:
    user_text = update.message.text
    translated_text, src_lang, dest_lang = translate_text_logic(user_text)

    if src_lang != "error":
        update.message.reply_text(
            f"Перевод ({src_lang} → {dest_lang}):\n\n{translated_text}"
        )
    else:
        update.message.reply_text(translated_text)

def handle_photo(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает фотографии с применением продвинутой предобработки для лучшего распознавания.
    """
    user_id = update.effective_user.id
    temp_photo_path = f"temp_photo_{user_id}.jpg"
    
    try:
        photo_file = update.message.photo[-1].get_file()
        photo_file.download(temp_photo_path)
        
        update.message.reply_text("Картинка получена. Применяю магию и распознаю...")

        # --- ШАГИ ПРОДВИНУТОЙ ПРЕДОБРАБОТКИ ---
        # 1. Читаем изображение с помощью OpenCV
        image = cv2.imread(temp_photo_path)
        
        # 2. Преобразуем в оттенки серого
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 3. Применяем бинаризацию с методом Оцу.
        #    Это самый важный шаг! Он превращает изображение в чисто черно-белое.
        _, binary_image = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        
        # 4. (Опционально, но полезно) Можно инвертировать изображение, если текст светлый на темном фоне
        # inverted_image = cv2.bitwise_not(binary_image)
        # В большинстве случаев обычная бинаризация работает лучше.

        # --- УЛУЧШЕННОЕ РАСПОЗНАВАНИЕ ---
        # Передаем в Tesseract уже идеально обработанную картинку
        custom_config = r'--oem 3 --psm 6'
        recognized_text = pytesseract.image_to_string(binary_image, lang='rus+eng', config=custom_config)

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

def translate_text_logic(text: str) -> tuple[str, str, str]:
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

def main() -> None:
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo))

    logger.info("Бот запускается с улучшенным распознаванием...")
    updater.start_polling()
    updater.idle()
    logger.info("Бот остановлен.")

if __name__ == '__main__':
    main()
