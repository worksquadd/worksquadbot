"""Media downloader command handler."""

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import time
from math import ceil
from typing import List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, MessageEntity
from telegram.error import TelegramError, RetryAfter
from telegram.ext import ContextTypes

from src.config import strings, settings
from src.config.logger import get_logger
from src.bot.group_mentions import is_bot_mention, strip_bot_mention
from src.media.downloader import (
    MediaResult,
    download_media,
    DownloadError,
    AuthRequiredError,
    DownloadTimeoutError,
)
from src.media.links import extract_media_link

logger = get_logger()

YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|live/)([\w-]{5,})")
YT_THUMB_URL = "https://i.ytimg.com/vi/{id}/hqdefault.jpg"

QUALITY_BUTTONS = [
    (strings.BUTTON_QUALITY_BEST, "mediaq:best"),
    (strings.BUTTON_QUALITY_1080, "mediaq:1080"),
    (strings.BUTTON_QUALITY_720, "mediaq:720"),
    (strings.BUTTON_QUALITY_480, "mediaq:480"),
    (strings.BUTTON_QUALITY_AUDIO, "mediaq:audio"),
]

QUALITY_LABELS = {
    "best": strings.QUALITY_LABEL_BEST,
    "1080": strings.QUALITY_LABEL_1080,
    "720": strings.QUALITY_LABEL_720,
    "480": strings.QUALITY_LABEL_480,
    "audio": strings.QUALITY_LABEL_AUDIO,
}

QUALITY_FORMATS = {
    "best": "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo+bestaudio/best",
    "1080": "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[acodec^=mp4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720": "bestvideo[vcodec^=avc1][height<=720]+bestaudio[acodec^=mp4a]/bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480": "bestvideo[vcodec^=avc1][height<=480]+bestaudio[acodec^=mp4a]/bestvideo[height<=480]+bestaudio/best[height<=480]",
    "audio": "audio",
}


async def _available_yt_qualities(url: str) -> dict[int, int]:
    """Return available H.264 heights mapped to an approximate merged file size."""
    cmd = [
        sys.executable, "-m", "yt_dlp", url, "--no-playlist", "--skip-download",
        "--dump-single-json", "--socket-timeout", "15",
    ]
    extractor_args = [f"getpot_bgutil_baseurl={settings.MEDIA_YT_POT_BASEURL}"]
    if settings.MEDIA_YT_PLAYER_CLIENT:
        extractor_args.append(f"player_client={settings.MEDIA_YT_PLAYER_CLIENT}")
    cmd.extend(["--extractor-args", "youtube:" + ";".join(extractor_args)])
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            return {}
        formats = json.loads(stdout).get("formats", [])
        audio_sizes = [
            item.get("filesize") or item.get("filesize_approx") or 0
            for item in formats
            if item.get("vcodec") == "none" and str(item.get("acodec", "")).startswith("mp4a")
        ]
        audio_size = max(audio_sizes, default=0)
        qualities: dict[int, int] = {}
        for item in formats:
            height = item.get("height")
            if not height or not str(item.get("vcodec", "")).startswith("avc1"):
                continue
            video_size = item.get("filesize") or item.get("filesize_approx") or 0
            if video_size:
                qualities[height] = max(qualities.get(height, 0), video_size + audio_size)
        return qualities
    except (asyncio.TimeoutError, FileNotFoundError, ValueError, json.JSONDecodeError):
        return {}


def _format_eta(size_bytes: Optional[int]) -> str:
    """Estimate server download plus upload time from a conservative 8 MiB/s rate."""
    if not size_bytes:
        return ""
    seconds = max(8, ceil(size_bytes / (8 * 1024 * 1024) + 5))
    if seconds < 60:
        eta = strings.QUALITY_ETA_SECONDS.format(seconds=seconds)
    else:
        eta = strings.QUALITY_ETA_MINUTES.format(minutes=ceil(seconds / 60))
    return strings.QUALITY_ETA.format(eta=eta)


def _extract_yt_id(url: str) -> Optional[str]:
    """Extract a YouTube video id from a whitelisted URL."""
    match = YT_ID_RE.search(url)
    return match.group(1) if match else None


def _extract_yt_thumb(url: str) -> Optional[str]:
    """Return a YouTube preview thumbnail URL for the link, if the id is recognised."""
    video_id = _extract_yt_id(url)
    return YT_THUMB_URL.format(id=video_id) if video_id else None


class MediaDownloaderCommand:
    """Handle media link downloads in private chats."""

    def __init__(self):
        """Initialize media downloader command handler."""
        self.logger = get_logger()
        self._user_sems: dict[int, asyncio.Semaphore] = {}
        self._global_sem = asyncio.Semaphore(settings.MEDIA_CONCURRENT_TOTAL)
        self.logger.info(
            f"Initializing MediaDownloaderCommand: per_user={settings.MEDIA_CONCURRENT_PER_USER}, "
            f"total={settings.MEDIA_CONCURRENT_TOTAL}"
        )

    def _user_sem(self, user_id: int) -> asyncio.Semaphore:
        """Return the per-user concurrency semaphore, creating it on first use."""
        return self._user_sems.setdefault(user_id, asyncio.Semaphore(settings.MEDIA_CONCURRENT_PER_USER))

    def _is_queued(self, user_id: int) -> bool:
        """Return True when this download would have to wait for a free slot."""
        return self._user_sem(user_id).locked() or self._global_sem.locked()

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle a private text message containing a supported media link.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        user_id = update.effective_user.id
        text = update.effective_message.text
        self.logger.info(f"User {user_id} sent private text message, checking for media link")

        if update.effective_chat.type != "private":
            if not is_bot_mention(text):
                self.logger.debug(f"User {user_id} group message does not mention the bot")
                return
            text = strip_bot_mention(text)
        extracted = extract_media_link(text)
        if extracted is None:
            self.logger.debug(f"User {user_id} message contains no supported media link")
            return

        platform, url = extracted
        self.logger.info(f"User {user_id} media link detected: platform={platform}, url={url}")

        if platform == "youtube":
            await self._offer_quality(update, context, url)
            return

        queued = self._is_queued(user_id)
        status = await update.effective_message.reply_text(
            strings.QUEUE_ADDED if queued else strings.DOWNLOADING
        )
        self.logger.info(f"User {user_id} download status message sent, queued={queued}")
        await self._download_and_deliver(update, context, platform, url, status, None)

    async def track_emoji_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Remember the last private message containing custom emojis.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        message = update.effective_message
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        text = (message.text or message.caption or "") if message else ""
        entities = list(message.entities or []) + list(message.caption_entities or []) if message else []
        has_custom_emoji = any(e.type == "custom_emoji" for e in entities)
        has_signature = "🎨worksquadbot🎨" in text
        if not has_custom_emoji and not has_signature:
            return
        custom_entities = [
            {"type": "custom_emoji", "offset": e.offset, "length": e.length, "custom_emoji_id": e.custom_emoji_id}
            for e in entities if e.type == "custom_emoji" and e.custom_emoji_id
        ]
        context.chat_data["emoji_caption"] = {"text": text, "entities": custom_entities}
        self.logger.info(
            f"User {user_id} saved emoji caption from message {message.message_id}: "
            f"entities={len(custom_entities)}, text={text[:50]!r}"
        )

    def _build_caption(self, context: ContextTypes.DEFAULT_TYPE) -> tuple[str, Optional[list]]:
        """
        Build media caption from the user's last custom emoji message.

        Args:
            context: Context for the handler

        Returns:
            Tuple of (caption text, custom emoji entities or None)
        """
        stored = context.chat_data.get("emoji_caption")
        if not stored or not stored.get("entities"):
            return strings.MEDIA_CAPTION, None
        entities = [
            MessageEntity(type=e["type"], offset=e["offset"], length=e["length"], custom_emoji_id=e["custom_emoji_id"])
            for e in stored["entities"]
        ]
        self.logger.info(f"Using saved emoji caption with {len(entities)} custom emoji")
        return stored["text"], entities

    async def _forward_emoji_ad(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Forward the user's last custom emoji message after a successful download.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        ad = context.chat_data.get("last_emoji_ad")
        user_id = update.effective_user.id
        if not ad:
            self.logger.debug(f"User {user_id} has no saved emoji ad, skipping forward")
            return
        try:
            await context.bot.forward_message(
                chat_id=ad["chat_id"],
                from_chat_id=ad["chat_id"],
                message_id=ad["message_id"],
            )
            self.logger.info(f"User {user_id} emoji ad forwarded after media delivery")
        except Exception as e:
            self.logger.warning(f"User {user_id} emoji ad forward failed (deleted?): {e}")

    async def handle_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle a quality choice callback for a pending YouTube link.

        Args:
            update: Telegram update object
            context: Context for the handler
        """
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()
        self.logger.info(f"User {user_id} quality callback: {query.data}")

        key = query.data.split(":", 1)[1] if ":" in (query.data or "") else ""
        if key not in QUALITY_FORMATS:
            self.logger.warning(f"User {user_id} unknown quality choice: {key!r}")
            await self._safe_edit(query.message, strings.ERROR_QUALITY_UNKNOWN)
            return

        pending_map = context.user_data.get("pending_media_links", {})
        pending = pending_map.get(query.message.message_id)
        if pending is None and pending_map:
            platform, url = list(pending_map.values())[-1]
            self.logger.warning(
                f"User {user_id} pending miss for message {query.message.message_id}, "
                f"falling back to latest pending link: {url}"
            )
        elif pending is None:
            self.logger.warning(
                f"User {user_id} has no pending media link for message {query.message.message_id}"
            )
            await self._safe_edit(query.message, strings.ERROR_QUALITY_UNKNOWN)
            return
        else:
            platform, url = pending

        queued = self._is_queued(user_id)
        await self._safe_edit(
            query.message,
            strings.QUEUE_ADDED if queued else strings.DOWNLOADING_QUALITY.format(quality=QUALITY_LABELS[key]),
        )
        self.logger.info(f"User {user_id} starting YouTube download: quality={key}, url={url}, queued={queued}")
        await self._download_and_deliver(update, context, platform, url, query.message, QUALITY_FORMATS[key])

    async def _offer_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
        """
        Send a YouTube preview image with a quality choice keyboard and remember the pending link.

        Args:
            update: Telegram update object
            context: Context for the handler
            url: Detected YouTube URL
        """
        user_id = update.effective_user.id
        message = update.effective_message
        qualities = await _available_yt_qualities(url)
        best_height = max(qualities, default=None)
        best_label = (
            f"{strings.BUTTON_QUALITY_BEST} · {best_height}p{_format_eta(qualities.get(best_height))}"
            if best_height else strings.BUTTON_QUALITY_BEST
        )
        buttons = [(best_label, "mediaq:best")]
        buttons.extend(
            (f"{label}{_format_eta(qualities.get(int(callback.rsplit(':', 1)[1])))}", callback)
            for label, callback in QUALITY_BUTTONS[1:-1]
            if int(callback.rsplit(":", 1)[1]) in qualities
        )
        buttons.append(QUALITY_BUTTONS[-1])
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(label, callback_data=callback)] for label, callback in buttons]
        )
        thumb = _extract_yt_thumb(url)
        prompt_message = None
        try:
            if thumb:
                prompt_message = await message.reply_photo(
                    photo=thumb, caption=strings.QUALITY_PROMPT, reply_markup=keyboard
                )
                self.logger.info(f"User {user_id} quality prompt sent with preview thumbnail")
        except TelegramError as e:
            self.logger.warning(f"User {user_id} thumbnail send failed, falling back to text: {e}")
        if prompt_message is None:
            prompt_message = await message.reply_text(strings.QUALITY_PROMPT, reply_markup=keyboard)
            self.logger.info(f"User {user_id} quality prompt sent as text")
        pending = context.user_data.setdefault("pending_media_links", {})
        pending[prompt_message.message_id] = ("youtube", url)
        while len(pending) > 10:
            pending.pop(next(iter(pending)))
        self.logger.info(
            f"User {user_id} offered YouTube quality choice: qualities={qualities}, "
            f"url={url}, prompt_message={prompt_message.message_id}"
        )

    async def _download_and_deliver(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        platform: str,
        url: str,
        status,
        format_hint: Optional[str],
    ) -> None:
        """
        Download media for a link and deliver the result, editing the status message.

        Args:
            update: Telegram update object
            context: Context for the handler
            platform: Whitelisted platform key
            url: Media URL
            status: Status message to edit during progress
            format_hint: Optional yt-dlp format selector or "audio"
        """
        user_id = update.effective_user.id
        started = time.time()
        output_dir = tempfile.mkdtemp(prefix=f"media_{user_id}_")
        self.logger.info(f"User {user_id} created output directory: {output_dir}")

        timeout_budget = (2 if platform == "instagram" else 1) * settings.MEDIA_DOWNLOAD_TIMEOUT_SEC + 900 + 10
        self.logger.info(
            f"User {user_id} download timeout budget: {timeout_budget}s (platform={platform}, includes 900s split phase)"
        )

        async with self._user_sem(user_id), self._global_sem:
            try:
                result = await asyncio.wait_for(
                    download_media(url, platform, output_dir, format_hint),
                    timeout=timeout_budget,
                )
                await self._send_result(update, context, result, status)
                await self._forward_emoji_ad(update, context)
                try:
                    await status.delete()
                    self.logger.info(f"User {user_id} status message deleted")
                except Exception as e:
                    self.logger.warning(f"User {user_id} failed to delete status message: {e}")
                self.logger.info(
                    f"User {user_id} media delivered: platform={platform}, kind={result.kind}, "
                    f"files={len(result.files)}, total_mb={result.total_mb:.2f}, "
                    f"elapsed={time.time() - started:.2f}s"
                )
            except AuthRequiredError as e:
                self.logger.warning(f"User {user_id} platform requires authentication: {e}")
                await self._safe_edit(status, strings.ERROR_IG_AUTH)
            except DownloadTimeoutError as e:
                self.logger.warning(f"User {user_id} media download timed out: {e}")
                await self._safe_edit(status, strings.ERROR_DOWNLOAD_TIMEOUT)
            except DownloadError as e:
                self.logger.error(f"User {user_id} media download failed: {e}", exc_info=True)
                await self._safe_edit(status, strings.ERROR_DOWNLOAD_FAILED)
            except asyncio.TimeoutError:
                self.logger.error(f"User {user_id} media download exceeded outer timeout", exc_info=True)
                await self._safe_edit(status, strings.ERROR_DOWNLOAD_TIMEOUT)
            except Exception as e:
                self.logger.error(f"User {user_id} unexpected media download error: {e}", exc_info=True)
                await self._safe_edit(status, strings.ERROR_DOWNLOAD_FAILED)
            finally:
                self.logger.info(f"User {user_id} cleaning up output directory: {output_dir}")
                shutil.rmtree(output_dir, ignore_errors=True)
                self.logger.info(f"User {user_id} output directory cleaned up")

    async def _safe_edit(self, message, text: str) -> None:
        """
        Edit a text or photo message, ignoring Telegram errors.

        Args:
            message: Message object to edit
            text: New text or caption
        """
        try:
            if message.photo:
                await message.edit_caption(caption=text)
            else:
                await message.edit_text(text)
        except Exception as e:
            self.logger.error(f"Failed to edit status message: {e}", exc_info=True)

    async def _safe_reply(self, message, text: str) -> None:
        """
        Reply with a text message, ignoring Telegram errors.

        Args:
            message: Telegram message object
            text: Text to send
        """
        try:
            await message.reply_text(text)
        except Exception as e:
            self.logger.error(f"Failed to send reply message: {e}", exc_info=True)

    async def _send_result(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, result: MediaResult, status
    ) -> None:
        """
        Send downloaded files to the user.

        Args:
            update: Telegram update object
            context: Telegram callback context used for the saved custom-emoji caption
            result: Downloaded media result
            status: Status message object for progress updates
        """
        message = update.effective_message
        caption, caption_entities = self._build_caption(context)

        if result.kind == "audio":
            audio_path = max(result.files, key=os.path.getsize)
            try:
                with open(audio_path, "rb") as f:
                    await message.reply_audio(audio=f, caption=caption, caption_entities=caption_entities)
                self.logger.info(f"Audio sent successfully: {audio_path}")
            except TelegramError as e:
                self.logger.warning(f"reply_audio failed, falling back to document: {e}")
                with open(audio_path, "rb") as f:
                    await message.reply_document(document=f, caption=caption, caption_entities=caption_entities)
                self.logger.info(f"Audio sent as document: {audio_path}")
            return

        if result.kind == "video":
            if len(result.files) == 1:
                await self._send_single_video(message, result.files[0], caption, caption_entities)
            else:
                await self._send_video_parts(message, status, result.files, caption, caption_entities)
            return

        if len(result.files) > 10:
            self.logger.warning(f"More than 10 photo files, sending first 10 only: {len(result.files)} total")
        files = result.files[:10]
        self.logger.info(f"Sending {len(files)} photo file(s)")

        if len(files) == 1:
            photo_path = files[0]
            try:
                with open(photo_path, "rb") as f:
                    await message.reply_photo(photo=f, caption=caption, caption_entities=caption_entities)
                self.logger.info(f"Photo sent successfully: {photo_path}")
            except TelegramError as e:
                self.logger.warning(f"reply_photo failed, falling back to document: {e}")
                with open(photo_path, "rb") as f:
                    await message.reply_document(document=f, caption=caption, caption_entities=caption_entities)
                self.logger.info(f"Photo sent as document: {photo_path}")
        else:
            handles = []
            media = []
            try:
                for index, path in enumerate(files):
                    f = open(path, "rb")
                    handles.append(f)
                    media.append(InputMediaPhoto(media=f, caption=caption if index == 0 else None, caption_entities=caption_entities if index == 0 else None))
                self.logger.debug(f"Opened {len(handles)} file handle(s) for media group send")
                await message.reply_media_group(media=media)
                self.logger.info(f"Photo group sent successfully: {len(files)} files")
            finally:
                for f in handles:
                    f.close()
                self.logger.debug(f"Closed {len(handles)} file handle(s) after media group send")

    async def _send_single_video(self, message, video_path: str, caption: str, caption_entities) -> None:
        """
        Send a single video file with streaming, falling back to document.

        Args:
            message: Telegram message object
            video_path: Path to the video file
            caption: Caption with the source link
            caption_entities: Optional custom-emoji entities for the caption
        """
        self.logger.info(f"Sending video: {video_path}")
        metadata = await self._probe_video_metadata(video_path)
        thumbnail_path = await self._create_video_thumbnail(video_path)
        video_kwargs = {
            "supports_streaming": True,
            "caption": caption,
            "caption_entities": caption_entities,
        }
        if metadata:
            video_kwargs.update(metadata)
        try:
            with open(video_path, "rb") as video_file:
                if thumbnail_path:
                    with open(thumbnail_path, "rb") as thumbnail_file:
                        await message.reply_video(video=video_file, thumbnail=thumbnail_file, **video_kwargs)
                else:
                    await message.reply_video(video=video_file, **video_kwargs)
            self.logger.info(f"Video sent successfully: {video_path}")
        except TelegramError as e:
            self.logger.warning(f"reply_video failed, falling back to document: {e}")
            with open(video_path, "rb") as f:
                await message.reply_document(document=f, caption=caption, caption_entities=caption_entities)
            self.logger.info(f"Video sent as document: {video_path}")

    async def _probe_video_metadata(self, video_path: str) -> Optional[dict]:
        """Return duration and dimensions explicitly required by Local Bot API cards."""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of", "json", video_path,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                return None
            payload = json.loads(stdout)
            stream = next((item for item in payload.get("streams", []) if item.get("codec_type") == "video"), None)
            duration = round(float(payload["format"]["duration"]))
            if not stream or duration <= 0:
                return None
            metadata = {"duration": duration}
            if stream.get("width") and stream.get("height"):
                metadata.update(width=stream["width"], height=stream["height"])
            return metadata
        except (asyncio.TimeoutError, FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not probe video metadata for {video_path}: {e}")
            return None

    async def _create_video_thumbnail(self, video_path: str) -> Optional[str]:
        """Create a JPEG preview because Local Bot API does not generate one reliably."""
        thumbnail_path = os.path.join(os.path.dirname(video_path), "telegram_preview.jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", "1", "-i", video_path, "-frames:v", "1",
            "-vf", "scale=320:-2", thumbnail_path,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(proc.wait(), timeout=30)
            if proc.returncode == 0 and os.path.getsize(thumbnail_path) > 0:
                return thumbnail_path
        except (asyncio.TimeoutError, FileNotFoundError, OSError) as e:
            self.logger.warning(f"Could not create video thumbnail for {video_path}: {e}")
        return None

    async def _send_video_parts(self, message, status, files: List[str], caption: str, caption_entities) -> None:
        """
        Send a split video as sequential document parts with per-part progress updates.

        Args:
            message: Telegram message object
            status: Status message object for progress updates
            files: Paths to the video part files
            caption: Caption for the first part
            caption_entities: Optional custom-emoji entities for the first part caption
        """
        original_total = len(files)
        if original_total > settings.MEDIA_MAX_PARTS:
            self.logger.warning(
                f"Video has {original_total} parts, sending only the first {settings.MEDIA_MAX_PARTS}"
            )
            files = files[: settings.MEDIA_MAX_PARTS]
        total = len(files)
        self.logger.info(f"Sending {total} video part(s) as documents")

        failed: List[int] = []
        for index, part in enumerate(files, start=1):
            await self._safe_edit(status, strings.MEDIA_SENDING_PART.format(current=index, total=total))
            sent = False
            try:
                self.logger.info(f"Sending video part {index}/{total}: {part}")
                with open(part, "rb") as f:
                    await message.reply_document(document=f, caption=caption if index == 1 else None, caption_entities=caption_entities if index == 1 else None)
                sent = True
                self.logger.info(f"Video part {index}/{total} sent successfully")
            except RetryAfter as e:
                retry_delay = int(e.retry_after) + 1
                self.logger.warning(f"Video part {index}/{total} hit the flood limit, retrying in {retry_delay}s: {e}")
                await asyncio.sleep(retry_delay)
                try:
                    self.logger.info(f"Retrying video part {index}/{total}: {part}")
                    with open(part, "rb") as f:
                        await message.reply_document(document=f)
                    sent = True
                    self.logger.info(f"Video part {index}/{total} sent on retry")
                except TelegramError as e:
                    self.logger.error(f"Retry failed for video part {index}/{total}: {e}", exc_info=True)
            except TelegramError as e:
                self.logger.error(f"Failed to send video part {index}/{total}: {e}", exc_info=True)
            if not sent:
                failed.append(index)
                self.logger.error(f"Video part {index}/{total} ultimately failed to send")
            if index < total:
                await asyncio.sleep(1)

        if failed:
            self.logger.warning(f"Video send finished with {len(failed)} of {total} part(s) failed: {failed}")
            await self._safe_reply(message, strings.MEDIA_PARTS_FAILED.format(count=len(failed), total=total))
        if original_total > total:
            self.logger.info(f"Video truncated: sent {total} of {original_total} parts, notifying user")
            await self._safe_reply(message, strings.MEDIA_PARTS_TRUNCATED.format(total=total))
            self.logger.info(f"Truncation notice sent: first {total} of {original_total} parts")
