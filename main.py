"""Main entry point for the emoji cropper bot."""

import os
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

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

    application = Application.builder().token(settings.BOT_TOKEN).request(request).build()
    print(application)
    logger.info("Telegram application created successfully")

    handlers = BotHandlers()
    logger.info("Bot handlers initialized")

    logger.info("Registering command handlers")
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("emoji_cropper", handlers.emoji_cropper))
    logger.info("Command handlers registered: /start, /help, /emoji_cropper")

    logger.info("Registering message and callback handlers")
    application.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handlers.handle_document))
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

    logger.info("Starting bot polling")
    application.run_polling()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Bot crashed with error: {e}", exc_info=True)
        raise
