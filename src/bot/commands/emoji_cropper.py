"""Emoji cropper command handler."""

import os
import shutil
from telegram import Update
from telegram.ext import ContextTypes

from src.config import strings, settings
from src.config.logger import get_logger
from src.bot.keyboards import KeyboardBuilder
from src.emoji.processor import ImageProcessor
from src.emoji.sticker import StickerPackCreator

logger = get_logger()


class EmojiCropperCommand:
    """Handle emoji cropper functionality."""

    def __init__(self):
        """Initialize emoji cropper command handler."""
        logger.info("Initializing EmojiCropperCommand")
        self.processor = ImageProcessor()
        self.keyboard_builder = KeyboardBuilder()
        logger.info(f"EmojiCropperCommand initialized with emoji size")

    def _format_emoji_grid(self, emoji_ids: list, cols: int, rows: int) -> str:
        """
        Format custom emoji IDs into a grid layout.

        Args:
            emoji_ids: List of custom emoji IDs
            cols: Number of columns
            rows: Number of rows

        Returns:
            Formatted emoji grid string
        """
        grid_lines = []
        for row in range(rows):
            row_emojis = []
            for col in range(cols):
                idx = row * cols + col
                if idx < len(emoji_ids):
                    row_emojis.append(f'<tg-emoji emoji-id="{emoji_ids[idx]}">🎨</tg-emoji>')
            grid_lines.append("".join(row_emojis))
        return "\n".join(grid_lines)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Start emoji cropper flow.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.info(f"User {user_id} started emoji cropper flow")

        reply_markup = self.keyboard_builder.build_back_to_menu()

        if update.message:
            logger.debug(f"User {user_id} started via message")
            await update.message.reply_text(
                strings.EMOJI_CROPPER_START,
                reply_markup=reply_markup
            )
        elif update.callback_query:
            logger.debug(f"User {user_id} started via callback")
            await update.callback_query.edit_message_text(
                strings.EMOJI_CROPPER_START,
                reply_markup=reply_markup
            )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming photos for emoji cropping.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id
        logger.info(f"User {user_id} uploading photo for processing")

        photo = update.message.photo[-1]
        logger.debug(f"User {user_id} photo file_id: {photo.file_id}, size: {photo.file_size} bytes")

        logger.info(f"User {user_id} downloading photo from Telegram")
        file = await photo.get_file()

        temp_dir = f"{settings.TEMP_DIR_PREFIX}{user_id}"
        os.makedirs(temp_dir, exist_ok=True)
        logger.debug(f"User {user_id} created temp directory: {temp_dir}")

        image_path = os.path.join(temp_dir, "input.jpg")
        logger.info(f"User {user_id} saving photo to: {image_path}")
        await file.download_to_drive(image_path)
        logger.info(f"User {user_id} photo downloaded successfully")

        context.user_data["image_path"] = image_path
        context.user_data["temp_dir"] = temp_dir

        logger.info(f"User {user_id} getting image dimensions")
        width, height = self.processor.get_image_dimensions(image_path)
        logger.info(f"User {user_id} image dimensions: {width}x{height}")

        logger.info(f"User {user_id} calculating suggested grid sizes")
        suggested_grids = self.processor.suggest_grid_sizes(width, height)
        logger.info(f"User {user_id} suggested grids: {suggested_grids}")

        reply_markup = self.keyboard_builder.build_grid_selection(suggested_grids)

        await update.message.reply_text(
            strings.ASK_GRID_SIZE.format(width=width, height=height),
            reply_markup=reply_markup
        )
        logger.info(f"User {user_id} presented with grid selection options")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming documents for emoji cropping.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id
        logger.info(f"User {user_id} uploading document for processing")

        document = update.message.document
        mime_type = document.mime_type
        logger.debug(f"User {user_id} document file_id: {document.file_id}, mime_type: {mime_type}, size: {document.file_size} bytes")

        if mime_type not in ["image/png", "image/webp"]:
            logger.warning(f"User {user_id} uploaded unsupported document type: {mime_type}")
            await update.message.reply_text(strings.UNSUPPORTED_FILE_FORMAT)
            return

        logger.info(f"User {user_id} downloading document from Telegram")
        file = await document.get_file()

        temp_dir = f"{settings.TEMP_DIR_PREFIX}{user_id}"
        os.makedirs(temp_dir, exist_ok=True)
        logger.debug(f"User {user_id} created temp directory: {temp_dir}")

        extension = "png" if mime_type == "image/png" else "webp"
        image_path = os.path.join(temp_dir, f"input.{extension}")
        logger.info(f"User {user_id} saving document to: {image_path}")
        await file.download_to_drive(image_path)
        logger.info(f"User {user_id} document downloaded successfully")

        context.user_data["image_path"] = image_path
        context.user_data["temp_dir"] = temp_dir

        logger.info(f"User {user_id} getting image dimensions")
        width, height = self.processor.get_image_dimensions(image_path)
        logger.info(f"User {user_id} image dimensions: {width}x{height}")

        logger.info(f"User {user_id} calculating suggested grid sizes")
        suggested_grids = self.processor.suggest_grid_sizes(width, height)
        logger.info(f"User {user_id} suggested grids: {suggested_grids}")

        reply_markup = self.keyboard_builder.build_grid_selection(suggested_grids)

        await update.message.reply_text(
            strings.ASK_GRID_SIZE.format(width=width, height=height),
            reply_markup=reply_markup
        )
        logger.info(f"User {user_id} presented with grid selection options")

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
        user_id = update.effective_user.id if update.effective_user else "Unknown"

        query = update.callback_query
        await query.answer()

        grid_data = query.data.replace("grid_", "")
        cols, rows = map(int, grid_data.split("x"))
        logger.info(f"User {user_id} selected grid size: {cols}x{rows}")

        context.user_data["grid_size"] = (cols, rows)

        reply_markup = self.keyboard_builder.build_padding_selection()

        await query.edit_message_text(
            strings.ASK_PADDING,
            reply_markup=reply_markup
        )
        logger.info(f"User {user_id} presented with padding selection options")

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
        user_id = update.effective_user.id

        query = update.callback_query
        await query.answer()

        padding = int(query.data.replace("padding_", ""))
        logger.info(f"User {user_id} selected padding: {padding}")

        await query.edit_message_text(strings.PROCESSING)
        logger.info(f"User {user_id} starting image processing")

        image_path = context.user_data.get("image_path")
        temp_dir = context.user_data.get("temp_dir")
        grid_size = context.user_data.get("grid_size")

        if not image_path or not grid_size:
            logger.error(f"User {user_id} missing required data - image_path: {bool(image_path)}, grid_size: {bool(grid_size)}")
            await query.edit_message_text(strings.ERROR_PROCESSING)
            return

        logger.info(f"User {user_id} processing with grid_size={grid_size}, padding={padding}")

        try:
            output_dir = os.path.join(temp_dir, "emojis")
            logger.info(f"User {user_id} cropping image to grid")
            cropped_files = self.processor.crop_to_grid(
                image_path,
                output_dir,
                grid_size,
                padding
            )
            logger.info(f"User {user_id} created {len(cropped_files)} emoji files")

            await query.edit_message_text(strings.CREATING_PACK)
            logger.info(f"User {user_id} creating sticker pack")

            sticker_creator = StickerPackCreator(context.bot)
            emoji_link, emoji_ids = await sticker_creator.create_emoji_pack(
                user_id=user_id,
                emoji_files=cropped_files
            )
            logger.info(f"User {user_id} sticker pack created successfully: {emoji_link}")

            cols, rows = grid_size
            emoji_grid = self._format_emoji_grid(emoji_ids, cols, rows)
            logger.info(f"User {user_id} formatted {len(emoji_ids)} emojis into {cols}x{rows} grid")

            reply_markup = self.keyboard_builder.build_back_to_menu()

            await query.edit_message_text(
                strings.SUCCESS.format(link=emoji_link, grid=emoji_grid),
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            logger.info(f"User {user_id} cleaning up temp directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"User {user_id} temp directory cleaned up successfully")

        except Exception as e:
            logger.error(f"User {user_id} error during processing: {e}", exc_info=True)
            reply_markup = self.keyboard_builder.build_back_to_menu()

            await query.edit_message_text(
                strings.ERROR_CREATING_PACK,
                reply_markup=reply_markup
            )

            if temp_dir and os.path.exists(temp_dir):
                logger.info(f"User {user_id} cleaning up temp directory after error: {temp_dir}")
                shutil.rmtree(temp_dir, ignore_errors=True)
