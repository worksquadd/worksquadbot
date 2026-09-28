"""Strict parsing for the bot's opt-in group message workflows."""

import re

from src.config import settings


def is_bot_mention(text: str | None) -> bool:
    """Return whether text starts with this bot's Telegram username."""
    return bool(text and re.match(rf"^\s*@{re.escape(settings.BOT_USERNAME)}(?:\s|$)", text, re.IGNORECASE))


def strip_bot_mention(text: str) -> str:
    """Remove one leading bot mention, leaving the requested payload."""
    return re.sub(rf"^\s*@{re.escape(settings.BOT_USERNAME)}\s*", "", text, count=1, flags=re.IGNORECASE).strip()


def is_emojicrop_request(text: str | None) -> bool:
    """Return whether text is exactly an explicit group emoji-crop request."""
    return bool(text and re.fullmatch(rf"\s*@{re.escape(settings.BOT_USERNAME)}\s+emojicrop\s*", text, re.IGNORECASE))
