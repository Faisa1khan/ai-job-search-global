"""Providers added to tools/ats_board_check.py: SmartRecruiters and the EU Lever host.

Why these tests exist. The board checker is the deterministic half of the
section-9 sweep lane: a dork finds a posting, the index lies about it, and this
script reads the employer's own board API for the truth. Two providers were
added on 2026-10-07, both verified against the live APIs first:

  * SmartRecruiters - the slug is CASE-EXACT. A wrong-case slug answers HTTP 200
    with `content: []` and `totalFound: 0`, so a bad slug is indistinguishable
    from an empty board unless the total is carried through as `board_total`.
    The list endpoint also paginates (limit=100 here) while `totalFound` reports
    the whole board, so a truncated listing must be visible, never silently
    passed off as complete.
  * Lever EU - European tenants are served from api.eu.lever.co, not
    api.lever.co. Same payload shape, different host, and the payload alone
    cannot tell you the wrong host answered.

These are offline tests: `fetch_json` is replaced, so they pin the request URL,
the field mapping and the verdict rules without touching the network.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import ats_board_check as abc  # noqa: E402


class ParseTarget(unittest.TestCase):
    def test_smartrecruiters_url_with_posting_id(self):
        provider, slug, pid = abc.parse_target(
            "https://jobs.smartrecruiters.com/BoschGroup/744000154191149"
        )
        self.assertEqual((provider, slug, pid), ("smartrecruiters", "BoschGroup", "744000154191149"))

    def test_smartrecruiters_board_url_without_id(self):
        provider, slug, pid = abc.parse_target("https://jobs.smartrecruiters.com/SGS")
        self.assertEqual((provider, slug, pid), ("smartrecruiters", "SGS", None))

    def test_smartrecruiters_prefix_form(self):
        provider, slug, pid = abc.parse_target("smartrecruiters:BoschGroup")
        self.assertEqual((provider, slug, pid), ("smartrecruiters", "BoschGroup", None))

    def test_lever_eu_host_is_its_own_provider(self):
        provider, slug, _ = abc.parse_target(
            "https://jobs.eu.lever.co/leverdemo/33538a2f-d27d-4a96-8f0a-1b2c3d4e5f60"
        )
        self.assertEqual(provider, "lever-eu")
        self.assertEqual(slug, "leverdemo")

    def test_lever_eu_prefix_form(self):
        provider, slug, _ = abc.parse_target("lever-eu:leverdemo")
        self.assertEqual((provider, slug), ("lever-eu", "leverdemo"))

    def test_original_providers_unchanged(self):
        """Regression guard: the three pre-existing providers still resolve."""
        self.assertEqual(abc.parse_target("ashby:g2i")[0], "ashby")
        self.assertEqual(abc.parse_target("greenhouse:cloudbeds")[0], "greenhouse")
        self.assertEqual(abc.parse_target("lever:jobgether")[0], "lever")
        self.assertEqual(
            abc.parse_target("https://jobs.lever.co/jobgether/275c1010-2ebe-40e4-88a2-0c44b4f6fb9b")[1],
            "jobgether",
        )

    def test_a_slug_that_starts_with_digits_is_not_eaten_by_the_id_group(self):
        provider, slug, pid = abc.parse_target("https://jobs.smartrecruiters.com/1Company")
        self.assertEqual((provider, slug, pid), ("smartrecruiters", "1Company", None))


class SmartRecruiters(unittest.TestCase):
    def _posting(self):
        return {
            "id": "744000154191149",
            "name": "Full Stack with C# & Angular",
            "releasedDate": "2026-10-07T00:00:00.000Z",
            "applyUrl": "https://jobs.smartrecruiters.com/BoschGroup/744000154191149-x",
            "active": True,
            "location": {"city": "hosur road bangalore", "region": "ka", "country": "in"},
        }

    def test_single_posting_is_live_with_provider_fields(self):
        with mock.patch.object(abc, "fetch_json", return_value=(self._posting(), 200, "")):
            r = abc.check_smartrecruiters("BoschGroup", "744000154191149")
        self.assertEqual(r["verdict"], "LIVE")
        self.assertEqual(r["posting"]["title"], "Full Stack with C# & Angular")
        self.assertEqual(r["posting"]["posted_date"], "2026-10-07")
        self.assertIn("bangalore", r["posting"]["location"])
        self.assertIn("in", r["posting"]["location"])

    def test_single_posting_404_is_gone_not_unknown(self):
        """A 404 on the employer's own board API is an expiry verdict."""
        with mock.patch.object(abc, "fetch_json", return_value=(None, 404, "")):
            r = abc.check_smartrecruiters("BoschGroup", "744000154191149")
        self.assertEqual(r["verdict"], "GONE")

    def test_board_listing_reports_the_whole_board_as_board_total(self):
        payload = {"totalFound": 555, "content": [self._posting() for _ in range(3)]}
        with mock.patch.object(abc, "fetch_json", return_value=(payload, 200, "")):
            r = abc.check_smartrecruiters("BoschGroup", None)
        self.assertEqual(r["verdict"], "LIVE")
        self.assertEqual(r["board_size"], 3)
        self.assertEqual(r["board_total"], 555, "a paginated listing must show the board total, not just the page")

    def test_country_filter_reaches_the_request_url(self):
        seen = {}

        def fake(url):
            seen["url"] = url
            return ({"totalFound": 0, "content": []}, 200, "")

        abc.BOARD_QUERY["country"] = "in"
        try:
            with mock.patch.object(abc, "fetch_json", side_effect=fake):
                abc.check_smartrecruiters("BoschGroup", None)
        finally:
            abc.BOARD_QUERY.pop("country", None)
        self.assertIn("country=in", seen["url"], "the --country filter must be sent, not applied client-side")

    def test_wrong_case_slug_looks_like_an_empty_board_but_carries_the_total(self):
        """The documented trap: 200 + empty content is a bad slug, not an empty board."""
        with mock.patch.object(abc, "fetch_json", return_value=({"totalFound": 0, "content": []}, 200, "")):
            r = abc.check_smartrecruiters("bosch", None)
        self.assertEqual(r["verdict"], "LIVE")
        self.assertEqual((r["board_size"], r["board_total"]), (0, 0))


class LeverEuHost(unittest.TestCase):
    def test_eu_provider_targets_the_eu_host(self):
        seen = {}

        def fake(url):
            seen["url"] = url
            return ([], 200, "")

        with mock.patch.object(abc, "fetch_json", side_effect=fake):
            r = abc.CHECKERS["lever-eu"]("leverdemo", None)
        self.assertIn("api.eu.lever.co", seen["url"])
        self.assertNotIn("//api.lever.co", seen["url"])
        self.assertEqual(r["verdict"], "LIVE")

    def test_default_lever_still_targets_the_us_host(self):
        seen = {}
        with mock.patch.object(abc, "fetch_json", side_effect=lambda url: (seen.update(url=url), ([], 200, ""))[1]):
            abc.check_lever("someboard", None)
        self.assertIn("api.lever.co", seen["url"])
        self.assertNotIn("api.eu.lever.co", seen["url"])


if __name__ == "__main__":
    unittest.main()
