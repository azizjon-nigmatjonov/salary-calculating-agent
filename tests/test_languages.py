"""Unit tests for language selection."""

import json
import os
import tempfile
import unittest
from unittest import mock

import languages


class LanguageTests(unittest.TestCase):
    """Tests for per-chat language preferences."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.tmp.close()
        os.unlink(self.tmp.name)
        self.lang_patcher = mock.patch.object(
            languages.config, "LANG_FILE", self.tmp.name
        )
        self.lang_patcher.start()
        languages.reload_from_disk()

    def tearDown(self) -> None:
        self.lang_patcher.stop()
        languages.reload_from_disk()
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_parse_and_store(self) -> None:
        languages.start_language_selection(42)
        self.assertTrue(languages.is_awaiting_language(42))
        lang = languages.parse_language_choice("Russian")
        self.assertEqual(lang, "ru")
        languages.set_language(42, "ru")
        self.assertEqual(languages.get_language(42), "ru")
        self.assertFalse(languages.is_awaiting_language(42))

    def test_localized_welcome(self) -> None:
        languages.set_language(42, "uz")
        self.assertIn("Salom", languages.t(42, "welcome"))

    def test_choice_persists_across_reload(self) -> None:
        languages.set_language(7, "uz")
        languages.set_language(9, "ru")

        # Simulate a bot restart: drop in-memory state, reload from disk.
        languages.reload_from_disk()

        self.assertEqual(languages.get_language(7), "uz")
        self.assertEqual(languages.get_language(9), "ru")

    def test_written_file_shape(self) -> None:
        languages.set_language(101, "en")
        with open(self.tmp.name, encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved, {"101": "en"})

    def test_clear_persists(self) -> None:
        languages.set_language(5, "uz")
        languages.clear_language(5)
        languages.reload_from_disk()
        self.assertIsNone(languages.get_language(5))

    def test_corrupt_file_is_tolerated(self) -> None:
        with open(self.tmp.name, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        languages.reload_from_disk()
        self.assertIsNone(languages.get_language(42))
        # Still writable afterwards.
        languages.set_language(42, "en")
        self.assertEqual(languages.get_language(42), "en")


if __name__ == "__main__":
    unittest.main()
