"""Unit tests for tools/tracker_utils.py and candidate_profile.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.tracker_utils import norm, get_tracked_keys, clean_slug
from tools.candidate_profile import CANDIDATE_PROFILE


class TestTrackerUtils(unittest.TestCase):
    def test_norm_normalizes_strings(self):
        self.assertEqual(norm("Google LLC"), "googlellc")
        self.assertEqual(norm("Senior Frontend Engineer (React 19)"), "seniorfrontendengineerreact19")
        self.assertEqual(norm(""), "")
        self.assertEqual(norm(None), "")

    def test_clean_slug(self):
        self.assertEqual(clean_slug("Made Card - Senior Frontend"), "made_card_senior_frontend")
        self.assertEqual(clean_slug("sa.global / Remote"), "sa_global_remote")
        self.assertEqual(clean_slug("___Test___"), "test")

    def test_get_tracked_keys_reads_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("company,role,status\n")
            f.write("Google,Frontend Engineer,applied\n")
            f.write("Stripe,Staff Engineer,interview\n")
            temp_path = Path(f.name)

        try:
            keys = get_tracked_keys(temp_path)
            self.assertIn(("google", "frontendengineer"), keys)
            self.assertIn(("stripe", "staffengineer"), keys)
            self.assertEqual(len(keys), 2)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_candidate_profile_schema(self):
        self.assertEqual(CANDIDATE_PROFILE["name"], "Alex Doe")
        self.assertEqual(CANDIDATE_PROFILE["email"], "user@example.com")
        self.assertIn("29 ADRs", CANDIDATE_PROFILE["metrics"]["adrs"])
        self.assertIn("25 Playwright", CANDIDATE_PROFILE["metrics"]["test_suites"])
        self.assertEqual(CANDIDATE_PROFILE["notice_period"], "45 days")


if __name__ == "__main__":
    unittest.main()
