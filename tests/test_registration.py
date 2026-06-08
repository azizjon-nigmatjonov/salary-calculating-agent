"""Unit tests for registration wizard."""

import unittest

import registration


class RegistrationWizardTests(unittest.TestCase):
    """Tests for multi-step worker registration."""

    def setUp(self) -> None:
        registration.clear_session(999)

    def tearDown(self) -> None:
        registration.clear_session(999)

    def test_start_add_new_worker(self) -> None:
        reply = registration.start_session(999, "en")
        self.assertIn("full name", reply.lower())
        self.assertTrue(registration.has_session(999))

    def test_full_wizard_flow(self) -> None:
        registration.start_session(999, "en")
        registration.handle_message(999, "Bobur Karimov")
        registration.handle_message(999, "22")
        registration.handle_message(999, "2024-03-01")
        reply = registration.handle_message(999, "5 mln")
        self.assertIn("Registered", reply)
        self.assertFalse(registration.has_session(999))

    def test_partial_message_prefill(self) -> None:
        text = "Register new worker, Bobur, age 22, salary is 5 mln som"
        prefill = registration.extract_prefill_from_text(text)
        self.assertEqual(prefill.get("full_name"), "Bobur")
        self.assertEqual(prefill.get("fixed_salary"), 5_000_000)
        self.assertIsNotNone(prefill.get("birthdate"))

    def test_wants_to_start(self) -> None:
        self.assertTrue(registration.wants_to_start("add a new worker"))
        self.assertTrue(registration.wants_to_start("Register new worker"))

    def test_parse_salary_ignores_trailing_period(self) -> None:
        self.assertIsNone(registration.parse_salary("Add a new worker."))

    def test_voice_register_phrase_starts_wizard(self) -> None:
        intent = {"action": "chat", "language": "en"}
        reply = registration.try_start_from_intent(999, "Add a new worker.", intent)
        self.assertIsNotNone(reply)
        self.assertIn("name", reply.lower())

    def test_whisper_and_vs_add(self) -> None:
        self.assertTrue(registration.wants_to_start("And a new worker."))
        normalized = registration.normalize_user_text("And a new worker.")
        self.assertEqual(normalized, "add a new worker")

    def test_uzbek_yangi_ishchi_qosh(self) -> None:
        for phrase in ("Yangi ishchi qo'sh", "yangi ishchi qo'sh", "Yangi ishchi qosh"):
            with self.subTest(phrase=phrase):
                self.assertTrue(registration.wants_to_start(phrase))

    def test_uzbek_typo_yengi_ishchi(self) -> None:
        self.assertTrue(registration.wants_to_start("yengi ishchi"))
        reply = registration.try_start_from_intent(
            999, "yengi ishchi", {"action": "chat", "language": "uz"}
        )
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertIn("ism", reply.lower())


if __name__ == "__main__":
    unittest.main()
