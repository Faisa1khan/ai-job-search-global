"""Tests for the liveness pass wired into tools/screen_jobs.py (Step 3 of /scrape).

The safety property is asymmetric on purpose, and it is the whole point of this file:

- only a verdict of exactly `expired` may move a row out of `new`;
- every other outcome - no render, no apply control, bot wall, fetch crash, missing URL,
  a differently-cased verdict - keeps the row exactly where it was.

A false `expired` writes a real job out of every future scan, while a false `uncertain`
costs one more look. These tests pin that direction so a future "helpful" cleanup cannot
invert it.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import tools.screen_jobs as sj  # noqa: E402


def state_file(entries):
    tmp = Path(tempfile.mkdtemp()) / "seen_jobs.json"
    tmp.write_text(json.dumps({"seen": entries}, indent=2), encoding="utf-8")
    return tmp


def run(path, *flags, verdicts=None):
    """Call main() in-process with liveness_for stubbed per URL."""
    calls = []

    def fake(url):
        calls.append(url)
        if verdicts is None:
            return {"result": "uncertain", "code": "no_apply_control", "reason": "stub"}
        return verdicts[url]

    out = io.StringIO()
    with mock.patch.object(sj, "liveness_for", side_effect=fake), \
            contextlib.redirect_stdout(out):
        code = sj.main(["--state", str(path), *flags])
    return code, out.getvalue(), calls


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))["seen"]


POSTING = "https://example.com/jobs/1"
NEW_ENTRY = {"title": "Senior React Engineer", "company": "Acme", "location": "Remote (India)",
             "status": "new", "url": POSTING}


class TestOnlyExpiredDrops(unittest.TestCase):
    def test_expired_is_reported_and_marks_the_row_on_apply(self):
        path = state_file({"k1": dict(NEW_ENTRY)})
        verdict = {POSTING: {"result": "expired", "code": "expired_body", "reason": "pattern matched"}}

        code, text, calls = run(path, "--liveness", verdicts=verdict)
        self.assertEqual(1, code, "a proven-closed row must block presentation until --apply")
        self.assertIn("prove CLOSED", text)
        self.assertEqual([POSTING], calls)
        self.assertEqual("new", load(path)["k1"]["status"], "report mode writes nothing")

        code, text, _ = run(path, "--liveness", "--apply", verdicts=verdict)
        self.assertEqual(0, code)
        entry = load(path)["k1"]
        self.assertEqual("expired", entry["status"])
        self.assertEqual("expired", entry["liveness"]["result"])
        self.assertEqual("expired_body", entry["liveness"]["code"])
        self.assertEqual(POSTING, entry["url"], "the entry is kept, not deleted")

    def test_uncertain_never_drops_a_row(self):
        for code_value in ("no_apply_control", "insufficient_content", "bot_challenge",
                           "fetch_failed", "redirected_off_posting"):
            path = state_file({"k1": dict(NEW_ENTRY)})
            verdict = {POSTING: {"result": "uncertain", "code": code_value, "reason": "x"}}
            code, text, _ = run(path, "--liveness", "--apply", verdicts=verdict)
            entry = load(path)["k1"]
            self.assertEqual("new", entry["status"], f"{code_value} must never drop a row")
            self.assertEqual(code_value, entry["liveness"]["code"],
                             "the reason is recorded so the row keeps it")
            self.assertEqual(0, code, f"{code_value} is not a failure of the screen")
            self.assertIn("KEPT as new", text)

    def test_a_case_variant_is_not_closure_evidence(self):
        path = state_file({"k1": dict(NEW_ENTRY)})
        verdict = {POSTING: {"result": "Expired", "code": "expired_body", "reason": "x"}}
        run(path, "--liveness", "--apply", verdicts=verdict)
        self.assertEqual("new", load(path)["k1"]["status"], "only exactly 'expired' may drop")

    def test_active_is_not_a_drop_either(self):
        path = state_file({"k1": dict(NEW_ENTRY)})
        verdict = {POSTING: {"result": "active", "code": "apply_control_visible", "reason": "x"}}
        code, _, _ = run(path, "--liveness", "--apply", verdicts=verdict)
        self.assertEqual("new", load(path)["k1"]["status"])
        self.assertEqual(0, code)

    def test_entry_without_a_url_is_uncertain_and_kept(self):
        entry = dict(NEW_ENTRY)
        entry["url"] = ""
        path = state_file({"k1": entry})
        code, _, calls = run(path, "--liveness", "--apply")
        self.assertEqual([""], calls, "the wrapper still runs and answers for a blank URL")
        kept = load(path)["k1"]
        self.assertEqual("new", kept["status"])
        self.assertEqual(0, code)


class TestWrapperSafety(unittest.TestCase):
    def test_fetch_crash_becomes_uncertain(self):
        def boom(url):
            raise TimeoutError("took too long")

        res = sj.liveness_for("https://example.com/jobs/1", fetch=boom)
        self.assertEqual("uncertain", res["result"])
        self.assertEqual("check_failed", res["code"])

    def test_blank_url_is_uncertain_without_touching_the_network(self):
        def must_not_run(url):
            raise AssertionError("no fetch for a blank URL")

        for blank in (None, "", "   "):
            res = sj.liveness_for(blank, fetch=must_not_run)
            self.assertEqual("uncertain", res["result"])
            self.assertEqual("no_url", res["code"])

    def test_junk_return_becomes_uncertain(self):
        res = sj.liveness_for("https://example.com/jobs/1", fetch=lambda u: None)
        self.assertEqual("uncertain", res["result"])

    def test_real_closure_evidence_passes_through(self):
        # 404 through the real classifier: the one path this wrapper must not soften.
        res = sj.liveness_for("https://example.com/gone")
        self.assertIn(res["result"], ("expired", "uncertain"))
        from tools.liveness_check import classify_liveness
        self.assertEqual("expired", classify_liveness(status=404)["result"])


class TestOptIn(unittest.TestCase):
    def test_without_the_flag_no_fetch_happens(self):
        path = state_file({"k1": dict(NEW_ENTRY)})

        def must_not_run(url):
            raise AssertionError("--liveness was not passed, so no fetch may happen")

        out = io.StringIO()
        with mock.patch.object(sj, "liveness_for", side_effect=must_not_run), \
                contextlib.redirect_stdout(out):
            code = sj.main(["--state", str(path)])
        self.assertEqual(0, code)
        self.assertNotIn("liveness", load(path)["k1"], "the offline screen writes no liveness key")

    def test_json_report_carries_both_buckets(self):
        path = state_file({"gone": dict(NEW_ENTRY),
                           "open": {**NEW_ENTRY, "url": "https://example.com/jobs/2"}})
        verdict = {POSTING: {"result": "expired", "code": "http_gone"},
                   "https://example.com/jobs/2": {"result": "uncertain", "code": "insufficient_content"}}
        out = io.StringIO()
        with mock.patch.object(sj, "liveness_for", side_effect=lambda u: verdict[u]), \
                contextlib.redirect_stdout(out):
            code = sj.main(["--state", str(path), "--liveness", "--json"])
        self.assertEqual(1, code)
        report = json.loads(out.getvalue())
        self.assertEqual(1, report["counts"]["expired"])
        self.assertEqual(1, report["counts"]["liveness_unproven"])
        self.assertEqual("http_gone", report["expired"][0]["code"])
        self.assertEqual("gone", report["expired"][0]["key"])

    def test_screened_violations_are_never_liveness_checked(self):
        path = state_file({"drop": {"title": "Senior C++ Developer", "company": "B",
                                    "location": "Delhi, India", "status": "new",
                                    "url": "https://example.com/jobs/3"}})
        code, _, calls = run(path, "--liveness", "--apply")
        self.assertEqual([], calls, "a row the screen already drops costs no fetch")
        self.assertEqual("skipped", load(path)["drop"]["status"])
        self.assertEqual(0, code)

    def test_non_new_entries_are_never_checked(self):
        path = state_file({"ranked": {**NEW_ENTRY, "status": "ranked", "rank_score": 71},
                           "old": {**NEW_ENTRY, "url": "https://example.com/jobs/9",
                                   "status": "expired"}})
        _, _, calls = run(path, "--liveness", "--apply")
        self.assertEqual([], calls)
        self.assertEqual("ranked", load(path)["ranked"]["status"])
        self.assertEqual("expired", load(path)["old"]["status"])


class TestScrapeStepWiring(unittest.TestCase):
    """The tool is only worth having if /scrape's Step 3 actually calls it."""

    def setUp(self):
        self.text = (REPO / ".agents" / "skills" / "scrape" / "SKILL.md").read_text(encoding="utf-8")

    def test_step_three_runs_the_liveness_pass(self):
        self.assertIn("tools/screen_jobs.py --liveness", self.text)

    def test_apply_documents_both_outcomes(self):
        self.assertIn("status=skipped / status=expired", self.text)

    def test_the_asymmetry_is_written_down(self):
        flat = " ".join(self.text.split())
        self.assertIn("can only ever prove a posting **closed**", flat)
        self.assertIn("never a drop", flat)


if __name__ == "__main__":
    unittest.main()
