"""Unit tests for spoken and written amount parsing."""

import unittest

import amount_parse
import registration


class AmountParseTests(unittest.TestCase):
    """Tests for natural language monetary amounts."""

    def test_six_million_voice(self) -> None:
        self.assertEqual(amount_parse.parse_amount("Six million."), 6_000_000)

    def test_five_mln(self) -> None:
        self.assertEqual(amount_parse.parse_amount("5 mln"), 5_000_000)

    def test_yarim_million(self) -> None:
        self.assertEqual(amount_parse.parse_amount("yarim million"), 500_000)

    def test_olti_million_uzbek(self) -> None:
        self.assertEqual(amount_parse.parse_amount("olti million"), 6_000_000)

    def test_five_hundred_ming(self) -> None:
        self.assertEqual(amount_parse.parse_amount("500 ming"), 500_000)

    def test_plain_digits(self) -> None:
        self.assertEqual(amount_parse.parse_amount("5000000"), 5_000_000)

    def test_russian_six_million(self) -> None:
        self.assertEqual(amount_parse.parse_amount("шесть миллионов"), 6_000_000)

    def test_registration_wizard_uses_parser(self) -> None:
        self.assertEqual(registration.parse_salary("Six million."), 6_000_000)

    def test_non_amount_returns_none(self) -> None:
        self.assertIsNone(amount_parse.parse_amount("Add a new worker."))

    def test_intent_amount_fallback(self) -> None:
        intent = {"amount": None, "fixed_salary": None}
        result = amount_parse.normalize_intent_amount(intent, "Six million bonus for Ali")
        self.assertEqual(result["amount"], 6_000_000)


if __name__ == "__main__":
    unittest.main()
