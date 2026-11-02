"""tools/rank_flags.py - the three triage flags rank was missing.

Ported as flags, not as score weights, from career-ops-plugin's scoring rubric:
compensation is a dimension there (a target 30%+ above the band is flagged, not
fatal) and location/remote is graded rather than binary. Here both print beside
the score and never exclude a job, matching the rule this repo already uses for
India eligibility.

The band is read from the POSTING TEXT, because the board APIs do not supply one
in practice - measured 2026-10-07: 0 compensation bands across 5 Ashby boards
(sarvam, plane, ramp, notion, openai) with includeCompensation=true, and 0
salaryRange across 2 Lever boards (jobgether 3,280 postings, meesho 60).

Two bugs are pinned here because live testing caught them, not the tests:
the timezone conversion had the offset sign inverted (a PST role read as
06:30-15:30 IST instead of 22:30-07:30), and a USD band returned plain UNKNOWN
instead of UNKNOWN_CURRENCY.
"""

import json
import os
import subprocess
import sys

# The ladder is neutral by default in this fork; these fixtures pin the reference
# numbers the assertions below were written against.
os.environ.setdefault("JOBSEARCH_FLOOR_INR", "1850000")
os.environ.setdefault("JOBSEARCH_ANCHOR_INR", "2400000")
os.environ.setdefault("JOBSEARCH_TARGET_HIGH_INR", "2800000")
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import rank_flags as rf  # noqa: E402


class ParseBand(unittest.TestCase):
    def test_lpa_range(self):
        low, high, cur, _ = rf.parse_band("Compensation: 24-28 LPA")
        self.assertEqual((low, high, cur), (2_400_000, 2_800_000, "INR"))

    def test_lpa_range_with_rupee_and_lakh_word(self):
        low, high, cur, _ = rf.parse_band("Pay: INR 18.5 to 24 lakhs")
        self.assertEqual((low, high, cur), (1_850_000, 2_400_000, "INR"))

    def test_single_lpa_value_becomes_a_point_band(self):
        low, high, cur, _ = rf.parse_band("Salary: ₹22 LPA")
        self.assertEqual((low, high, cur), (2_200_000, 2_200_000, "INR"))

    def test_absolute_rupee_range(self):
        low, high, cur, _ = rf.parse_band("INR 25,00,000 - INR 35,00,000 per annum")
        self.assertEqual((low, high, cur), (2_500_000, 3_500_000, "INR"))

    def test_usd_band_is_named_not_converted(self):
        low, high, cur, raw = rf.parse_band("Base salary: $120,000 - $160,000 USD")
        self.assertEqual((low, high), (None, None))
        self.assertEqual(cur, "USD")
        self.assertIn("non-INR", raw)

    def test_a_bare_dollar_sign_is_not_a_band(self):
        """Measured false positive: "toward our $50M goal" was read as a USD band."""
        low, high, cur, _ = rf.parse_band("We are scaling rapidly toward our $50M goal, with 3x growth.")
        self.assertEqual((low, high, cur), (None, None, None))

    def test_a_dollar_amount_outside_salary_context_is_not_a_band(self):
        low, high, cur, _ = rf.parse_band("We process $2,000,000 in GMV monthly.")
        self.assertEqual((low, high, cur), (None, None, None))

    def test_a_usd_band_in_salary_context_is_named(self):
        low, high, cur, raw = rf.parse_band("Base salary: $120,000 - $160,000 per annum.")
        self.assertEqual((low, high), (None, None))
        self.assertEqual(cur, "USD")
        self.assertIn("120,000", raw)

    def test_nothing_stated(self):
        self.assertEqual(rf.parse_band("Competitive salary, great team"), (None, None, None, None))


class CompFlag(unittest.TestCase):
    def test_band_overlapping_the_target_is_ok(self):
        r = rf.comp_flag(2_400_000, 2_800_000)
        self.assertEqual(r["flag"], "OK")

    def test_band_below_the_never_accept_floor_is_flagged(self):
        r = rf.comp_flag(1_200_000, 1_500_000)
        self.assertEqual(r["flag"], "BELOW_FLOOR")
        self.assertIn("never accept below", r["reason"])

    def test_floor_beats_a_mismatch_verdict(self):
        """A band under the floor is the verdict even when the target is far above it."""
        r = rf.comp_flag(1_200_000, 1_500_000, target=2_400_000)
        self.assertEqual(r["flag"], "BELOW_FLOOR")

    def test_target_far_above_the_band_is_flagged_not_fatal(self):
        r = rf.comp_flag(1_800_000, 2_200_000, target=3_000_000)
        self.assertEqual(r["flag"], "MISMATCH_ABOVE")
        self.assertIn("do not exclude", r["reason"])

    def test_band_above_the_anchor_is_reported_as_strong_money(self):
        r = rf.comp_flag(2_500_000, 3_500_000)
        self.assertEqual(r["flag"], "MISMATCH_BELOW")

    def test_no_band_is_unknown_never_an_estimate(self):
        r = rf.comp_flag(None, None)
        self.assertEqual(r["flag"], "UNKNOWN")
        self.assertIn("no band stated", r["reason"])

    def test_non_inr_band_is_not_compared(self):
        r = rf.comp_flag(None, None, currency="USD")
        self.assertEqual(r["flag"], "UNKNOWN_CURRENCY")


class TimezoneFlag(unittest.TestCase):
    def test_us_hours_are_tight_from_ist(self):
        """The pinned regression: PST 9-18 is 22:30-07:30 IST, not 06:30-15:30."""
        r = rf.tz_flag("Engineer, Remote (US). Core hours 9:00-18:00 PST.")
        self.assertEqual(r["flag"], "TIGHT")
        self.assertEqual(r["best_overlap"]["in_ist"], "22:30-07:30")

    def test_london_hours_flag_as_a_late_night(self):
        r = rf.tz_flag("Working hours: 9am-6pm GMT.")
        self.assertEqual(r["flag"], "TIGHT")
        self.assertEqual(r["best_overlap"]["in_ist"], "14:30-23:30")
        self.assertTrue(r["late_end_ist"])

    def test_india_hours_are_ok(self):
        r = rf.tz_flag("Working hours 10am-7pm IST.")
        self.assertEqual(r["flag"], "OK")
        self.assertEqual(r["best_overlap"]["in_ist"], "10:00-19:00")

    def test_eu_hours_are_tight(self):
        r = rf.tz_flag("Core hours 09:00-18:00 CET.")
        self.assertEqual(r["flag"], "TIGHT")

    def test_no_stated_window_is_unknown(self):
        r = rf.tz_flag("Remote - Global. Competitive salary.")
        self.assertEqual(r["flag"], "UNKNOWN")
        self.assertEqual(r["windows"], [])

    def test_meridiem_edges(self):
        self.assertEqual(rf._to_hours("12", None, "am"), 0.0)
        self.assertEqual(rf._to_hours("12", None, "pm"), 12.0)
        self.assertEqual(rf._to_hours("1", "30", "pm"), 13.5)


class WarningLine(unittest.TestCase):
    """Only a warning prints; UNKNOWN and OK stay silent.

    Measured 2026-10-08: five of five archived postings returned UNKNOWN on both
    flags, so a report that printed the absent case would grow every line of every
    daily message and carry no signal.
    """

    def test_unknown_and_ok_produce_nothing(self):
        unknown_comp = rf.comp_flag(None, None)
        unknown_tz = rf.tz_flag("Remote - Global. Competitive salary.")
        self.assertIsNone(rf.warning_line(unknown_comp, unknown_tz))
        self.assertIsNone(rf.warning_line(rf.comp_flag(2_400_000, 2_800_000),
                                          rf.tz_flag("Working hours 10am-7pm IST.")))

    def test_below_floor_prints_the_pay_reason(self):
        line = rf.warning_line(rf.comp_flag(1_200_000, 1_500_000), None)
        self.assertIsNotNone(line)
        self.assertTrue(line.startswith("pay: "), line)
        self.assertIn("floor", line)

    def test_tight_hours_print_ist_window_and_the_late_end(self):
        line = rf.warning_line(None, rf.tz_flag("Working hours: 9am-6pm GMT."))
        self.assertIsNotNone(line)
        self.assertTrue(line.startswith("hours: "), line)
        self.assertIn("14:30-23:30 IST", line)
        self.assertIn("4.0h inside a 09:30-18:30 IST day", line)
        self.assertIn("ends after 22:00 IST", line)

    def test_both_warnings_are_joined_on_one_line(self):
        line = rf.warning_line(rf.comp_flag(1_200_000, 1_500_000), rf.tz_flag("Working hours: 9am-6pm GMT."))
        self.assertIn("pay: ", line)
        self.assertIn("hours: ", line)
        self.assertIn(" | ", line)

    def test_missing_or_malformed_flags_are_silent_not_crashes(self):
        """Entries ranked before the flags existed carry neither key."""
        self.assertIsNone(rf.warning_line(None, None))
        self.assertIsNone(rf.warning_line("UNKNOWN", {"flag": None}))
        self.assertEqual(rf.warning_line({"flag": "BELOW_FLOOR"}, None), "pay: BELOW_FLOOR")


class YearsFlag(unittest.TestCase):
    """The third flag: the years bar a posting states, annotated beside the score.

    The fixtures are the real requirement phrasings from 2026-10-30. The abstentions
    matter more than the verdicts: a bar scoped to one skill ("4+ years of experience
    with React") is not an overall floor, and reading it as one would put a wrong OUT on
    every posting in this candidate's lane.
    """

    IN_JD = ("Qualifications Bachelor's degree. 4+ years of professional Full-Stack "
             "JavaScript development experience. Strong expertise in JavaScript.")
    OUT_JD = "Requirements: 10+ years of experience building production web applications."
    NONE_JD = ("What We're Looking For Strong professional experience developing production "
               "applications with TypeScript and Node.js.")

    def test_reachable_floor_is_in(self):
        r = rf.years_flag(self.IN_JD)
        self.assertEqual(r["flag"], "YEARS_IN")
        self.assertEqual(r["verdict"], "in")
        self.assertEqual(r["min"], 4)
        self.assertIn("6.8", r["reason"])

    def test_floor_above_the_record_is_out(self):
        r = rf.years_flag(self.OUT_JD)
        self.assertEqual(r["flag"], "YEARS_OUT")
        self.assertEqual(r["verdict"], "out")
        self.assertIn("never a drop", r["reason"])
        self.assertEqual(r["candidate_years"], 6.8)
        self.assertEqual(r["stretch_reaches"], 8.0)

    def test_an_eight_plus_bar_is_in_but_says_it_is_only_the_stretch(self):
        # the alphasense/aryaxai shape, measured on the archived postings: 8+ reads IN
        # because the 1.2-stretch reaches 8.0, and the reason must not claim the 6.8-year
        # record clears it.
        r = rf.years_flag("Requirements: 8+ years of experience building production web applications.")
        self.assertEqual(r["flag"], "YEARS_IN")
        self.assertEqual(r["min"], 8)
        self.assertIn("stretch", r["reason"])
        self.assertNotIn("inside the 6.8 yr record", r["reason"])

    def test_no_stated_bar_is_unknown_not_out(self):
        r = rf.years_flag(self.NONE_JD)
        self.assertEqual(r["flag"], "YEARS_UNKNOWN")
        self.assertIn("no years bar stated", r["reason"])

    def test_skill_scoped_bar_never_reads_as_an_overall_floor(self):
        # the UltaHost shape: years attached to one technology, not to the candidate
        r = rf.years_flag("Senior Frontend Engineer. 4+ years of experience with React and TypeScript.")
        self.assertEqual(r["flag"], "YEARS_UNKNOWN")
        self.assertIn("skill", r["reason"])

    def test_preferred_only_bar_does_not_gate(self):
        r = rf.years_flag("Preferred Qualifications\n5+ years of overall engineering experience.")
        self.assertEqual(r["flag"], "YEARS_UNKNOWN")
        self.assertIn("preferred", r["reason"])

    def test_empty_text_is_unknown_with_a_reason(self):
        r = rf.years_flag("")
        self.assertEqual(r["flag"], "YEARS_UNKNOWN")
        self.assertEqual(r["reason"], "no JD text")

    def test_missing_parser_abstains_instead_of_raising(self):
        import jd_years
        with mock.patch.object(jd_years, "_node", return_value=None):
            r = rf.years_flag(self.OUT_JD)
        self.assertEqual(r["flag"], "YEARS_UNKNOWN")
        self.assertIn("node not on PATH", r["reason"])

    def test_parser_crash_abstains(self):
        import jd_years
        with mock.patch.object(jd_years, "band_for_text", side_effect=RuntimeError("boom")):
            r = rf.years_flag(self.OUT_JD)
        self.assertEqual(r["flag"], "YEARS_UNKNOWN")
        self.assertIn("years parser failed", r["reason"])

    def test_warning_line_prints_out_and_only_out(self):
        line = rf.warning_line(None, None, rf.years_flag(self.OUT_JD))
        self.assertIsNotNone(line)
        self.assertTrue(line.startswith("years: "), line)
        self.assertIsNone(rf.warning_line(None, None, rf.years_flag(self.IN_JD)))
        self.assertIsNone(rf.warning_line(None, None, rf.years_flag(self.NONE_JD)))

    def test_years_and_the_other_two_flags_join(self):
        line = rf.warning_line(rf.comp_flag(1_200_000, 1_500_000),
                               rf.tz_flag("Working hours: 9am-6pm GMT."),
                               rf.years_flag(self.OUT_JD))
        self.assertIn("pay: ", line)
        self.assertIn("hours: ", line)
        self.assertIn("years: ", line)


class YearsFlagCli(unittest.TestCase):
    def test_years_mode_reads_a_posting_file(self):
        posting = Path(tempfile.mkdtemp()) / "posting.txt"
        posting.write_text(YearsFlag.OUT_JD, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(REPO / "tools" / "rank_flags.py"),
                               "years", "--text", str(posting)],
                              cwd=REPO, capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("YEARS_OUT", json.loads(proc.stdout)["years"]["flag"])


if __name__ == "__main__":
    unittest.main()
