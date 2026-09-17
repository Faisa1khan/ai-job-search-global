"""Unit tests for tools/verify_humanizer.py."""

import os
import tempfile
import unittest
from pathlib import Path

from tools.verify_humanizer import (
    check_humanizer,
    extract_prose_from_html,
    extract_prose_from_text,
    verify_humanizer,
)


class TestExtractProse(unittest.TestCase):
    def test_extract_from_html_strips_tags_and_scripts(self):
        raw_html = """
        <html>
        <head><style>body { color: red; }</style></head>
        <body>
          <h1>Heading</h1>
          <p>This is a paragraph with <strong>bold</strong> text.</p>
          <script>console.log("ignore");</script>
        </body>
        </html>
        """
        lines = extract_prose_from_html(raw_html)
        texts = [t for _, t in lines]
        self.assertIn("Heading", texts)
        self.assertIn("This is a paragraph with  bold  text.", texts)
        self.assertFalse(any("console.log" in t for t in texts))
        self.assertFalse(any("body {" in t for t in texts))

    def test_extract_from_text_skips_code_blocks(self):
        md = """
        # Title
        Some introduction.
        ```python
        # leverage and align with
        def test(): pass
        ```
        Conclusion sentence.
        """
        lines = extract_prose_from_text(md)
        texts = [t for _, t in lines]
        self.assertIn("# Title", texts)
        self.assertIn("Some introduction.", texts)
        self.assertIn("Conclusion sentence.", texts)
        self.assertFalse(any("def test" in t for t in texts))


class TestHumanizerRules(unittest.TestCase):
    def test_clean_prose_passes(self):
        lines = [
            (1, "Senior Frontend Engineer with 6+ years shipping React and TypeScript applications."),
            (2, "Built a deterministic payroll computation engine handling ESI and PF compliance."),
        ]
        violations = check_humanizer(Path("test.html"), lines)
        self.assertEqual(violations, [])

    def test_banned_words_detected(self):
        lines = [
            (1, "We leverage modern frameworks to deliver solutions."),
            (2, "My background aligns with your engineering mission."),
            (3, "Spearheaded the migration of the core platform."),
            (4, "Stands as a testament to engineering excellence."),
        ]
        violations = check_humanizer(Path("test.html"), lines)
        self.assertEqual(len(violations), 4)
        self.assertTrue(any("leverage" in v for v in violations))
        self.assertTrue(any("align with" in v for v in violations))
        self.assertTrue(any("spearhead" in v for v in violations))
        self.assertTrue(any("testament" in v for v in violations))

    def test_staged_openers_detected(self):
        lines = [
            (1, "Let's dive in and explore the architecture."),
            (2, "Here is what you need to know about the system."),
            (3, "Real talk: the previous implementation was broken."),
        ]
        violations = check_humanizer(Path("test.html"), lines)
        self.assertEqual(len(violations), 3)

    def test_chatbot_residue_detected(self):
        lines = [
            (1, "I hope this helps! Let me know if you need more info."),
            (2, "Great question! The service uses PostgreSQL."),
        ]
        violations = check_humanizer(Path("test.html"), lines)
        self.assertGreaterEqual(len(violations), 2)
        self.assertTrue(any("hope this helps" in v for v in violations))
        self.assertTrue(any("Great question" in v for v in violations))

    def test_prohibited_sot_claims_detected(self):
        lines = [
            (1, "Guided by 30 ADRs and 14 test suites."),
            (2, "Scaled own delivery to 500k employees."),
            (3, "Fixed bug QN-4633 in production."),
        ]
        violations = check_humanizer(Path("test.html"), lines)
        self.assertEqual(len(violations), 4)  # 30 ADRs, 14 test suites, 500k, QN-4633

    def test_platform_framed_scale_is_not_flagged(self):
        lines = [
            (1, "Built recruitment AI on a platform serving 500k+ employees."),
        ]
        self.assertEqual(check_humanizer(Path("test.html"), lines), [])

    def test_em_dashes_in_prose_detected(self):
        lines = [
            (1, "Delivered core modules — payroll, attendance, and leave."),
        ]
        violations = check_humanizer(Path("test.html"), lines, strict_dashes=True)
        self.assertEqual(len(violations), 1)
        self.assertTrue(any("em dash" in v for v in violations))


class TestMasterDesignSeparators(unittest.TestCase):
    """Gate 4 must not flag the locked Master design's own separator dashes.

    Regression guard: verify_humanizer used to report the canonical Master
    resume (entry-title role spans, education spans, award lead-ins) and any
    document faithful to it, which made "all 5 gates pass" unreachable.
    """

    def _doc(self, body: str) -> Path:
        fh = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
        fh.write(
            "<html><head><title>Jane Doe — Senior Engineer</title>"
            '<meta name="description" content="Jane Doe — Senior Engineer"></head>'
            f"<body>{body}</body></html>"
        )
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return Path(fh.name)

    def test_role_span_separator_is_design_not_prose(self):
        path = self._doc(
            '<div class="entry-title">Acme Corp <span class="role">— Senior Software Engineer</span></div>'
        )
        self.assertEqual(verify_humanizer(path), [])

    def test_edu_span_and_award_separators_are_design_not_prose(self):
        path = self._doc(
            '<div class="edu-name">State University, City <span>— B.Tech in Computer Science</span></div>'
            "<li><strong>Mobile Web Challenge Scholar</strong> — Selected among top 150 candidates nationwide; "
            "completed Mobile Web Specialist Nanodegree</li>"
        )
        self.assertEqual(verify_humanizer(path), [])

    def test_head_metadata_dash_is_not_prose(self):
        self.assertEqual(verify_humanizer(self._doc("<p>Plain body copy.</p>")), [])

    def test_prose_em_dash_still_fails(self):
        path = self._doc("<li>Delivered core modules — payroll, attendance, and leave.</li>")
        self.assertTrue(any("em dash" in v for v in verify_humanizer(path)))

    def test_banned_word_inside_a_design_span_still_fails(self):
        path = self._doc(
            '<div class="entry-title">Acme Corp <span class="role">— Leverage Engineer</span></div>'
        )
        self.assertTrue(any("leverage" in v.lower() for v in verify_humanizer(path)))


if __name__ == "__main__":
    unittest.main()
