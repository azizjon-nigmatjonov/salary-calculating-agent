"""Unit tests for Uzbek commands from CSV."""

import unittest

import uzbek_commands


class UzbekCommandsTests(unittest.TestCase):
    """Tests for CSV-loaded Uzbek command matching."""

    def test_load_csv_commands(self) -> None:
        uzbek_commands.reload_commands()
        self.assertGreaterEqual(len(uzbek_commands.COMMANDS), 11)

    def test_match_avans_berdim(self) -> None:
        cmd = uzbek_commands.match_command("avans berdim")
        self.assertIsNotNone(cmd)
        assert cmd is not None
        self.assertEqual(cmd.action, "add_advance")

    def test_match_shtraf_soldim(self) -> None:
        cmd = uzbek_commands.match_command("Shtraf soldim")
        self.assertIsNotNone(cmd)
        assert cmd is not None
        self.assertEqual(cmd.action, "add_penalty")

    def test_match_delete_worker(self) -> None:
        cmd = uzbek_commands.match_command("Ishchini o'zchirib tashla")
        self.assertIsNotNone(cmd)
        assert cmd is not None
        self.assertEqual(cmd.action, "delete_worker")

    def test_advance_wizard_start(self) -> None:
        uzbek_commands.clear_session(100)
        reply = uzbek_commands.try_start(100, "avans berdim", "uz")
        self.assertIsNotNone(reply)
        self.assertTrue(uzbek_commands.has_session(100))
        uzbek_commands.clear_session(100)

    def test_match_list_workers_phrases(self) -> None:
        phrases = (
            "ishchilar ro'yxatini ber",
            "ishcilar ro'yxati",
            "ishchilar soni",
            "ishchilar royxati",
            "ishchilar royhati",
            "ishchilarmni ko'rsat",
            "ishchilrim",
            "ishchilarim",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                cmd = uzbek_commands.match_command(phrase)
                self.assertIsNotNone(cmd)
                assert cmd is not None
                self.assertEqual(cmd.action, "list_workers")

    def test_list_workers_is_instant(self) -> None:
        uzbek_commands.clear_session(101)
        reply = uzbek_commands.try_start(101, "ishchilar soni", "uz")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertIn("ishchilar soni", reply.lower())
        self.assertFalse(uzbek_commands.has_session(101))


if __name__ == "__main__":
    unittest.main()
