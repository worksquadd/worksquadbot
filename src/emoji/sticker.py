"""Sticker pack creation and management."""

import time
from typing import List
from telegram import Bot, InputSticker
from telegram.constants import StickerFormat

from src.config.logger import get_logger

logger = get_logger()


class StickerPackCreator:
    """Handles creation of custom emoji sticker packs."""

    def __init__(self, bot: Bot):
        """
        Initialize sticker pack creator.

        Args:
            bot: Telegram bot instance
        """
        self.bot = bot
        logger.info(f"StickerPackCreator initialized with bot: {bot.username}")

    async def create_emoji_pack(
        self,
        user_id: int,
        emoji_files: List[str],
        pack_title: str = None
    ) -> tuple[str, List[str]]:
        """
        Create custom emoji sticker pack.

        Args:
            user_id: Telegram user ID
            emoji_files: List of paths to emoji images
            pack_title: Custom pack title

        Returns:
            Tuple of (URL to the created emoji pack, list of custom emoji IDs)
        """
        logger.info(f"User {user_id} creating emoji pack with {len(emoji_files)} stickers")

        timestamp = int(time.time())
        pack_name = f"emoji_{user_id}_{timestamp}_by_{self.bot.username}"
        logger.info(f"User {user_id} pack name: {pack_name}")

        if not pack_title:
            pack_title = f"Emoji Pack {timestamp}"

        logger.info(f"User {user_id} pack title: {pack_title}")

        logger.info(f"User {user_id} preparing stickers for pack")
        stickers = []
        for idx, emoji_path in enumerate(emoji_files):
            logger.debug(f"User {user_id} loading sticker {idx+1}/{len(emoji_files)}: {emoji_path}")
            with open(emoji_path, "rb") as img_file:
                sticker = InputSticker(
                    sticker=img_file.read(),
                    emoji_list=["😀"],
                )
                stickers.append(sticker)

        logger.info(f"User {user_id} calling Telegram API to create sticker set")
        emoji_ids = []
        try:
            await self.bot.create_new_sticker_set(
                user_id=user_id,
                name=pack_name,
                title=pack_title,
                stickers=stickers[:1],
                sticker_type="custom_emoji",
                sticker_format=StickerFormat.STATIC
            )
            for sticker in stickers[1:]:
                await self.bot.add_sticker_to_set(
                    user_id=user_id,
                    name=pack_name,
                    sticker=sticker
                )
            logger.info(f"User {user_id} sticker set created successfully")

            logger.info(f"User {user_id} fetching sticker set via raw API")
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{self.bot.token}/getStickerSet",
                    params={"name": pack_name}
                )
                response_data = response.json()
                logger.info(f"User {user_id} raw API response: {response_data}")

                if response_data.get("ok") and "result" in response_data:
                    stickers_data = response_data["result"].get("stickers", [])
                    emoji_ids = [s.get("custom_emoji_id") for s in stickers_data if s.get("custom_emoji_id")]
                    logger.info(f"User {user_id} extracted {len(emoji_ids)} custom emoji IDs")
                else:
                    logger.warning(f"User {user_id} failed to get sticker set from API")

        except Exception as e:
            logger.error(f"User {user_id} failed to create sticker set: {e}", exc_info=True)
            raise

        pack_url = f"https://t.me/addemoji/{pack_name}"
        logger.info(f"User {user_id} pack URL: {pack_url}")

        return pack_url, emoji_ids
