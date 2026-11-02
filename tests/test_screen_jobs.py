"""Tests for tools/screen_jobs.py - /scrape Step 3's screen, made checkable.

The rules are cheap to get wrong in both directions, so every test below is either a
real residual from the 2026-09-30 second sweep (should be screened) or a real false
positive the first draft produced (must be kept).
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.screen_jobs import screen_entry  # noqa: E402


def geo_hits(title, loc):
    """Geography-rule hits, whichever flavour: `geography` or `geography-country-locked`."""
    return [r for r in screen_entry(title, loc) if r.startswith("geography")]


class TestScreened(unittest.TestCase):
    """Postings that must be screened out - each one really reached the table."""

    def test_foreign_onsite_is_screened(self):
        # Singapore / Vietnam / Indonesia / Hong Kong rows presented on the 2nd sweep
        for title, loc in [
            ("Senior Front-end Engineer", "Singapore, Singapore"),
            ("Full Stack Engineer (Remote: Vietnam)", "Vietnam"),
            ("Senior AI Applied Software Engineer", "Ho Chi Minh"),
            ("Senior Technical Product Owner", "Wanchai, Hong Kong"),
            ("Senior Full Stack Engineer, AI Builder", "Indonesia"),
        ]:
            self.assertTrue(geo_hits(title, loc), f"{title} / {loc}")

    def test_non_ncr_indian_city_onsite_is_screened(self):
        self.assertTrue(geo_hits("Senior Full Stack Software Engineer", "Bengaluru, IN"))
        self.assertTrue(geo_hits("Sr Software Engineer (React.js / Next.js)", "Pune, MH, in"))
        self.assertTrue(geo_hits("Sr AI Engineer", "Hyderabad, Telangana, India"))

    def test_country_locked_remote_is_screened(self):
        self.assertTrue(geo_hits("Senior Frontend Engineer", "Remote (US)"))
        self.assertTrue(geo_hits("Senior React Developer", "Canada EOR only"))
        # "remote" in the title does not make a foreign-scoped posting open-to-anywhere
        self.assertTrue(geo_hits("Full Stack Engineer (Remote: Vietnam)", "Vietnam"))
        self.assertTrue(geo_hits(
            "Senior Node/React Engineer - Remote, End-to-End Ownership", "Singapore, Singapore"))

    def test_remote_worldwide_language_still_wins(self):
        # an explicit worldwide/anywhere signal overrides the foreign place
        self.assertEqual([], screen_entry("Senior Frontend Engineer (Worldwide Remote)", "Singapore"))
        # ...and so does an India mention in a multi-country remote location
        self.assertEqual([], screen_entry("Senior React Engineer", "Remote - India / Singapore"))

    def test_places_missing_from_the_foreign_list_are_still_screened(self):
        """Default-deny geography: these leaked when the rule listed foreign countries."""
        for title, loc in [
            ("Full-Stack Developer", "Costa Rica"),
            ("Intermediate/Senior Full Stack Software Engineer", "Wellington"),
            ("Senior Applied AI Software Engineer", "Manila, NCR, ph"),
            ("Sr. Full-Stack Software Engineer", "Charlotte, Clinton County"),
            ("Frontend Engineer", "Lagos, Nigeria"),
            ("React Developer", "Sao Paulo"),
        ]:
            self.assertTrue(geo_hits(title, loc), f"{title} / {loc}")

    def test_manila_ncr_is_not_delhi_ncr(self):
        # Manila's National Capital Region shares the abbreviation - it must not pass
        self.assertTrue(geo_hits("Senior Full Stack Engineer", "Manila, NCR, ph"))
        # ...while a real NCR location still passes
        self.assertEqual([], screen_entry("Senior Full Stack Engineer", "Noida, Uttar Pradesh, India"))

    def test_out_of_family_titles_are_screened(self):
        for title in [
            "Engineering Manager - Frontend",
            "Director of Engineering",
            "Principal Frontend Engineer",
            "Frontend Architect",
            "Technical Product Manager",
            "Sales Executive - SaaS",
            "Technical Recruiter",
        ]:
            self.assertIn("title-family", screen_entry(title, "Noida, India"))

    def test_wrong_discipline_is_screened(self):
        for title in [
            "Senior iOS Engineer",
            "React Native Developer",
            "Backend Engineer (Node)",
            "Site Reliability Engineer",
            "Senior Software Engineer - Data Platform",
            "Machine Learning Engineer",
        ]:
            self.assertIn("discipline", screen_entry(title, "Noida, India"))

    def test_non_js_stack_without_a_js_token_is_screened(self):
        for title in [
            "Senior C++ Developer",
            "Senior Python Engineer (Cheminformatics / Drug Discovery)",
            "Senior AI Engineer/Python Developer",
            ".NET Developer",
            "Senior Software Developer (PHP)",
            "RevTech Senior Salesforce Developer",
            "Senior Full Stack Developer - Java",
        ]:
            self.assertIn("non-js-stack", screen_entry(title, "Noida, India"))

    def test_non_english_title_is_screened(self):
        self.assertIn("non-english-title", screen_entry("Développeur React senior H/F", "Montpellier, France"))
        self.assertIn("non-english-title", screen_entry("Desenvolvedor(a) Full Stack", "Blumenau, Brazil"))


class TestKept(unittest.TestCase):
    """False positives the first draft produced - these must never be screened."""

    def test_remote_anywhere_is_kept(self):
        for loc in ["Remote", "Worldwide / Remote", "Work From Home", "IN / Remote (IN)", "Remote - Unspecified"]:
            self.assertEqual([], screen_entry("Senior Frontend Engineer", loc), loc)

    def test_country_only_india_is_kept(self):
        # jobgether and friends label remote-India roles with just "India"
        self.assertEqual([], screen_entry("Senior Full-Stack TypeScript Engineer", "India"))
        self.assertEqual([], screen_entry("Senior AI Engineer", "in"))

    def test_ncr_onsite_is_kept(self):
        for loc in ["Gurgaon, Haryana, India", "Noida, Uttar Pradesh, India", "New Delhi, Delhi, India"]:
            self.assertEqual([], screen_entry("React Developer", loc), loc)

    def test_java_react_and_data_frontend_titles_are_kept(self):
        self.assertEqual([], screen_entry("Java React Developer", "Gurgaon, India"))
        self.assertEqual([], screen_entry("Senior Javascript Developer - React", "Remote - India"))
        self.assertEqual([], screen_entry("Full Stack Engineer - Web + Java", "India"))
        # "Data" alone is a frontend title word, not a discipline signal
        self.assertEqual([], screen_entry("Frontend Engineer, Data Product Experiences", "Remote"))
        self.assertEqual([], screen_entry("Salesforce Commerce Cloud Senior Frontend Developer", "Delhi, India"))

    def test_remote_signal_in_title_counts(self):
        # Bangalore in the location, but the posting itself is remote
        self.assertEqual([], screen_entry("Senior Full Stack Engineer (Remote)", "Bangalore, India"))

    def test_blank_location_is_not_screened_for_geography(self):
        # the portal reported nothing - guessing is forbidden, so it is reported, not dropped
        self.assertEqual([], screen_entry("Senior Frontend Engineer", None))
        self.assertEqual([], screen_entry("React Developer", ""))
        # ...but a title rule still applies regardless of the location
        self.assertIn("non-js-stack", screen_entry("Senior C++ Developer", None))


class TestCli(unittest.TestCase):
    def _state(self, entries):
        tmp = Path(tempfile.mkdtemp()) / "seen_jobs.json"
        tmp.write_text(json.dumps({"seen": entries}, indent=2), encoding="utf-8")
        return tmp

    def test_reports_and_exits_nonzero_on_violation(self):
        state = self._state({
            "keep": {"title": "React Developer", "company": "A", "location": "Gurgaon, India", "status": "new"},
            "drop": {"title": "Senior C++ Developer", "company": "B", "location": "Delhi, India", "status": "new"},
        })
        proc = subprocess.run(
            [sys.executable, "tools/screen_jobs.py", "--state", str(state), "--json"],
            cwd=REPO, capture_output=True, text=True,
        )
        self.assertEqual(1, proc.returncode)
        report = json.loads(proc.stdout)
        self.assertEqual(1, report["counts"]["violations"])
        self.assertEqual("drop", report["violations"][0]["key"])

    def test_apply_flips_only_new_entries_and_leaves_them_stored(self):
        state = self._state({
            "keep": {"title": "React Developer", "company": "A", "location": "Gurgaon, India", "status": "new"},
            "drop": {"title": "Senior C++ Developer", "company": "B", "location": "Delhi, India",
                     "status": "new", "portal": "freehire-search", "url": "https://x/1"},
            "ranked": {"title": "Senior PHP Developer", "company": "C", "location": "Noida, India",
                       "status": "ranked", "rank_score": 71},
        })
        proc = subprocess.run(
            [sys.executable, "tools/screen_jobs.py", "--state", str(state), "--apply"],
            cwd=REPO, capture_output=True, text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        seen = json.loads(state.read_text(encoding="utf-8"))["seen"]
        self.assertEqual("new", seen["keep"]["status"], "a passing entry must stay presented")
        self.assertEqual("skipped", seen["drop"]["status"], "a violating entry must be recorded as skipped")
        self.assertEqual("https://x/1", seen["drop"]["url"], "the entry must be kept, not deleted")
        self.assertEqual("ranked", seen["ranked"]["status"], "/rank's status must never be rewritten")

    def test_clean_state_exits_zero(self):
        state = self._state({
            "a": {"title": "Senior Frontend Engineer", "company": "A", "location": "Remote (India)", "status": "new"},
        })
        proc = subprocess.run(
            [sys.executable, "tools/screen_jobs.py", "--state", str(state)],
            cwd=REPO, capture_output=True, text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
