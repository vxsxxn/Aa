"""Aa naming: the agent answers to whatever the user calls it.

Covers the first-run stamp (hermes_cli/agent_naming.py): the question wording
settled in PLAN review is "What do you want to call me?" — the agent asks the
USER; a blank answer keeps the shipped default (untitled); a SOUL.md the user has
already written is never touched.
"""

import tempfile
import unittest
from pathlib import Path

from hermes_constants import get_hermes_home, reset_hermes_home_override, set_hermes_home_override
from hermes_cli.agent_naming import (
    DEFAULT_AGENT_NAME,
    NAMING_QUESTION,
    _clean_name,
    identity_is_seeded,
    offer_naming,
    personalize,
)
from hermes_cli.default_soul import (
    DEFAULT_SOUL_MD, IDENTITY_HEAD, LEGACY_AA_IDENTITY_HEAD, LEGACY_IDENTITY_HEAD,
)


class NamingTestCase(unittest.TestCase):
    """Each test gets a throwaway HERMES_HOME with a freshly seeded SOUL.md."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._token = set_hermes_home_override(self._tmp.name)
        self.soul = Path(get_hermes_home()) / "SOUL.md"
        self.soul.parent.mkdir(parents=True, exist_ok=True)
        self.soul.write_text(DEFAULT_SOUL_MD + "\n", encoding="utf-8")

    def tearDown(self):
        reset_hermes_home_override(self._token)
        self._tmp.cleanup()

    def offer(self, answer: str) -> str | None:
        return offer_naming(input_fn=lambda _prompt: answer, is_tty=lambda: True)

    def test_question_wording_is_agent_asks_user(self):
        self.assertEqual(NAMING_QUESTION, "What do you want to call me?")

    def test_enter_keeps_shipped_default(self):
        stamped = self.offer("")
        self.assertEqual(stamped, DEFAULT_AGENT_NAME)
        self.assertEqual(self.soul.read_text(encoding="utf-8"), DEFAULT_SOUL_MD + "\n")

    def test_custom_name_is_stamped(self):
        stamped = self.offer("  'Sparky'  ")
        self.assertEqual(stamped, "Sparky")
        first_line = self.soul.read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(first_line.startswith("You are Sparky, "))
        self.assertIn("Be direct:", first_line)

    def test_blank_and_default_answer_both_keep_behavior_text(self):
        self.offer("Sparky")
        behavior = " Be direct: " in self.soul.read_text(encoding="utf-8")
        self.assertTrue(behavior)
        self.assertNotIn("Hermes Agent,", self.soul.read_text(encoding="utf-8").splitlines()[0])

    def test_long_name_is_capped(self):
        stamped = self.offer("x" * 100)
        self.assertEqual(stamped, "x" * 40)

    def test_clean_name_strips_wrapping_quotes(self):
        self.assertEqual(_clean_name('  "Aa" '), "Aa")
        self.assertEqual(_clean_name("''"), "")

    def test_customized_soul_is_never_touched(self):
        self.soul.write_text("You are whoever I say I am.\n", encoding="utf-8")
        stamped = self.offer("Sparky")
        self.assertIsNone(stamped)
        self.assertEqual(self.soul.read_text(encoding="utf-8"), "You are whoever I say I am.\n")

    def test_missing_soul_file(self):
        self.soul.unlink()
        self.assertIsNone(self.offer("Sparky"))

    def test_interrupted_answer_leaves_seed_for_next_launch(self):
        def interrupt(_prompt):
            raise EOFError

        self.assertIsNone(offer_naming(input_fn=interrupt, is_tty=lambda: True))
        self.assertTrue(identity_is_seeded(self.soul))

    def test_no_tty_never_asks(self):
        self.assertIsNone(offer_naming(input_fn=lambda _p: "Sparky", is_tty=lambda: False))
        self.assertTrue(identity_is_seeded(self.soul))

    def test_pre_rebrand_seed_is_upgraded_in_place(self):
        self.soul.write_text(LEGACY_IDENTITY_HEAD + DEFAULT_SOUL_MD[len(IDENTITY_HEAD):] + "\n", encoding="utf-8")
        self.assertTrue(identity_is_seeded(self.soul))
        self.assertEqual(self.offer("Buddy"), "Buddy")
        first_line = self.soul.read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(first_line.startswith("You are Buddy, a lean,"))

    def test_pre_untitled_aa_seed_is_upgraded_in_place(self):
        """Installs seeded before the default became "untitled" still personalize."""
        self.soul.write_text(LEGACY_AA_IDENTITY_HEAD + DEFAULT_SOUL_MD[len(IDENTITY_HEAD):] + "\n", encoding="utf-8")
        self.assertTrue(identity_is_seeded(self.soul))
        self.assertEqual(self.offer("Buddy"), "Buddy")
        first_line = self.soul.read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(first_line.startswith("You are Buddy, a lean,"))

    def test_personalize_rejects_blank_name(self):
        self.assertIsNone(personalize(self.soul, "   "))
        self.assertTrue(identity_is_seeded(self.soul))


if __name__ == "__main__":
    unittest.main()
