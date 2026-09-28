"""Pure link detection for whitelisted media platforms."""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+")

SCHEMELESS_RE = re.compile(
    r"(?:(?:www|m|music)\.)?(?:youtube\.com|youtu\.be|instagram\.com|vk\.com|vk\.ru|vkvideo\.ru|tiktok\.com)/\S+",
    re.IGNORECASE,
)

PLATFORM_PATTERNS = {
    "youtube": re.compile(
        r"^https?://(?:www\.|m\.|music\.)?youtube\.com/(?:watch\?[^\s]*v=[\w-]+[^\s]*|shorts/[\w-]+[^\s]*|live/[\w-]+[^\s]*)$"
        r"|^https?://(?:www\.|m\.|music\.)?youtu\.be/[\w-]+[^\s]*$",
        re.IGNORECASE,
    ),
    "instagram": re.compile(
        r"^https?://(?:www\.|m\.)?instagram\.com/(?:p|reel|reels|tv|share)/(?:[\w-]+[^\s]*)$",
        re.IGNORECASE,
    ),
    "vk": re.compile(
        r"^https?://(?:www\.|m\.)?vk\.(?:com|ru)/(?:video|clip)[\w.-]*[^\s]*$"
        r"|^https?://(?:www\.|m\.)?vkvideo\.ru/(?:video|clip)[\w.-]*[^\s]*$",
        re.IGNORECASE,
    ),
    "tiktok": re.compile(
        r"^https?://(?:www\.)?tiktok\.com/@[\w.-]+/(?:video|photo)/\d+[^\s]*$"
        r"|^https?://(?:vm|vt)\.tiktok\.com/[\w]+[^\s]*$",
        re.IGNORECASE,
    ),
}

TRAILING_PUNCTUATION = ".,!?:;\"'()[]"


def clean_url(url: str) -> str:
    """Strip trailing punctuation from a URL repeatedly."""
    url = url.strip()
    while url and url[-1] in TRAILING_PUNCTUATION:
        url = url[:-1]
    return url


def extract_media_link(text: str) -> Optional[Tuple[str, str]]:
    """Return (platform, url) if text is exactly one whitelisted URL, else None."""
    text = text.strip()
    urls = URL_RE.findall(text)
    logger.debug(f"extract_media_link: found {len(urls)} URL(s) in text")
    if len(urls) > 1:
        logger.debug(f"extract_media_link: expected at most 1 URL, got {len(urls)}, returning None")
        return None
    if urls:
        url = clean_url(urls[0])
    else:
        candidates = SCHEMELESS_RE.findall(text)
        if len(candidates) != 1:
            logger.debug(f"extract_media_link: no single schemeless candidate ({len(candidates)}), returning None")
            return None
        url = clean_url(candidates[0])
        if not url.lower().startswith("http"):
            url = f"https://{url}"
    logger.debug(f"extract_media_link: cleaned url: {url}")
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.fullmatch(url):
            logger.debug(f"extract_media_link: matched platform '{platform}' for url '{url}'")
            return platform, url
    logger.debug(f"extract_media_link: url '{url}' did not match any platform pattern")
    return None
