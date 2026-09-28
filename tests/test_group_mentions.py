"""Tests for strict opt-in group mention parsing."""

import unittest

from src.bot.group_mentions import is_bot_mention, is_emojicrop_request, strip_bot_mention


class GroupMentionTests(unittest.TestCase):
    def test_media_mention_keeps_only_the_link_payload(self):
        text = " @worksquadbot https://youtu.be/example "
        self.assertTrue(is_bot_mention(text))
        self.assertEqual(strip_bot_mention(text), "https://youtu.be/example")

    def test_emojicrop_requires_the_exact_explicit_request(self):
        self.assertTrue(is_emojicrop_request("@worksquadbot emojicrop"))
        self.assertTrue(is_emojicrop_request(" @WorksquadBot   emojiCrop  "))
        self.assertFalse(is_emojicrop_request("@worksquadbot emojicrop please"))
        self.assertFalse(is_emojicrop_request("emojicrop"))
