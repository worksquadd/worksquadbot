"""Main entry point for the emoji cropper bot."""

import os
import shutil
import tempfile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, PicklePersistence, filters

from src.config import settings
from src.config.logger import setup_logger
from src.bot.handlers import BotHandlers
from telegram.request import HTTPXRequest


request = HTTPXRequest(
    connection_pool_size=8,
    read_timeout=60.0,
    write_timeout=60.0,
    connect_timeout=30.0,
    pool_timeout=10.0
)

logger = setup_logger()


def cleanup_stale_media_dirs():
    """Remove orphaned media_* temp dirs left by a previous run (kill -9 skips finally-cleanup)."""
    stale = [
        os.path.join(tempfile.gettempdir(), name)
        for name in os.listdir(tempfile.gettempdir())
        if name.startswith("media_")
    ]
    for path in stale:
        shutil.rmtree(path, ignore_errors=True)
    if stale:
        logger.warning(f"Cleaned up {len(stale)} orphaned media temp dir(s): {stale}")
    else:
        logger.info("No orphaned media temp dirs found")


def main():
    """Start the bot."""
    logger.info("Starting emoji cropper bot application")

    try:
        logger.info("Validating configuration settings")
        settings.validate()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.critical(f"Configuration validation failed: {e}")
        raise

    logger.info("Building Telegram application")
    cleanup_stale_media_dirs()

    if settings.is_local_mode():
        logger.info("Using self-hosted Local Bot API: url=%s, 2GB uploads enabled", settings.TELEGRAM_LOCAL_BASE_URL)
        local_request = HTTPXRequest(
            connection_pool_size=8,
            read_timeout=300.0,
            write_timeout=300.0,
            connect_timeout=30.0,
            pool_timeout=10.0
        )
        application = (
            Application.builder()
            .token(settings.BOT_TOKEN)
            .base_url(settings.TELEGRAM_LOCAL_BASE_URL)
            .base_file_url(settings.TELEGRAM_LOCAL_FILE_BASE_URL)
            .local_mode(True)
            .request(local_request)
            .persistence(PicklePersistence(filepath=settings.PERSISTENCE_FILE))
            .concurrent_updates(True)
            .build()
        )
    else:
        logger.info("Using standard Telegram Bot API")
        if settings.MEDIA_MAX_FILE_MB > 48:
            logger.warning(
                f"Clamping MEDIA_MAX_FILE_MB from {settings.MEDIA_MAX_FILE_MB} to 48: "
                "standard Bot API has a 50MB upload limit and Local Bot API is not configured"
            )
            settings.MEDIA_MAX_FILE_MB = 48
        application = (
            Application.builder()
            .token(settings.BOT_TOKEN)
            .request(request)
            .persistence(PicklePersistence(filepath=settings.PERSISTENCE_FILE))
            .concurrent_updates(True)
            .build()
        )
    logger.info("Telegram application created successfully")

    handlers = BotHandlers()
    logger.info("Bot handlers initialized")

    logger.info("Registering command handlers")
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("emoji_cropper", handlers.emoji_cropper))
    logger.info("Command handlers registered: /start, /help, /emoji_cropper")

    logger.info("Registering message and callback handlers")
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO, handlers.handle_photo))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.Document.IMAGE | filters.Document.VIDEO | filters.Document.MimeType("image/gif")), handlers.handle_document))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.VIDEO, handlers.handle_video))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.ANIMATION, handlers.handle_animation))
    application.add_handler(
        CallbackQueryHandler(handlers.handle_command_callback, pattern="^cmd_")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.handle_grid_selection, pattern="^grid_")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.handle_padding_selection, pattern="^padding_")
    )
    logger.info("Message and callback handlers registered")

    group_emoji_filter = filters.ChatType.GROUPS & filters.Regex(
        rf"(?i)^\s*@{settings.BOT_USERNAME}\s+emojicrop\s*$"
    )
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.PHOTO & filters.CaptionRegex(
        rf"(?i)^\s*@{settings.BOT_USERNAME}\s+emojicrop\s*$"
    ), handlers.handle_group_photo_emojicrop))
    application.add_handler(MessageHandler(group_emoji_filter & filters.REPLY, handlers.handle_group_reply_emojicrop))
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & filters.Regex(rf"(?i)^\s*@{settings.BOT_USERNAME}\s+"),
        handlers.handle_media_link,
    ))
    logger.info("Registered explicit group mention handlers")

    logger.info("Registering private media link handler")
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            handlers.handle_media_link
        )
    )
    logger.info("Registered private media link handler")

    logger.info("Registering emoji ad tracker handler")
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            handlers.track_emoji_message
        ),
        group=1,
    )
    logger.info("Registered emoji ad tracker handler")

    logger.info("Registering media quality callback handler")
    application.add_handler(
        CallbackQueryHandler(handlers.handle_media_quality, pattern="^mediaq:")
    )
    logger.info("Registered media quality callback handler")

    logger.info("Starting bot polling")
    application.run_polling()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Bot crashed with error: {e}", exc_info=True)
        raise
