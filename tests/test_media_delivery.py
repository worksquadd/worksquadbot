"""Regression tests for Telegram media delivery."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.error import BadRequest

from src.bot.commands.media_downloader import MediaDownloaderCommand, _format_eta
from src.config.settings import settings
from src.media.downloader import MediaResult


class RecordingMessage:
    """Minimal async Telegram-message fake that records media sends."""

    def __init__(self, video_error=None):
        self.video_error = video_error
        self.video_calls = []
        self.document_calls = []

    async def reply_video(self, **kwargs):
        self.video_calls.append(kwargs)
        if self.video_error:
            raise self.video_error

    async def reply_document(self, **kwargs):
        self.document_calls.append(kwargs)


class MediaDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def _deliver(self, message):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video:
            video.write(b"test video")
            video_path = video.name
        self.addCleanup(lambda: os.path.exists(video_path) and os.unlink(video_path))
        command = MediaDownloaderCommand()
        command._probe_video_metadata = AsyncMock(
            return_value={"duration": 42, "width": 640, "height": 360}
        )
        command._create_video_thumbnail = AsyncMock(return_value=None)
        update = SimpleNamespace(effective_message=message)
        result = MediaResult("youtube", "video", [video_path], 0.01, "https://youtu.be/test")
        await command._send_result(update, result, status=None)

    async def test_single_video_is_sent_as_video(self):
        message = RecordingMessage()

        await self._deliver(message)

        self.assertEqual(len(message.video_calls), 1)
        self.assertEqual(message.video_calls[0]["caption"], "🎨worksquadbot🎨")
        self.assertTrue(message.video_calls[0]["supports_streaming"])
        self.assertEqual(message.video_calls[0]["duration"], 42)
        self.assertEqual(message.video_calls[0]["width"], 640)
        self.assertEqual(message.video_calls[0]["height"], 360)
        self.assertEqual(message.document_calls, [])

    async def test_document_is_only_fallback_after_telegram_video_error(self):
        message = RecordingMessage(video_error=BadRequest("unsupported video"))

        await self._deliver(message)

        self.assertEqual(len(message.video_calls), 1)
        self.assertEqual(len(message.document_calls), 1)

    async def test_configured_signature_uses_two_custom_emoji_entities(self):
        command = MediaDownloaderCommand()
        original_ids = settings.MEDIA_CAPTION_CUSTOM_EMOJI_IDS
        self.addCleanup(setattr, settings, "MEDIA_CAPTION_CUSTOM_EMOJI_IDS", original_ids)
        settings.MEDIA_CAPTION_CUSTOM_EMOJI_IDS = ("first", "second")

        caption, entities = command._build_caption()

        self.assertEqual(caption, "🎨worksquadbot🎨")
        self.assertEqual([(entity.offset, entity.length, entity.custom_emoji_id) for entity in entities], [
            (0, 2, "first"), (14, 2, "second"),
        ])

    async def test_embedded_youtube_client_is_the_default(self):
        self.assertEqual(settings.MEDIA_YT_PLAYER_CLIENT, "embedded")

    async def test_quality_eta_uses_size_based_estimate(self):
        self.assertEqual(_format_eta(8 * 1024 * 1024), " · ~8 с")
        self.assertEqual(_format_eta(389 * 1024 * 1024), " · ~54 с")
