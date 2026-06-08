"""Unit tests for typo-tolerant phrase matching."""

import unittest

import text_match


class TextMatchTests(unittest.TestCase):
  """Tests for Uzbek typo normalization and fuzzy matching."""

  def test_yengi_to_yangi(self) -> None:
    self.assertEqual(text_match.normalize_typos("yengi ishchi"), "yangi ishchi")

  def test_whisper_turkish_orthography(self) -> None:
    self.assertEqual(text_match.normalize_transcription("Yenge işçi"), "yangi ishchi")
    self.assertEqual(text_match.normalize_transcription("Yanke işçi"), "yangi ishchi")

  def test_fuzzy_register_phrases(self) -> None:
    self.assertTrue(text_match.fuzzy_equals("yengi ishchi", "yangi ishchi"))
    self.assertTrue(text_match.fuzzy_equals("yang ishchi", "yangi ishchi"))
    self.assertIsNotNone(
      text_match.fuzzy_match_phrase("yengi ishchi", text_match.REGISTER_PHRASES)
    )

  def test_exact_phrase_not_false_positive(self) -> None:
    self.assertFalse(text_match.fuzzy_equals("salom", "yangi ishchi"))


if __name__ == "__main__":
  unittest.main()
