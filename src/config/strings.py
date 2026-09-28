"""String constants for the bot."""

START_MESSAGE = (
    "👋 Привет! Выберите команду из меню ниже:\n\n"
    "🖼️ Emoji Cropper - создать эмодзи-пак из картинки\n"
    "ℹ️ Help - получить справку\n\n"
    "Или используйте команды напрямую: /emoji_cropper, /help"
)

EMOJI_CROPPER_START = (
    "🖼️ Emoji Cropper\n\n"
    "Отправьте мне изображение или видео, и я разрежу его на эмодзи!\n\n"
    "💡 Совет: Для сохранения прозрачности отправляйте PNG или WebP как документ.\n"
    "🎬 Видео: MP4, GIF или WebM (макс. 3 сек)"
)

GRID_WHOLE_IMAGE = "1 эмодзи (вся картинка)"

ASK_GRID_SIZE = (
    "📐 Выбери размер сетки для разрезания картинки:\n\n"
    "Картинка будет разрезана на {width}x{height} частей"
)

ASK_PADDING = (
    "📏 Выбери отступ между эмодзи (padding):\n\n"
    "минимальный\n"
    "маленький\n"
    "средний\n"
    "большой\n"
    "максимальный"
)

PROCESSING = "⏳ Обрабатываю изображение..."

CREATING_PACK = "📦 Создаю эмодзи-пак..."

SUCCESS = (
    "✅ Готово! Эмодзи-пак создан!\n\n"
    "{grid}\n\n"
    "🔗 Ссылка: {link}\n\n"
    "Нажмите на ссылку чтобы добавить эмодзи-пак и использовать их в своих сообщениях."
)

ERROR_PROCESSING = "❌ Ошибка при обработке изображения. Попробуйте другую картинку."

ERROR_CREATING_PACK = "❌ Ошибка при создании эмодзи-пака. Попробуйте позже."

ERROR_INVALID_PADDING = "❌ Неверное значение. Выберите от 1 до 5."

UNSUPPORTED_FILE_FORMAT = "❌ Неподдерживаемый формат файла.\n\n📷 Изображения: PNG, WebP\n🎬 Видео: MP4, WebM, GIF"

UNSUPPORTED_VIDEO_FORMAT = "❌ Неподдерживаемый формат видео. Отправьте MP4, WebM или GIF."

PROCESSING_VIDEO = "🎬 Конвертирую видео в WebM..."

HELP_MESSAGE = (
    "ℹ️ Как использовать бота:\n\n"
    "📋 Доступные команды:\n"
    "/start - главное меню\n"
    "/emoji_cropper - создать эмодзи-пак\n"
    "/help - показать эту справку\n\n"
    "🖼️ Emoji Cropper:\n"
    "1. Отправьте картинку или видео\n"
    "2. Выберите размер сетки (NxM)\n"
    "3. Выберите отступ\n"
    "4. Получите ссылку на эмодзи-пак!\n\n"
    "💡 Для прозрачных эмодзи отправляйте PNG/WebP как документ.\n"
    "🎬 Видео: MP4, GIF, WebM (макс. 3 сек)"
)

GRID_OPTIONS = {
    "2x2": "2x2 (4 эмодзи)",
    "3x3": "3x3 (9 эмодзи)",
    "4x4": "4x4 (16 эмодзи)",
    "5x5": "5x5 (25 эмодзи)",
    "3x2": "3x2 (6 эмодзи)",
    "4x3": "4x3 (12 эмодзи)",
}

PADDING_OPTIONS = {
    "1": "1 - Минимальный",
    "2": "2 - Маленький",
    "3": "3 - Средний",
    "4": "4 - Большой",
    "5": "5 - Максимальный",
}

MENU_BUTTONS = {
    "emoji_cropper": "🖼️ Emoji Cropper",
    "help": "ℹ️ Help",
    "back_to_menu": "◀️ Back to Menu",
}

DOWNLOADING = "⏳ Скачиваю медиа..."
QUEUE_ADDED = "⏳ Ставлю в очередь, скоро начну качать."

ERROR_ALREADY_DOWNLOADING = "⏳ Уже качаю твою предыдущую ссылку, подожди!"

ERROR_DOWNLOAD_FAILED = "❌ Не смог скачать это медиа. Возможно ссылка битая или платформа изменилась."

ERROR_DOWNLOAD_TIMEOUT = "⌛ Скачивание заняло слишком много времени. Попробуй позже."

ERROR_IG_AUTH = "🔒 Instagram требует авторизацию. Добавь cookies-файл (см. README) и перезапусти бота."

MEDIA_SENDING_PART = "📨 Отправляю часть {current}/{total}..."

MEDIA_PARTS_TRUNCATED = "⚠️ Видео очень большое — отправлены только первые {total} частей."

MEDIA_PARTS_FAILED = "⚠️ Не удалось отправить {count} из {total} частей."

MEDIA_CAPTION = "🍿 worksquad"

QUALITY_PROMPT = "🎬 Выбери качество видео:"
QUALITY_ETA = " · ~{eta}"
QUALITY_ETA_SECONDS = "{seconds} с"
QUALITY_ETA_MINUTES = "{minutes} мин"
BUTTON_QUALITY_BEST = "⭐ Лучшее"
BUTTON_QUALITY_1080 = "📹 1080p"
BUTTON_QUALITY_720 = "📹 720p"
BUTTON_QUALITY_480 = "📹 480p"
BUTTON_QUALITY_AUDIO = "🎵 Только звук (MP3)"
QUALITY_LABEL_BEST = "в лучшем качестве"
QUALITY_LABEL_1080 = "в 1080p"
QUALITY_LABEL_720 = "в 720p"
QUALITY_LABEL_480 = "в 480p"
QUALITY_LABEL_AUDIO = "как MP3"
DOWNLOADING_QUALITY = "⏳ Скачиваю {quality}..."
ERROR_QUALITY_UNKNOWN = "⏳ Эта ссылка устарела (бот перезапускался). Отправь ссылку ещё раз 🙏"
