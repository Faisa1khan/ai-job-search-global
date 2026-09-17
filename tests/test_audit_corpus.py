"""Unit tests for tools/audit_corpus.py (corpus sweep helpers)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import audit_corpus


class TestCollectPairs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "cv").mkdir()
        (self.root / "cover_letters").mkdir()

    def _touch(self, rel: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        return path

    def test_pairs_require_both_html_and_pdf(self):
        self._touch("cv/Resume_Acme.html")
        self._touch("cv/Resume_Acme.pdf")
        self._touch("cv/Resume_Orphan.html")
        self._touch("cover_letters/Cover_Letter_Acme.html")
        self._touch("cover_letters/Cover_Letter_Acme.pdf")
        self._touch("cover_letters/Cover_Letter_Orphan.pdf")

        pairs = audit_corpus.collect_pairs(self.root)
        names = sorted(html.name for html, _ in pairs)
        self.assertEqual(names, ["Cover_Letter_Acme.html", "Resume_Acme.html"])

    def test_company_filter_is_case_insensitive_substring(self):
        for name in ("Acme", "Weave"):
            self._touch(f"cv/Resume_{name}.html")
            self._touch(f"cv/Resume_{name}.pdf")
        pairs = audit_corpus.collect_pairs(self.root, company="weave")
        self.assertEqual([html.name for html, _ in pairs], ["Resume_Weave.html"])


class TestSummarize(unittest.TestCase):
    def test_counts_passes_failures_and_per_gate_failures(self):
        results = [
            {"failed_gates": []},
            {"failed_gates": ["humanizer"]},
            {"failed_gates": ["humanizer", "sot"]},
        ]
        summary = audit_corpus.summarize(results)
        self.assertEqual(summary["pairs"], 3)
        self.assertEqual(summary["passing"], 1)
        self.assertEqual(summary["failing"], 2)
        self.assertEqual(summary["per_gate_failures"]["humanizer"], 2)
        self.assertEqual(summary["per_gate_failures"]["sot"], 1)
        self.assertEqual(summary["per_gate_failures"]["layout"], 0)


class TestWriteState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._root = audit_corpus.ROOT
        audit_corpus.ROOT = Path(self.tmp.name)
        audit_corpus.STATE_FILE = audit_corpus.ROOT / "documents" / "verification_state.json"
        self.addCleanup(self._restore)

    def _restore(self):
        audit_corpus.ROOT = self._root
        audit_corpus.STATE_FILE = self._root / "documents" / "verification_state.json"

    def _pair(self, name: str, body: str) -> dict:
        html_rel = f"cv/{name}.html"
        pdf_rel = f"cv/{name}.pdf"
        for rel, content in ((html_rel, body), (pdf_rel, "pdf-bytes")):
            path = audit_corpus.ROOT / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return {"html": html_rel, "pdf": pdf_rel, "success": True, "failed_gates": [], "errors": []}

    def test_state_records_hashes_and_flags_content_drift(self):
        result = self._pair("Resume_Acme", "one")
        first = audit_corpus.write_state([result], {})
        state = json.loads(Path(first["written"]).read_text(encoding="utf-8"))
        entry = state["cv/Resume_Acme.pdf"]
        self.assertTrue(entry["success"])
        self.assertEqual(len(entry["html_sha256"]), 64)
        self.assertEqual(len(entry["pdf_sha256"]), 64)

        # Unchanged content: no drift reported.
        second = audit_corpus.write_state([result], state)
        self.assertEqual(second["changed_since_last_run"], [])

        # Edited PDF: drift reported with the previous verification timestamp.
        (audit_corpus.ROOT / "cv" / "Resume_Acme.pdf").write_text("new-bytes", encoding="utf-8")
        third = audit_corpus.write_state([result], second and state)
        self.assertEqual(len(third["changed_since_last_run"]), 1)
        self.assertEqual(third["changed_since_last_run"][0]["pdf"], "cv/Resume_Acme.pdf")


if __name__ == "__main__":
    unittest.main()
