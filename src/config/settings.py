"""Application settings and configuration."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application configuration settings."""

    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    TEMP_DIR_PREFIX: str = "temp_"
    MAX_COLS = 15
    MAX_CELLS = 120
    SELECT_PERCENTAGES = [1.0, 0.75, 0.5, 0.35, 0.25, 0.15]
    MIN_ASPECT_RATIO = 0.30
    MEDIA_DOWNLOAD_TIMEOUT_SEC: int = int(os.getenv("MEDIA_DOWNLOAD_TIMEOUT_SEC", "3600"))
    MEDIA_MAX_FILE_MB: int = min(1900, max(10, int(os.getenv("MEDIA_MAX_FILE_MB", "1900"))))
    MEDIA_IG_COOKIES_FILE: str = os.getenv("MEDIA_IG_COOKIES_FILE", "/app/ig-cookies.txt")
    MEDIA_YT_PLAYER_CLIENT: str = os.getenv("MEDIA_YT_PLAYER_CLIENT", "android")
    MEDIA_YT_POT_BASEURL: str = os.getenv("MEDIA_YT_POT_BASEURL", "http://bgutil:4416")
    MEDIA_MAX_PARTS: int = int(os.getenv("MEDIA_MAX_PARTS", "40"))
    MEDIA_CONCURRENT_PER_USER: int = int(os.getenv("MEDIA_CONCURRENT_PER_USER", "16"))
    MEDIA_CONCURRENT_TOTAL: int = int(os.getenv("MEDIA_CONCURRENT_TOTAL", "16"))
    MEDIA_YT_CONCURRENT_FRAGMENTS: int = int(os.getenv("MEDIA_YT_CONCURRENT_FRAGMENTS", "4"))
    TELEGRAM_API_ID: str = os.getenv("TELEGRAM_API_ID", "")
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_LOCAL_BASE_URL: str = os.getenv("TELEGRAM_LOCAL_BASE_URL", "http://telegram-bot-api:8081/bot")
    TELEGRAM_LOCAL_FILE_BASE_URL: str = os.getenv("TELEGRAM_LOCAL_FILE_BASE_URL", "http://telegram-bot-api:8081/file/bot")
    PERSISTENCE_FILE: str = os.getenv("PERSISTENCE_FILE", "/app/temp/bot_data.pkl")

    @classmethod
    def is_local_mode(cls) -> bool:
        """Return True when self-hosted Local Bot API credentials are configured."""
        return bool(cls.TELEGRAM_API_ID and cls.TELEGRAM_API_HASH)

    @classmethod
    def validate(cls):
        """Validate required settings."""
        from src.config.logger import get_logger
        logger = get_logger()

        logger.info("Validating application settings")
        logger.info(f"BOT_TOKEN present: {bool(cls.BOT_TOKEN)}")
        logger.debug(f"TEMP_DIR_PREFIX: {cls.TEMP_DIR_PREFIX}")
        logger.debug(f"MEDIA_DOWNLOAD_TIMEOUT_SEC: {cls.MEDIA_DOWNLOAD_TIMEOUT_SEC}")
        logger.debug(f"MEDIA_MAX_FILE_MB: {cls.MEDIA_MAX_FILE_MB}")
        logger.debug(f"MEDIA_IG_COOKIES_FILE: {cls.MEDIA_IG_COOKIES_FILE}, present: {os.path.exists(cls.MEDIA_IG_COOKIES_FILE)}")
        logger.debug(f"MEDIA_YT_PLAYER_CLIENT: {cls.MEDIA_YT_PLAYER_CLIENT}")
        logger.debug(f"MEDIA_MAX_PARTS: {cls.MEDIA_MAX_PARTS}")
        logger.debug(f"TELEGRAM_API_ID present: {bool(cls.TELEGRAM_API_ID)}")
        logger.debug(f"TELEGRAM_API_HASH present: {bool(cls.TELEGRAM_API_HASH)}")
        logger.debug(f"TELEGRAM_LOCAL_BASE_URL: {cls.TELEGRAM_LOCAL_BASE_URL}")
        logger.info(f"Local Bot API mode: {cls.is_local_mode()}")
        if not cls.is_local_mode() and cls.MEDIA_MAX_FILE_MB > 48:
            logger.warning(
                f"Standard Bot API mode: 50MB upload limit applies, "
                f"MEDIA_MAX_FILE_MB={cls.MEDIA_MAX_FILE_MB} will be clamped to 48 at startup"
            )

        if not cls.BOT_TOKEN:
            logger.error("BOT_TOKEN not found in environment variables")
            raise ValueError("BOT_TOKEN not found in environment variables")

        logger.info("Settings validation successful")


settings = Settings()
