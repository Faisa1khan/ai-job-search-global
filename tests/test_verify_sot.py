"""Unit tests for tools/verify_sot.py.

The gate is a mechanism, so these tests build rule sets in a temp directory and
check both directions: a document that breaks a rule fails, a document that keeps
it passes. Nothing here depends on any particular candidate's claims.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.verify_sot import (
    EXAMPLE_RULES_PATH,
    SOTVerificationError,
    check_sot_grounding,
    load_rules,
)

RULES = {
    "platform_framing_markers": ["platform", "product line"],
    "superseded_figures": [
        {"pattern": r"\b12\s+ADRs?\b", "message": "the ADR count is superseded"},
    ],
    "hard_exclusions": [
        {"pattern": r"\b(?:ISO|SOC)\s*2?\s*27001\b", "message": "certification not held"},
    ],
    "scale_figures": [
        {"pattern": r"\b\d{3}[,.]?000\+?\s+employees\b", "message": "needs platform framing"},
    ],
    "advisory_metrics": [
        {"pattern": r"\bp9\d\s+latency\b", "message": "percentile latency needs its method"},
    ],
}


class SOTRuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.rules_path = Path(self.tmp.name) / "rules.json"
        self.rules_path.write_text(json.dumps(RULES), encoding="utf-8")
        self.rules = load_rules(self.rules_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def check(self, lines, warnings=None):
        return check_sot_grounding(lines, warnings=warnings, rules=self.rules)


class TestRuleLoading(SOTRuleTestCase):
    def test_classes_compiled(self):
        self.assertEqual(len(self.rules["superseded_figures"]), 1)
        self.assertEqual(len(self.rules["hard_exclusions"]), 2)  # rule + built-in key rule
        self.assertEqual(len(self.rules["scale_figures"]), 1)
        self.assertEqual(len(self.rules["advisory_metrics"]), 1)
        self.assertEqual(self.rules["source"], str(self.rules_path))

    def test_shipped_example_is_valid(self):
        rules = load_rules(EXAMPLE_RULES_PATH)
        self.assertEqual(rules["source"], str(EXAMPLE_RULES_PATH))
        self.assertTrue(rules["hard_exclusions"])

    def test_malformed_json_raises(self):
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(SOTVerificationError):
            load_rules(bad)

    def test_invalid_regex_raises(self):
        bad = Path(self.tmp.name) / "badre.json"
        bad.write_text(json.dumps({"hard_exclusions": [{"pattern": "(", "message": "x"}]}), encoding="utf-8")
        with self.assertRaises(SOTVerificationError):
            load_rules(bad)

    def test_missing_explicit_path_raises(self):
        with self.assertRaises(SOTVerificationError):
            load_rules(Path(self.tmp.name) / "absent.json")

    def test_env_var_selects_rule_file(self):
        with mock.patch.dict(os.environ, {"JOBSEARCH_SOT_RULES": str(self.rules_path)}, clear=False):
            rules = load_rules()
        self.assertEqual(rules["source"], str(self.rules_path))


class TestSupersededFigures(SOTRuleTestCase):
    def test_superseded_figure_fails(self):
        violations = self.check([(1, "Guided by 12 ADRs in production.")])
        self.assertEqual(len(violations), 1)
        self.assertIn("superseded", violations[0])

    def test_current_figure_passes(self):
        self.assertEqual(self.check([(1, "Guided by 29 ADRs in production.")]), [])


class TestHardExclusions(SOTRuleTestCase):
    def test_exclusion_fails(self):
        violations = self.check([(1, "Holds ISO 27001 certification.")])
        self.assertEqual(len(violations), 1)
        self.assertIn("certification not held", violations[0])

    def test_work_item_key_fails_by_default(self):
        violations = self.check([(1, "Resolved TICKET-123 in sprint 4.")])
        self.assertEqual(len(violations), 1)
        self.assertIn("work-item", violations[0])

    def test_work_item_prefix_is_configurable(self):
        with mock.patch.dict(os.environ, {"JOBSEARCH_INTERNAL_KEY_PREFIXES": "ACME"}, clear=False):
            rules = load_rules(self.rules_path)
        violations = check_sot_grounding([(1, "Resolved ACME-77.")], rules=rules)
        self.assertEqual(len(violations), 1)
        self.assertEqual(check_sot_grounding([(1, "Resolved TICKET-123.")], rules=rules), [])


class TestScaleFigures(SOTRuleTestCase):
    def test_unframed_scale_fails(self):
        violations = self.check([(1, "Scaled to 500,000 employees across regions.")])
        self.assertEqual(len(violations), 1)
        self.assertIn("platform framing", violations[0])

    def test_platform_framed_scale_passes(self):
        self.assertEqual(
            self.check([(1, "Shipped on a platform serving 500,000 employees.")]),
            [],
        )

    def test_custom_framing_markers_respected(self):
        custom = Path(self.tmp.name) / "custom.json"
        custom.write_text(
            json.dumps(
                {
                    "platform_framing_markers": ["suite"],
                    "scale_figures": [{"pattern": r"\b\d{3}[,.]?000\+?\s+employees\b", "message": "m"}],
                }
            ),
            encoding="utf-8",
        )
        rules = load_rules(custom)
        self.assertEqual(check_sot_grounding([(1, "The suite serves 500,000 employees.")], rules=rules), [])
        self.assertEqual(
            len(check_sot_grounding([(1, "I serve 500,000 employees.")], rules=rules)),
            1,
        )


class TestAdvisories(SOTRuleTestCase):
    def test_advisory_warns_without_failing(self):
        warnings: list[str] = []
        violations = self.check([(1, "Improved p95 latency by 40%.")], warnings=warnings)
        self.assertEqual(violations, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("advisory", warnings[0])

    def test_advisory_absent_when_no_match(self):
        warnings: list[str] = []
        self.check([(1, "Improved the interface.")], warnings=warnings)
        self.assertEqual(warnings, [])


class TestNoRules(SOTRuleTestCase):
    def test_empty_ruleset_only_checks_work_item_keys(self):
        bare = Path(self.tmp.name) / "bare.json"
        bare.write_text("{}", encoding="utf-8")
        rules = load_rules(bare)
        self.assertEqual(check_sot_grounding([(1, "Guided by 12 ADRs.")], rules=rules), [])
        self.assertEqual(
            len(check_sot_grounding([(1, "Closed PROJ-1.")], rules=rules)),
            1,
        )


if __name__ == "__main__":
    unittest.main()
