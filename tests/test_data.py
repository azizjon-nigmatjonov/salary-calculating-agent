"""Unit tests for data.py payroll logic."""

import json
import os
import tempfile
import unittest
from unittest import mock

import data


class DataLayerTests(unittest.TestCase):
    """Tests for salary storage and calculations."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"workers": {}}, self.tmp)
        self.tmp.close()
        self.db_patcher = mock.patch.object(data.config, "DB_FILE", self.tmp.name)
        self.db_patcher.start()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        os.unlink(self.tmp.name)

    def test_register_and_get_worker(self) -> None:
        worker = data.register_worker(
            "Ali Karimov", "2024-03-01", "1990-05-15", 5_000_000
        )
        self.assertEqual(worker["key"], "ali_karimov")
        self.assertEqual(worker["fixed_salary"], 5_000_000)

        fetched = data.get_worker("ali_karimov")
        assert fetched is not None
        self.assertEqual(fetched["full_name"], "Ali Karimov")

    def test_duplicate_registration_rejected(self) -> None:
        data.register_worker("Ali Karimov", "2024-03-01", "1990-05-15", 5_000_000)
        with self.assertRaises(ValueError):
            data.register_worker("Ali Karimov", "2024-03-01", "1990-05-15", 5_000_000)

    def test_bonus_advance_payout_and_net(self) -> None:
        data.register_worker("Bobur", "2024-01-01", "1988-01-01", 2_000_000)
        data.add_bonus("bobur", 500_000, "performance")
        data.add_advance("bobur", 300_000, "advance")
        data.record_payout("bobur", 1_000_000, "2025-03")

        worker = data.get_worker("bobur")
        assert worker is not None
        breakdown = data.calculate_net_salary(worker)
        self.assertEqual(breakdown["fixed_salary"], 2_000_000)
        self.assertEqual(breakdown["total_bonuses"], 500_000)
        self.assertEqual(breakdown["total_advances"], 300_000)
        self.assertEqual(breakdown["total_payouts"], 1_000_000)
        self.assertEqual(breakdown["net_payable"], 1_200_000)

    def test_period_filtering(self) -> None:
        data.register_worker("Kamol", "2024-01-01", "1992-06-01", 3_000_000)
        db = data.load_db()
        worker = db["workers"]["kamol"]
        worker["bonuses"] = [
            {"amount": 100_000, "note": "Jan", "timestamp": "2025-01-10T09:00:00"},
            {"amount": 200_000, "note": "Mar", "timestamp": "2025-03-10T09:00:00"},
        ]
        worker["advances"] = [
            {"amount": 50_000, "note": "Mar", "timestamp": "2025-03-05T09:00:00"},
        ]
        worker["payouts"] = [
            {
                "amount": 500_000,
                "period": "2025-03",
                "timestamp": "2025-03-31T18:00:00",
            }
        ]
        data.save_db(db)

        march = data.calculate_net_salary(worker, period="2025-03")
        self.assertEqual(march["total_bonuses"], 200_000)
        self.assertEqual(march["total_advances"], 50_000)
        self.assertEqual(march["total_payouts"], 500_000)
        self.assertEqual(march["net_payable"], 2_650_000)

    def test_resolve_worker_key_partial_name(self) -> None:
        data.register_worker("Ali Karimov", "2024-03-01", "1990-05-15", 5_000_000)
        self.assertEqual(data.resolve_worker_key("ali"), "ali_karimov")

    def test_resolve_ambiguous_name(self) -> None:
        data.register_worker("Ali Karimov", "2024-03-01", "1990-05-15", 5_000_000)
        data.register_worker("Alisher Tursunov", "2024-03-01", "1991-01-01", 4_000_000)
        with self.assertRaises(ValueError) as ctx:
            data.resolve_worker_key("ali")
        self.assertIn("Ambiguous", str(ctx.exception))

    def test_history_limit(self) -> None:
        data.register_worker("Test Worker", "2024-01-01", "1990-01-01", 1_000_000)
        for i in range(15):
            data.add_bonus("test_worker", 10_000, f"bonus {i}")
        history = data.get_history("test_worker", limit=10)
        self.assertEqual(len(history), 10)


if __name__ == "__main__":
    unittest.main()
