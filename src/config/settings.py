"""Application settings and configuration."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application configuration settings."""

    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    TEMP_DIR_PREFIX: str = "temp_"
    MAX_COLS = 11
    MAX_CELLS = 120
    SELECT_PERCENTAGES = [1.0, 0.75, 0.5, 0.35, 0.25, 0.15]
    MIN_ASPECT_RATIO = 0.30

    @classmethod
    def validate(cls):
        """Validate required settings."""
        from src.config.logger import get_logger
        logger = get_logger()

        logger.info("Validating application settings")
        logger.info(f"BOT_TOKEN present: {bool(cls.BOT_TOKEN)}")
        logger.debug(f"TEMP_DIR_PREFIX: {cls.TEMP_DIR_PREFIX}")

        if not cls.BOT_TOKEN:
            logger.error("BOT_TOKEN not found in environment variables")
            raise ValueError("BOT_TOKEN not found in environment variables")

        logger.info("Settings validation successful")


settings = Settings()
