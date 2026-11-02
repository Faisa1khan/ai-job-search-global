"""Tests for tools/liveness_check.py - proof of closure, never proof of life.

Ported from career-ops-hq/career-ops liveness-core.mjs. These tests pin the two behaviours
that make it safe: it can only ever say `expired` on real closure evidence, and it refuses
to read a closure phrase as a banner when that phrase's own clause is conditional.

The United case is the reason the port exists, and it is also the one place this file
deliberately exceeds upstream: their pattern misses the word "new".
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.liveness_check import (  # noqa: E402
    classify_liveness, job_id_token, normalize_for_match,
)

LONG = "Senior Frontend Engineer React TypeScript remote India. " * 12


def classify(body="", **kw):
    return classify_liveness(body_text=body, **kw)


class TestNormalisation(unittest.TestCase):
    def test_typographic_quotes_fold_to_ascii(self):
        self.assertIn("n'est", normalize_for_match("n\u2019est"))
        self.assertIn('"x"', normalize_for_match("\u201cx\u201d"))

    def test_accents_are_stripped(self):
        self.assertEqual(normalize_for_match("Cette offre n'est plus disponible"),
                         "Cette offre n'est plus disponible")

    def test_line_breaks_survive_when_asked(self):
        self.assertIn("\n", normalize_for_match("a\nb", keep_line_breaks=True))
        self.assertNotIn("\n", normalize_for_match("a\nb"))


class TestClosureEvidence(unittest.TestCase):
    def test_http_gone_is_expired(self):
        self.assertEqual(classify(status=404), {"result": "expired", "code": "http_gone",
                                                "reason": "HTTP 404"})
        self.assertEqual(classify(status=410)["code"], "http_gone")

    def test_united_phrasing_is_caught(self):
        body = ("While we are no longer accepting new applications for this position, our "
                "recruitment team is evaluating all candidates. " + LONG)
        r = classify(body)
        self.assertEqual(r["result"], "expired")
        self.assertEqual(r["code"], "expired_body")

    def test_upstream_phrasing_is_caught(self):
        r = classify("We are no longer accepting applications for this role. " + LONG)
        self.assertEqual(r["result"], "expired")

    def test_filled_position_is_caught(self):
        r = classify("The job you are trying to apply for has been filled. " + LONG)
        self.assertEqual(r["result"], "expired")

    def test_expired_url_redirect_is_caught(self):
        # Upstream's URL rule is narrow on purpose: a Workday-style ?error=true hit.
        r = classify(LONG, final_url="https://wd1.myworkdaysite.com/job/123?error=true")
        self.assertEqual(r["result"], "expired")
        self.assertEqual(r["code"], "expired_url")


class TestConditionalClausesAreNotEvidence(unittest.TestCase):
    def test_applications_until_filled_is_not_closed(self):
        body = ("Applications will be accepted until the position has been filled. "
                "We will contact shortlisted candidates. " + LONG)
        r = classify(body)
        self.assertNotEqual(r["result"], "expired", r)

    def test_once_applications_have_closed_is_not_closed(self):
        body = ("We will reach out once applications have closed for this role. " + LONG)
        r = classify(body)
        self.assertNotEqual(r["result"], "expired", r)


class TestNeverSaysLiveWithoutAControl(unittest.TestCase):
    def test_no_apply_control_is_uncertain(self):
        r = classify(LONG)
        self.assertEqual(r["result"], "uncertain")
        self.assertEqual(r["code"], "no_apply_control")

    def test_apply_control_makes_it_active(self):
        r = classify(LONG, apply_controls=["Apply for this job"])
        self.assertEqual(r["result"], "active")

    def test_short_page_is_uncertain_not_expired(self):
        r = classify("Loading...")
        self.assertEqual(r["result"], "uncertain")
        self.assertEqual(r["code"], "insufficient_content")


class TestAccessBlockedIsNotExpired(unittest.TestCase):
    def test_rate_limit_is_uncertain(self):
        r = classify(status=429, body="Too Many Requests")
        self.assertEqual(r["result"], "uncertain")
        self.assertEqual(r["code"], "access_blocked")

    def test_server_error_is_uncertain(self):
        r = classify(status=502, body="502 Bad Gateway")
        self.assertEqual(r["result"], "uncertain")
        self.assertEqual(r["code"], "server_error")

    def test_bot_challenge_is_uncertain(self):
        r = classify(body="Just a moment... checking your browser before accessing. " + LONG)
        self.assertEqual(r["result"], "uncertain")
        self.assertEqual(r["code"], "bot_challenge")


class TestRedirectGuard(unittest.TestCase):
    def test_job_id_lost_in_redirect_is_uncertain(self):
        url = "https://jobs.ashbyhq.com/Diagrid/06fdf2f3-fff0-4628-b58c-2c07d408e656"
        r = classify(LONG, requested_url=url, final_url="https://jobs.ashbyhq.com/Diagrid")
        self.assertEqual(r["result"], "uncertain")
        self.assertEqual(r["code"], "redirected_off_posting")

    def test_job_id_token_reads_uuid_and_numeric(self):
        self.assertEqual(job_id_token("https://x/jobs/4481841452"), "4481841452")
        self.assertTrue(job_id_token(
            "https://jobs.ashbyhq.com/Diagrid/06fdf2f3-fff0-4628-b58c-2c07d408e656"))


if __name__ == "__main__":
    unittest.main()
