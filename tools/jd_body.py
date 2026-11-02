#!/usr/bin/env python3
"""Isolate a posting's job description from the page around it.

Why this exists: `job_eligibility.stack_gate` reads body text, but the fetchers return
the whole page for aggregators. That page carries site navigation, footers and
"similar roles" widgets, so blocked-stack tokens belonging to OTHER jobs get parsed as
requirements. Measured on 2026-10-28: the Diagnostics AI posting (fit 93) was blocked on
"Angular" that appears only in onlyfrontendjobs' own nav ("Handpicked React, Vue, Angular,
and Next.js roles") and a cross-sell widget. The gate was right; the input was polluted.

Extraction is stdlib-only (html.parser) because this repo takes no third-party runtime
deps. Greenhouse, Lever and Ashby return their description as HTML in the API response
and need no carving, but the same extractor is harmless there.

Usage:
  python3 tools/jd_body.py <url> [<url> ...]        # report body size + gate before/after
  python3 tools/jd_body.py --text <url>             # print the extracted body
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}

# A container shorter than this is a teaser or an empty shell, not the posting. Real bodies
# run 1,200 to 12,000 characters; the smallest seen in the tracker was 2,126.
MIN_BODY = 120

# Class predicates per source. A container matches if every fragment in `need` is
# present in its class attribute, and no fragment in `avoid` is.
CONTAINERS = {
    "linkedin": [{"need": ("description__text",), "avoid": ()}],
    "onlyfrontendjobs": [{"need": ("prose", "min-w-0"), "avoid": ("prose-sm",)}],
    "greenhouse": [{"need": ("job__description",), "avoid": ()},
                   {"need": ("job-post",), "avoid": ()}],
    "lever": [{"need": ("posting",), "avoid": ("posting-header",)}],
    "ashby": [{"need": ("job-description",), "avoid": ()}],
    "_generic": [{"need": ("job-description",), "avoid": ()},
                 {"need": ("jobdescription",), "avoid": ()},
                 {"need": ("description__text",), "avoid": ()},
                 {"need": ("posting",), "avoid": ("posting-header",)}],
}


class _Body(HTMLParser):
    """Capture the text of the first element whose class matches a predicate."""

    def __init__(self, rules):
        super().__init__(convert_charrefs=True)
        self.rules = rules
        self.depth = 0
        self.active = False
        self.found = False
        self.skip = 0
        self.parts: list[str] = []

    def _matches(self, cls: str) -> bool:
        low = cls.lower()
        for r in self.rules:
            if all(n in low for n in r["need"]) and not any(a in low for a in r["avoid"]):
                return True
        return False

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            if self.active and tag in ("br", "hr"):
                self.parts.append("\n")
            return
        if not self.active:
            cls = dict(attrs).get("class") or ""
            if cls and self._matches(cls):
                self.active = True
                self.found = True
                self.depth = 1
            return
        self.depth += 1
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "ul", "ol"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in VOID or not self.active:
            return
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        self.depth -= 1
        if self.depth <= 0:
            self.active = False

    def handle_data(self, data):
        if self.active and not self.skip:
            self.parts.append(data)


def tidy(text: str) -> str:
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract(html: str, provider: str = "") -> str | None:
    """Return the posting body, or None when no known container is present."""
    for key in (provider, "_generic"):
        rules = CONTAINERS.get(key)
        if not rules:
            continue
        p = _Body(rules)
        try:
            p.feed(html)
            p.close()
        except Exception:
            continue
        body = tidy("".join(p.parts))
        if p.found and len(body) > MIN_BODY:
            return body
    return None


def body_for(url: str) -> tuple[str | None, str]:
    """Fetch a posting and isolate its body. Returns (body, provider)."""
    sys.path.insert(0, "/home/ubuntu/.hermes/scripts")
    import job_eligibility as je  # noqa: E402  (shared fetchers)

    provider = ("linkedin" if "linkedin.com" in url
                else "onlyfrontendjobs" if "onlyfrontendjobs.com" in url
                else "greenhouse" if "greenhouse.io" in url
                else "lever" if "jobs.lever.co" in url
                else "ashby" if "ashbyhq" in url
                else "")
    if provider in ("greenhouse", "lever", "ashby"):
        r = je.fetch_posting(url)
        if isinstance(r, dict):
            return r.get("text") or None, provider
    status, html = je.get(url)
    if status != 200:
        return None, provider
    return extract(html, provider), provider


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    show = "--text" in argv
    urls = [a for a in argv if a.startswith("http")]
    sys.path.insert(0, "/home/ubuntu/.hermes/scripts")
    import job_eligibility as je

    for u in urls:
        body, provider = body_for(u)
        if show:
            print(f"### {provider} :: {u}\n{body or '(no container)'}\n")
            continue
        raw = je.fetch_posting(u)
        raw_text = (raw.get("text") or "") if isinstance(raw, dict) else (raw or "")
        before = je.stack_gate(raw_text)
        after = je.stack_gate(body or "")
        name = (raw.get("title") if isinstance(raw, dict) else "") or u
        print(f"{name[:70]}")
        print(f"  provider {provider or '?'} | raw {len(raw_text)}c -> body {len(body or '')}c")
        print(f"  gate BEFORE extraction: {before or 'none'}")
        print(f"  gate AFTER  extraction: {after or 'none'}")
        if before != after:
            print(f"  DELTA: {sorted(set(before) - set(after))} removed, "
                  f"{sorted(set(after) - set(before))} added")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
