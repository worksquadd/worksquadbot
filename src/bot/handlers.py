"""Telegram bot handlers coordinator."""

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.commands import StartCommand, HelpCommand, EmojiCropperCommand
from src.bot.commands.media_downloader import MediaDownloaderCommand
from src.bot.group_mentions import is_emojicrop_request
from src.config.logger import get_logger

logger = get_logger()


class BotHandlers:
    """Coordinator for bot commands and callbacks."""

    def __init__(self):
        """Initialize bot handlers and command instances."""
        logger.info("Initializing BotHandlers")
        self.start_command = StartCommand()
        self.help_command = HelpCommand()
        self.emoji_cropper_command = EmojiCropperCommand()
        self.media_downloader = MediaDownloaderCommand()
        logger.info("BotHandlers initialized successfully")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /start command.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} executed /start command")
        await self.start_command.handle(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /help command.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} executed /help command")
        await self.help_command.handle(update, context)

    async def emoji_cropper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /emoji_cropper command.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} executed /emoji_cropper command")
        await self.emoji_cropper_command.start(update, context)

    async def handle_media_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle private text messages with media links.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} sent private message, routing to media downloader")
        await self.media_downloader.handle(update, context)

    async def handle_media_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle quality choice callbacks for pending YouTube links.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.callback_query.from_user.id if update.callback_query else "Unknown"
        logger.info(f"User {user_id} sent quality callback, routing to media downloader")
        await self.media_downloader.handle_quality(update, context)

    async def handle_group_photo_emojicrop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Crop a group photo only when its caption explicitly mentions this bot."""
        if not is_emojicrop_request(update.effective_message.caption):
            return
        logger.info(f"User {update.effective_user.id} requested group photo emoji crop")
        await self.emoji_cropper_command.handle_photo(update, context)

    async def handle_group_reply_emojicrop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Crop the photo that an explicit group emojicrop request replies to."""
        message = update.effective_message
        target = message.reply_to_message
        if not is_emojicrop_request(message.text) or not target or not target.photo:
            return
        logger.info(f"User {update.effective_user.id} requested group reply emoji crop")
        await self.emoji_cropper_command.handle_photo(update, context, source_message=target)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming photos.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} uploaded a photo")
        await self.emoji_cropper_command.handle_photo(update, context)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming documents.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} uploaded a document")
        await self.emoji_cropper_command.handle_document(update, context)

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming videos.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} uploaded a video")
        await self.emoji_cropper_command.handle_video(update, context)

    async def handle_animation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming animations (GIFs).

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} uploaded an animation")
        await self.emoji_cropper_command.handle_animation(update, context)

    async def handle_command_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle command button callbacks from main menu.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        query = update.callback_query
        command = query.data.replace("cmd_", "")
        user_id = update.effective_user.id if update.effective_user else "Unknown"

        logger.info(f"User {user_id} selected menu command: {command}")

        if command == "start":
            await self.start_command.handle_callback(update, context)
        elif command == "help":
            await self.help_command.handle_callback(update, context)
        elif command == "emoji_cropper":
            await self.emoji_cropper_command.start(update, context)

    async def handle_grid_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle grid size selection.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        query = update.callback_query
        grid_size = query.data.replace("grid_", "")
        user_id = update.effective_user.id if update.effective_user else "Unknown"

        logger.info(f"User {user_id} selected grid size: {grid_size}")
        await self.emoji_cropper_command.handle_grid_selection(update, context)

    async def handle_padding_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle padding selection and process image.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        query = update.callback_query
        padding = query.data.replace("padding_", "")
        user_id = update.effective_user.id if update.effective_user else "Unknown"

        logger.info(f"User {user_id} selected padding: {padding}")
        await self.emoji_cropper_command.handle_padding_selection(update, context)
