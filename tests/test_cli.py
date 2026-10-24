import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifegraph.cli import gemini_key_problems, preflight_gemini

GOOD_KEY = "AIza" + "x" * 35


class KeyShapeTests(unittest.TestCase):
    def test_good_key_has_no_problems(self):
        self.assertEqual(gemini_key_problems(GOOD_KEY), [])
        self.assertEqual(gemini_key_problems("AQ." + "y" * 50), [])  # the newer AI Studio format
        self.assertIn("53 characters", " ".join(gemini_key_problems("AQ.short")))

    def test_common_mistakes_are_named(self):
        self.assertEqual(gemini_key_problems(""), ["GEMINI_API_KEY is empty"])
        self.assertIn("quotes or whitespace", " ".join(gemini_key_problems(f'"{GOOD_KEY}"')))
        self.assertIn("Bearer", " ".join(gemini_key_problems("Bearer " + GOOD_KEY)))
        self.assertIn("variable name", " ".join(gemini_key_problems("$GEMINI_API_KEY")))
        self.assertIn("start with 'AIza'", " ".join(gemini_key_problems("ya29.oauth-token-" + "x" * 22)))
        self.assertIn("39 characters", " ".join(gemini_key_problems("AIzaShort")))


class PreflightTests(unittest.TestCase):
    def _client(self, fail_with=None):
        def list_models():
            if fail_with:
                raise fail_with
            return []
        return SimpleNamespace(models=SimpleNamespace(list=list_models))

    def test_passes_when_google_accepts_the_key(self):
        preflight_gemini(self._client(), GOOD_KEY)  # no exit, no exception

    def test_exits_with_shape_diagnosis_for_a_bad_key(self):
        with self.assertRaises(SystemExit) as cm:
            preflight_gemini(self._client(RuntimeError("Error code: 400 - Invalid Auth key.")), "not-a-key")
        msg = str(cm.exception)
        self.assertIn("Invalid Auth key", msg)
        self.assertIn("looks wrong", msg)
        self.assertIn("start with 'AIza'", msg)
        self.assertIn("aistudio.google.com/apikey", msg)
        self.assertNotIn("not-a-key", msg.split("Google rejected")[0])  # the key itself is never echoed as a value

    def test_exits_with_google_side_diagnosis_for_a_well_formed_key(self):
        with self.assertRaises(SystemExit) as cm:
            preflight_gemini(self._client(RuntimeError("Error code: 400 - Invalid Auth key.")), GOOD_KEY)
        msg = str(cm.exception)
        self.assertIn("right shape", msg)
        self.assertIn("Generative Language API", msg)
        self.assertNotIn(GOOD_KEY, msg)


if __name__ == "__main__":
    unittest.main()
