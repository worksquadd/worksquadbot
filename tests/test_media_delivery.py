"""Regression tests for Telegram media delivery."""

import os
import tempfile
import unittest
from types import SimpleNamespace

from telegram.error import BadRequest

from src.bot.commands.media_downloader import MediaDownloaderCommand
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
        update = SimpleNamespace(effective_message=message)
        context = SimpleNamespace(chat_data={})
        result = MediaResult("youtube", "video", [video_path], 0.01, "https://youtu.be/test")
        await command._send_result(update, context, result, status=None)

    async def test_single_video_is_sent_as_video(self):
        message = RecordingMessage()

        await self._deliver(message)

        self.assertEqual(len(message.video_calls), 1)
        self.assertEqual(message.video_calls[0]["caption"], "🍿 worksquad")
        self.assertTrue(message.video_calls[0]["supports_streaming"])
        self.assertEqual(message.document_calls, [])

    async def test_document_is_only_fallback_after_telegram_video_error(self):
        message = RecordingMessage(video_error=BadRequest("unsupported video"))

        await self._deliver(message)

        self.assertEqual(len(message.video_calls), 1)
        self.assertEqual(len(message.document_calls), 1)
