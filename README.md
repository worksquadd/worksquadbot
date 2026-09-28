# САМЫЙ ЛУЧШИЙ БОТ В ИСТОРИИ ТЕЛЕГРАМА
by
- tima
- vanya
- maratik
- qrutomitya
- rassel
- mishanya

## Emoji Image Cropper Bot

Telegram bot that automatically crops images into custom emoji packs.

### Features

- Upload any image
- Automatically suggests grid sizes based on image aspect ratio
- Choose custom grid size (2x2, 3x3, 4x4, etc.)
- Adjustable padding between emoji pieces
- Automatic emoji pack creation
- Get shareable link instantly

### Quick Start

1. Copy environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your bot token from [@BotFather](https://t.me/BotFather):
```
BOT_TOKEN=your_bot_token_here
```

3. Run with Docker Compose:
```bash
docker-compose up -d
```

### Usage

1. Start bot with `/start`
2. Send any image
3. Choose grid size (how many parts to cut)
4. Choose padding (spacing between emoji pieces)
5. Get your emoji pack link!

### Development

Run locally without Docker:
```bash
pip install -r requirements.txt
python main.py
```

### Project Structure

```
src/
├── bot/
│   ├── handlers.py    # Bot command and callback handlers
│   └── keyboards.py   # Inline keyboard builders
├── emoji/
│   ├── processor.py   # Image cropping and processing
│   └── sticker.py     # Sticker pack creation
└── config/
    ├── settings.py    # Application configuration
    └── strings.py     # Bot messages and text
main.py               # Entry point
```

## 📥 Media downloader

Отправьте боту в личку ссылку — он скачает медиа и отправит вам готовым файлом.

Поддерживаются: YouTube (watch/shorts/live/youtu.be), Instagram (посты, reels, tv), VK (видео и клипы), TikTok (видео и короткие ссылки vm/vt.tiktok.com).

### Cookies для Instagram

Instagram требует авторизацию:

1. Экспортируйте `cookies.txt` браузерным расширением (например, Get cookies.txt LOCALLY)
2. Положите файл по пути из `MEDIA_IG_COOKIES_FILE` (по умолчанию `/app/ig-cookies.txt`)
3. Для docker-compose добавьте read-only mount (пример закомментирован):

```yaml
# volumes:
#   - ./ig-cookies.txt:/app/ig-cookies.txt:ro
```

### Настройки

- `MEDIA_DOWNLOAD_TIMEOUT_SEC` — таймаут скачивания в секундах (по умолчанию 3600)
- `MEDIA_MAX_FILE_MB` — максимальный размер одного файла/части видео в МБ (по умолчанию 1900 с Local Bot API, в стандартном режиме бот сам урезает до 48)
- `MEDIA_MAX_PARTS` — максимальное число частей видео для отправки (по умолчанию 40)
- `MEDIA_IG_COOKIES_FILE` — путь к cookies-файлу Instagram
- `MEDIA_YT_PLAYER_CLIENT` — player client для YouTube (по умолчанию `android`)

Бот скачивает видео любого размера (до 10 часов). Если файл больше `MEDIA_MAX_FILE_MB`, он без перекодирования режется на части (ffmpeg `-c copy`) и отправляется отдельными документами.

### Local Bot API (2ГБ)

Стандартный Bot API ограничивает отправку ~50 МБ. Self-hosted Local Bot API поднимает лимит до 2 ГБ на файл: видео до ~3 часов отправляется целиком, разбивка на части остаётся только для файлов больше 2 ГБ.

Как включить:

1. Получите `api_id` и `api_hash` на [my.telegram.org](https://my.telegram.org) (раздел «API development tools»)
2. Запишите их в `.env`: `TELEGRAM_API_ID=...` и `TELEGRAM_API_HASH=...`
3. Запустите `docker compose up -d` — сервис `telegram-bot-api` поднимется вместе с ботом

Без `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` бот работает через стандартный Bot API с лимитом ~50 МБ, а `MEDIA_MAX_FILE_MB` автоматически урезается до 48 при старте.

Файлы Local Bot API хранятся в папке `bot-api-data/` (не удалять).
