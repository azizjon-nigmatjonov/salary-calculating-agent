"""Unit tests for tools.py."""

import json
import os
import tempfile
import unittest
from unittest import mock

import data
import tools


class ToolsTests(unittest.TestCase):
    """Tests for salary tool wrappers."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"workers": {}}, self.tmp)
        self.tmp.close()
        self.db_patcher = mock.patch.object(data.config, "DB_FILE", self.tmp.name)
        self.db_patcher.start()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        os.unlink(self.tmp.name)

    def test_register_and_list(self) -> None:
        result = tools.tool_register_worker(
            "Ali Karimov", "2024-03-01", "1990-05-15", 5_000_000
        )
        self.assertIn("Registered Ali Karimov", result)
        listed = tools.tool_list()
        self.assertIn("Name: Ali Karimov", listed)
        self.assertIn("Age:", listed)
        self.assertIn("Salary: 5,000,000", listed)

        tools.tool_register_worker("Bobur Karimov", "2024-01-01", "1988-01-01", 3_000_000)
        listed_multi = tools.tool_list()
        self.assertIn("------", listed_multi)

    def test_calculate_salary_string(self) -> None:
        tools.tool_register_worker("Bobur", "2024-01-01", "1988-01-01", 2_000_000)
        tools.tool_add_bonus("bobur", 500_000)
        result = tools.tool_calculate_salary("bobur")
        self.assertIn("net payable", result.lower())
        self.assertIn("2,500,000", result)

    def test_history_tool(self) -> None:
        tools.tool_register_worker("Kamol", "2024-01-01", "1992-06-01", 3_000_000)
        tools.tool_add_advance("kamol", 100_000, "March advance")
        result = tools.tool_history("kamol")
        self.assertIn("add_advance", result)


if __name__ == "__main__":
    unittest.main()
