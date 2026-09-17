"""Unit tests for tools/verify_sot.py."""

import unittest
from pathlib import Path

from tools.verify_sot import check_sot_grounding, verify_sot


class TestSOTRules(unittest.TestCase):
    def test_canonical_numbers_pass(self):
        lines = [
            (1, "Project Nexus: 29 ADRs, 25 Playwright test suites, and 16 feature modules."),
            (2, "Acme: delivered across 8 core modules, serving 10,000+ active enterprise users."),
            (3, "Integrated 42 OpenAPI endpoints against external payroll gateway."),
        ]
        violations = check_sot_grounding(lines)
        self.assertEqual(violations, [])

    def test_superseded_adrs_detected(self):
        lines = [(1, "Guided by 30 ADRs in production.")]
        violations = check_sot_grounding(lines)
        self.assertEqual(len(violations), 1)
        self.assertIn("29 ADRs", violations[0])

    def test_superseded_test_suites_detected(self):
        lines = [(1, "Validated across 14 test suites in CI.")]
        violations = check_sot_grounding(lines)
        self.assertEqual(len(violations), 1)
        self.assertIn("25 Playwright suites", violations[0])

    def test_unauthenticated_scale_detected(self):
        lines = [
            (1, "Scaled to 500,000+ employees across regions."),
            (2, "Handled 100k monthly transactions."),
        ]
        violations = check_sot_grounding(lines)
        self.assertEqual(len(violations), 2)
        self.assertTrue(any("500k scale" in v for v in violations))
        self.assertTrue(any("100k" in v for v in violations))

    def test_platform_framed_scale_is_allowed(self):
        # SOT Section 1/7: the platform figure is valid when attributed to the platform.
        lines = [
            (1, "Integrated Gemini AI into recruitment on a platform serving 500k+ employees."),
            (2, "Acme platform scale: 100,000+ monthly payroll transactions."),
        ]
        self.assertEqual(check_sot_grounding(lines), [])

    def test_pci_dss_certification_claim_detected_but_bridge_allowed(self):
        self.assertEqual(
            len(check_sot_grounding([(1, "Holds PCI-DSS certification.")])),
            1,
        )
        self.assertEqual(
            check_sot_grounding([(1, "Audit discipline closer to what PCI-DSS workflows demand.")]),
            [],
        )

    def test_advisory_metrics_warn_without_failing(self):
        warnings: list[str] = []
        lines = [
            (1, "Reduced Time-to-Interactive from 2.1s to 120ms."),
            (2, "Eliminated an 800ms freeze with a closed-form calculation."),
        ]
        self.assertEqual(check_sot_grounding(lines, warnings=warnings), [])
        self.assertEqual(len(warnings), 2)
        self.assertTrue(all("advisory" in w for w in warnings))

    def test_hard_exclusions_detected(self):
        lines = [
            (1, "Built KeeLead payment workflows."),
            (2, "Holds PCI-DSS certification."),
            (3, "Resolved ticket QN-4633 in sprint 4."),
            (4, "Claimed a US green card authorization."),
            (5, "Refurso's 65% UI turnaround."),
        ]
        violations = check_sot_grounding(lines)
        self.assertEqual(len(violations), 5)
        self.assertTrue(any("KeeLead" in v for v in violations))
        self.assertTrue(any("PCI-DSS" in v for v in violations))
        self.assertTrue(any("QN-*" in v or "Jira" in v for v in violations))


if __name__ == "__main__":
    unittest.main()
