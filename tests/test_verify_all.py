"""Unit tests for tools/verify_all.py composite verification suite."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.verify_all import verify_package

ROOT = Path(__file__).resolve().parent.parent


class TestVerifyAll(unittest.TestCase):
    def setUp(self):
        self.master_html = ROOT / "cv" / "Resume_Master.html"
        self.master_pdf = ROOT / "cv" / "Resume_Master.pdf"

    def test_verify_package_runs_on_master_with_gates(self):
        if not self.master_html.exists() or not self.master_pdf.exists():
            self.skipTest("Master resume files not found")

        # All 5 gates run: the canonical Master must be the definition of
        # compliant, so skipping humanizer here would hide gate miscalibration.
        res = verify_package(self.master_html, self.master_pdf, expected_pages=1)
        self.assertTrue(res["pdf_clean"], res["errors"])
        self.assertTrue(res["layout_clean"], res["errors"])
        self.assertTrue(res["template_clean"], res["errors"])
        self.assertTrue(res["humanizer_clean"], res["errors"])
        self.assertTrue(res["sot_clean"], res["errors"])
        self.assertEqual(res["pages"], 1)

    def test_verify_package_passes_on_master_cover_letter(self):
        cl_html = ROOT / "cover_letters" / "Cover_Letter_Master.html"
        cl_pdf = ROOT / "cover_letters" / "Cover_Letter_Master.pdf"
        if not cl_html.exists() or not cl_pdf.exists():
            self.skipTest("Master cover letter files not found")

        res = verify_package(cl_html, cl_pdf, expected_pages=1)
        self.assertTrue(res["success"], res["errors"])

    def test_skip_parameter_bypasses_all_gates(self):
        if not self.master_html.exists() or not self.master_pdf.exists():
            self.skipTest("Master resume files not found")

        res = verify_package(
            self.master_html,
            self.master_pdf,
            skip={"layout", "template", "humanizer", "sot"},
        )
        self.assertTrue(res["layout_clean"])
        self.assertTrue(res["template_clean"])
        self.assertTrue(res["humanizer_clean"])
        self.assertTrue(res["sot_clean"])

    def test_missing_pdf_fails_cleanly(self):
        non_existent = ROOT / "cv" / "non_existent_doc.pdf"
        res = verify_package(
            self.master_html,
            non_existent,
            skip={"layout", "template", "humanizer", "sot"},
        )
        self.assertFalse(res["success"])
        self.assertFalse(res["pdf_clean"])
        self.assertEqual(res["pages"], "overflow")
        self.assertTrue(any("PDF" in e for e in res["errors"]))


if __name__ == "__main__":
    unittest.main()
