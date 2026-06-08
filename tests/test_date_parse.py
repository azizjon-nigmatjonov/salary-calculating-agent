"""Unit tests for date parsing helpers."""

import unittest
from datetime import date

import date_parse


class DateParseTests(unittest.TestCase):
    """Tests for intent date normalization."""

    def test_normalize_derives_period_from_date(self) -> None:
        intent = {"date": "2026-02-15", "period": None}
        result = date_parse.normalize_intent_dates(intent)
        self.assertEqual(result["date"], "2026-02-15")
        self.assertEqual(result["period"], "2026-02")

    def test_invalid_date_cleared(self) -> None:
        intent = {"date": "not-a-date", "period": "2026-02"}
        result = date_parse.normalize_intent_dates(intent)
        self.assertIsNone(result["date"])
        self.assertEqual(result["period"], "2026-02")

    def test_build_prompt_contains_today(self) -> None:
        import agent

        prompt = agent.build_intent_system_prompt()
        self.assertIn(date_parse.today_iso(), prompt)
        self.assertIn(date_parse.yesterday_iso(), prompt)

    def test_this_year_february_15th(self) -> None:
        year = date.today().year
        self.assertEqual(
            date_parse.extract_date_from_text("This year in February 15th."),
            f"{year}-02-15",
        )

    def test_year_month_day_format(self) -> None:
        self.assertEqual(
            date_parse.extract_date_from_text("2026 February 15"),
            "2026-02-15",
        )

    def test_fallback_when_ollama_omits_date(self) -> None:
        intent = {"action": "add_bonus", "date": None, "period": None}
        result = date_parse.normalize_intent_dates(
            intent, "This year in February 15th, add bonus to Ali"
        )
        self.assertEqual(result["date"], f"{date.today().year}-02-15")
        self.assertEqual(result["period"], f"{date.today().year}-02")


if __name__ == "__main__":
    unittest.main()
