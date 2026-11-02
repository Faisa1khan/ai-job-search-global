"""Tests for tools/jd_years.py - the advisory years-of-experience band.

The parser is vendored from career-ops-hq/career-ops, so these tests pin the behaviour
the pipeline depends on rather than upstream's own cases: a stated floor that is in
reach reads IN, a floor well above the candidate's years reads OUT, and anything ambiguous stays
UNKNOWN instead of guessing. The last one is the important one: an advisory tool that
guesses is worse than one that abstains.

The fixtures are the real requirement blocks from postings reviewed on 2026-10-30.
"""
import os
import sys
import unittest
from pathlib import Path

# The tools are neutral by default; these fixtures pin the reference numbers.
os.environ.setdefault("JOBSEARCH_CANDIDATE_YEARS", "5.0")
os.environ.setdefault("JOBSEARCH_STRETCH_YEARS", "1.0")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.jd_years import band_for_text, _node  # noqa: E402


def band(text, years=5.0, stretch=1.0):
    return band_for_text(text, years, stretch)


@unittest.skipUnless(_node(), "node is not installed")
class TestStatedBars(unittest.TestCase):
    def test_four_plus_is_in_reach(self):
        jd = ("Qualifications Bachelor's degree. 4+ years of professional Full-Stack "
              "JavaScript development experience. Strong expertise in JavaScript.")
        r = band(jd)
        self.assertEqual(r["status"], "stated")
        self.assertEqual(r["min"], 4)
        self.assertEqual(r["verdict"], "in")
        self.assertTrue(r["confident"])

    def test_three_plus_is_in_reach(self):
        jd = "What We're Looking For 3+ years of full stack software engineering experience."
        r = band(jd)
        self.assertEqual(r["min"], 3)
        self.assertEqual(r["verdict"], "in")

    def test_range_is_read_as_a_band(self):
        jd = ("4-7 years of professional software engineering experience. Strong proficiency "
              "in JavaScript and Typescript.")
        r = band(jd)
        self.assertEqual((r["min"], r["max"]), (4, 7))
        self.assertEqual(r["verdict"], "in")

    def test_ten_plus_is_out_of_reach(self):
        jd = "Requirements: 10+ years of experience building production web applications."
        r = band(jd)
        self.assertEqual(r["verdict"], "out")


@unittest.skipUnless(_node(), "node is not installed")
class TestAbstains(unittest.TestCase):
    def test_no_stated_years_is_unknown_not_in(self):
        jd = ("What We're Looking For Strong professional experience developing production "
              "applications with TypeScript and Node.js.")
        r = band(jd)
        self.assertEqual(r["status"], "none")
        self.assertEqual(r["verdict"], "unknown")
        self.assertFalse(r["confident"])

    def test_preferred_only_does_not_gate(self):
        jd = "Preferred Qualifications\n5+ years of overall engineering experience."
        r = band(jd)
        self.assertEqual(r["verdict"], "unknown")
        self.assertEqual(r["status"], "preferred-only")

    def test_skill_scoped_bar_inside_preferred_never_gates(self):
        # A preferred section asking for years in ONE technology is a skill bar, not an
        # overall one, so it is ignored for gating rather than read as a floor.
        jd = "Preferred Qualifications\n5+ years of experience with distributed systems."
        r = band(jd)
        self.assertEqual(r["verdict"], "unknown")
        self.assertIn(r["status"], ("none", "skill-only"))

    def test_empty_text_is_unknown(self):
        r = band("")
        self.assertEqual(r["verdict"], "unknown")
        self.assertEqual(r["reason"], "no JD text")


class TestNeverRaises(unittest.TestCase):
    """The tool is advisory: whatever happens, a verdict comes back and nothing blows up."""

    def test_network_path_returns_a_dict_on_bad_url(self):
        from tools.jd_years import band_for_url
        r = band_for_url("https://example.invalid/not-a-posting")
        self.assertIsInstance(r, dict)
        self.assertEqual(r["verdict"], "unknown")
        self.assertTrue(r["reason"])

    def test_candidate_band_is_honest(self):
        from tools.jd_years import CANDIDATE_YEARS, STRETCH_YEARS
        self.assertAlmostEqual(CANDIDATE_YEARS, 5.0)
        self.assertLessEqual(CANDIDATE_YEARS + STRETCH_YEARS, 6.0,
                             "stretch must not reach the 8-year floors he has missed on")


if __name__ == "__main__":
    unittest.main()
