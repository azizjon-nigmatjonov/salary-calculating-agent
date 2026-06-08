"""Unit tests for language selection."""

import unittest

import languages


class LanguageTests(unittest.TestCase):
    """Tests for per-chat language preferences."""

    def tearDown(self) -> None:
        languages.clear_language(42)

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


if __name__ == "__main__":
    unittest.main()
