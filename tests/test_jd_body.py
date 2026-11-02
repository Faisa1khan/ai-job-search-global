"""Tests for tools/jd_body.py - the extraction step that keeps page chrome out of the stack gate.

Measured failure this guards against: on 2026-10-28 the Diagnostics AI posting (fit 93) was
blocked by `job_eligibility.stack_gate` on "Angular". The job description never mentions
Angular; it appears only in onlyfrontendjobs' own navigation ("Handpicked React, Vue, Angular,
and Next.js roles") and a "similar handpicked roles" cross-sell widget. The gate was correct
and the input was polluted. So both directions are tested: the body must survive, the chrome
must not.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.jd_body import extract  # noqa: E402

# Shape of a real onlyfrontendjobs listing: nav and cross-sell carry other jobs' framework
# names, the JD sits in div.prose.
OFJ_PAGE = """
<html><body>
<header><nav>Handpicked React, Vue, Angular, and Next.js roles
  <a href="/angular-jobs">Angular Jobs</a></nav></header>
<main>
  <div class="prose prose-slate min-w-0 max-w-none">
    <h2>The Role</h2>
    <p>You will build and scale the digital health platform end to end, bridging interactive
    React client applications, Supabase Edge Functions, PostgreSQL data architectures and
    AI orchestration pipelines.</p>
    <p>Frontend: React, TypeScript, responsive web interfaces.</p>
    <ul><li>PostgreSQL data architectures and migrations</li>
    <li>RAG architectures and prompt chains</li>
    <li>Accessible, high performance web interfaces</li></ul>
  </div>
  <aside><h3>Similar handpicked roles</h3>
    <p>UI Architect, SymphonyAI. React Angular TypeScript.</p></aside>
</main>
<footer>Terms. Angular Jobs. Vue Jobs. Svelte Jobs.</footer>
</body></html>
"""

# Shape of a real LinkedIn guest posting: the description lives in div.description__text,
# with a nested div and a criteria list beside it.
LINKEDIN_PAGE = """
<html><body><section class="top-card">Full Stack Developer</section>
<div class="description__text description__text--rich">
  <section class="show-more-less-html">
    <div><p>You will join a small engineering team building internal tools for finance and
    logistics customers, with ownership from database schema through to the browser.</p>
    <p>You will work with Git, Docker, and basic CI/CD across a Node and React codebase.</p>
    <p>Hands-on experience with the OpenAI API and building RAG pipelines over internal
    documents is expected, along with a critical eye for AI generated code.</p></div>
  </section>
</div>
<ul class="description__job-criteria-list"><li>Mid-Senior level</li></ul>
</body></html>
"""


class TestAggregatorChrome(unittest.TestCase):
    def test_nav_and_cross_sell_are_excluded(self):
        body = extract(OFJ_PAGE, "onlyfrontendjobs")
        self.assertIsNotNone(body)
        self.assertNotIn("Angular", body)
        self.assertNotIn("Vue", body)
        self.assertNotIn("Svelte", body)

    def test_description_body_survives(self):
        body = extract(OFJ_PAGE, "onlyfrontendjobs")
        for token in ("React", "TypeScript", "Supabase Edge Functions", "PostgreSQL", "RAG"):
            self.assertIn(token, body)


class TestLinkedIn(unittest.TestCase):
    def test_description_text_is_captured(self):
        body = extract(LINKEDIN_PAGE, "linkedin")
        self.assertIsNotNone(body)
        self.assertIn("Docker", body)
        self.assertIn("OpenAI API", body)

    def test_criteria_list_is_excluded(self):
        body = extract(LINKEDIN_PAGE, "linkedin")
        self.assertNotIn("Mid-Senior level", body)

    def test_nested_elements_are_not_truncated(self):
        body = extract(LINKEDIN_PAGE, "linkedin")
        # the second paragraph sits two divs inside the container; a depth bug drops it
        self.assertIn("RAG pipelines", body)


class TestFallbacks(unittest.TestCase):
    def test_unknown_page_returns_none(self):
        self.assertIsNone(extract("<html><body><p>hello</p></body></html>", ""))

    def test_empty_container_is_not_returned(self):
        page = '<div class="prose min-w-0">short</div>'
        self.assertIsNone(extract(page, "onlyfrontendjobs"))

    def test_generic_container_still_works(self):
        page = ('<div class="job-description"><p>' + "React and TypeScript. " * 20 +
                "</p></div>")
        self.assertIsNotNone(extract(page, ""))


if __name__ == "__main__":
    unittest.main()
