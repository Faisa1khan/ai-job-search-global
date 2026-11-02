"""Tests for tools/precheck_duplicate.py - "have I applied here before?", advisory.

Every case below comes from the tracker on 2026-10-30. The one that matters most is the
JioStar pair: two rows at one company, different requisitions, which must NOT be reported
as one posting. Collapsing siblings into duplicates is the silent failure this tool could
introduce, so it is pinned here.
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.precheck_duplicate import (  # noqa: E402
    company_relation, find_duplicates, norm_req, normalize_url, role_fuzzy_match,
    strip_location_suffix, title_identity_key,
)

ROWS = [
    {"date": "2026-10-30", "company": "JioStar", "role": "Senior Software Development Engineer",
     "status": "applied", "notes": "", "source": ""},
    {"date": "2026-09-28", "company": "JioStar",
     "role": "Senior Software Engineer - Frontend (Video Insights)", "status": "rejected",
     "notes": "", "source": ""},
    {"date": "2026-10-30", "company": "Intellias", "role": "Senior React + Next.js Engineer",
     "status": "applied", "notes": "", "source": ""},
    {"date": "2026-10-29", "company": "Intellias",
     "role": "Naukri application (role not stated in receipt)", "status": "applied",
     "notes": "", "source": ""},
    {"date": "2026-10-16", "company": "BJAK",
     "role": "Full Stack Software Engineer - AI Finance Agent", "status": "applied",
     "notes": "", "source": "https://jobs.ashbyhq.com/bjakcareer/08454ce3-a782-45b8-834e-a3c9452b1647"},
]


class TestUrlKey(unittest.TestCase):
    def test_tracking_params_are_dropped(self):
        a = normalize_url("https://jobs.ashbyhq.com/bjakcareer/08454ce3?utm_source=x&utm_medium=y")
        b = normalize_url("https://jobs.ashbyhq.com/bjakcareer/08454ce3")
        self.assertEqual(a, b)

    def test_functional_param_survives(self):
        k = normalize_url("https://boards.example.com/apply?gh_jid=12345")
        self.assertIn("gh_jid=12345", k)

    def test_scheme_and_trailing_slash_are_normalised(self):
        self.assertEqual(normalize_url("http://Example.com/jobs/9/"),
                         normalize_url("https://example.com/jobs/9"))

    def test_placeholder_has_no_key(self):
        for junk in ("N/A", "TBD", "", "not a url", "local:jds/x"):
            self.assertEqual(normalize_url(junk), "", junk)


class TestReqNumber(unittest.TestCase):
    def test_label_and_separator_variants_collapse(self):
        self.assertEqual(norm_req("JR9727"), norm_req("JR-9727"))
        self.assertEqual(norm_req("REQ-2026-32061"), norm_req("2026-32061"))

    def test_body_is_never_altered(self):
        self.assertNotEqual(norm_req("JR9727"), norm_req("JR9728"))


class TestTitles(unittest.TestCase):
    def test_identity_is_order_and_accent_free(self):
        self.assertEqual(title_identity_key("Senior React Engineer"),
                         title_identity_key("React Senior Engineer"))
        self.assertEqual(title_identity_key("Développeur Frontend"),
                         title_identity_key("Developpeur Frontend"))

    def test_location_suffix_is_stripped(self):
        self.assertEqual(strip_location_suffix("Senior Frontend Engineer (Remote)"),
                         "Senior Frontend Engineer")
        self.assertEqual(strip_location_suffix("Senior Engineer (Gurgaon)"), "Senior Engineer")

    def test_team_suffix_is_kept(self):
        self.assertEqual(strip_location_suffix("Software Engineer (Backend)"),
                         "Software Engineer (Backend)")

    def test_level_marker_is_kept(self):
        self.assertEqual(strip_location_suffix("Engineer (II)"), "Engineer (II)")


class TestRoleMatch(unittest.TestCase):
    def test_seniority_disagreement_blocks(self):
        self.assertFalse(role_fuzzy_match("Senior Frontend Engineer", "Principal Frontend Engineer"))

    def test_sub_baseline_qualifier_blocks(self):
        self.assertFalse(role_fuzzy_match("Associate Product Manager", "Product Manager"))

    def test_close_titles_match(self):
        self.assertTrue(role_fuzzy_match("Senior Frontend Engineer", "Senior Frontend Developer"))

    def test_distinct_requisitions_do_not_match(self):
        self.assertFalse(role_fuzzy_match("Senior Software Development Engineer",
                                          "Senior Software Engineer - Frontend (Video Insights)"))


class TestCompanyRelation(unittest.TestCase):
    def test_case_and_form_insensitive(self):
        self.assertEqual(company_relation("BJAK", "Bjak"), "same")
        self.assertEqual(company_relation("Acme Pvt Ltd", "Acme"), "same")

    def test_unrelated_is_none(self):
        self.assertIsNone(company_relation("BJAK", "Barclays"))


class TestFindDuplicates(unittest.TestCase):
    def test_exact_url_beats_everything(self):
        c = find_duplicates(ROWS, url="https://jobs.ashbyhq.com/bjakcareer/08454ce3-a782-45b8-834e-a3c9452b1647?utm_source=x")
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["reason"], "url")

    def test_same_title_found(self):
        c = find_duplicates(ROWS, company="Intellias", title="Senior React + Next.js Engineer")
        self.assertEqual([x["reason"] for x in c], ["same-title"])

    def test_rejection_carries_a_warning(self):
        c = find_duplicates(ROWS, company="JioStar",
                            title="Senior Software Engineer - Frontend (Video Insights)")
        self.assertEqual(len(c), 1)
        self.assertTrue(c[0]["warning"])
        self.assertEqual(c[0]["status"], "rejected")

    def test_sibling_requisition_is_not_a_duplicate(self):
        # The September rejection must NOT be returned when checking today's different req.
        c = find_duplicates(ROWS, company="JioStar", title="Senior Software Development Engineer")
        self.assertEqual([x["role"] for x in c], ["Senior Software Development Engineer"])

    def test_unknown_company_is_no_match(self):
        self.assertEqual(find_duplicates(ROWS, company="Nonexistent", title="Senior Engineer"), [])


class TestCliSafety(unittest.TestCase):
    def test_company_alone_is_refused(self):
        from tools.precheck_duplicate import main
        self.assertEqual(main(["--company", "BJAK"]), 1)

    def test_unusable_url_is_refused(self):
        from tools.precheck_duplicate import main
        self.assertEqual(main(["--company", "BJAK", "--url", "N/A"]), 1)


if __name__ == "__main__":
    unittest.main()
