#!/usr/bin/env python3
"""Is this posting still open? Read the page, decide expired or uncertain. Never "live".

Ported from career-ops-hq/career-ops `liveness-core.mjs` (MIT, upstream 3d30cf14). The
pattern set is machine-extracted into `tools/vendor/liveness_patterns.py` rather than
retyped, so the 61 rules are upstream's own regex sources.

The design rule that matters: **this tool can only prove a posting is CLOSED.** Without a
rendered DOM there is no Apply control to see, so "live" is never asserted; a page that
fails to show closure evidence comes back `uncertain`, which is a result, not a pass.

That asymmetry is deliberate and upstream argues it at length: a false `expired` writes a
real job out of every future scan, while a false `uncertain` costs one more look.

Why this exists: our closed-posting check was a plain substring test, and it missed
United's posting which read "no longer accepting new applications" while still carrying the
title and location. Upstream's pattern set covers that phrasing, normalises typographic
quotes and accents first, and refuses to read a closure banner as a banner when its own
clause opens with "if" or "until".

Usage:
  python3 tools/liveness_check.py --file page.txt
  python3 tools/liveness_check.py --url https://...        (fetches, no JS: body text only)
  python3 tools/liveness_check.py --file page.txt --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from vendor.liveness_patterns import (  # noqa: E402
    APPLY_PATTERNS, BOT_CHALLENGE_PATTERNS, EXPIRED_URL_PATTERNS, HARD_EXPIRED_PATTERNS,
    LISTING_PAGE_PATTERNS, SOFT_EXPIRED_PATTERNS,
)

MIN_CONTENT_CHARS = 300
JOB_ID_TOKEN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\d{5,}", re.I)

# Extensions on top of upstream's set, each carrying the posting that motivated it. Keep
# this list short and evidenced: the whole point of vendoring is that their rules are
# somebody else's to maintain.
EXTRA_HARD_EXPIRED_PATTERNS = [
    # United Airlines reads "no longer accepting new applications for this position" and
    # upstream's /no longer accepting applications/ misses the "new". Verified 2026-10-30
    # against the live careers page, which still showed the title and location.
    re.compile(r"no longer accepting\s+(?:new\s+)?applications", re.I),
]

# A closure banner can be preceded by its own condition ("until the position has been
# filled", "once applications have closed"). An occurrence only counts when no time or
# condition word opens its clause.
TIME_OR_CONDITION_CLAUSE = re.compile(
    r"\b(?:until|till|once|when|whenever|after|before|unless|if|whether|as soon as) "
    r"(?:[^\s.,;:!?…|•·]+ ){0,9}[^\s.,;:!?…|•·]+$", re.I)


def normalize_for_match(text: str, keep_line_breaks: bool = False) -> str:
    """Fold typographic punctuation and accents, collapse whitespace.

    Upstream's lesson: a pattern spelled with an ASCII apostrophe silently never matches
    a board that renders U+2019, so a clearly expired posting reads as uncertain forever.
    """
    if not isinstance(text, str):
        return ""
    s = text
    s = re.sub(r"[‘’ʼ′´`]", "'", s)
    s = re.sub(r"[“”″]", '"', s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    if keep_line_breaks:
        return re.sub(r"\s+", lambda m: "\n" if "\n" in m.group(0) else " ", s)
    return re.sub(r"\s+", " ", s)


def job_id_token(url: str) -> str | None:
    matches = JOB_ID_TOKEN.findall(url or "")
    return matches[-1].lower() if matches else None


def first_match(patterns, text: str):
    for pattern in patterns:
        if pattern.search(text):
            return pattern
    return None


def first_stated_match(patterns, lines: str):
    """A hard pattern only counts when its own clause is not time- or condition-opened."""
    text = lines.replace("\n", " ")
    for pattern in patterns:
        for m in pattern.finditer(text):
            if not TIME_OR_CONDITION_CLAUSE.search(lines[: m.end()]):
                return pattern
    return None


def has_apply_control(controls) -> bool:
    return any(p.search(c) for c in controls for p in APPLY_PATTERNS)


def classify_liveness(status: int = 200, requested_url: str = "", final_url: str = "",
                      body_text: str = "", apply_controls=None) -> dict:
    apply_controls = [normalize_for_match(c) for c in (apply_controls or [])]
    body_lines = normalize_for_match(body_text, keep_line_breaks=True)
    body = body_lines.replace("\n", " ")

    if status in (404, 410):
        return {"result": "expired", "code": "http_gone", "reason": f"HTTP {status}"}

    # Anti-bot walls are checked before the content-length heuristic: a short challenge
    # body would otherwise read as a dead posting.
    challenge = first_match(BOT_CHALLENGE_PATTERNS, body)
    if challenge:
        return {"result": "uncertain", "code": "bot_challenge",
                "reason": f"anti-bot challenge: {challenge.pattern}"}
    if status in (403, 429, 503):
        return {"result": "uncertain", "code": "access_blocked",
                "reason": f"HTTP {status} (access blocked, likely anti-bot)"}
    if status in (401, 451):
        why = "sign-in required" if status == 401 else "unavailable for legal reasons, usually by region"
        return {"result": "uncertain", "code": "access_blocked", "reason": f"HTTP {status} ({why})"}
    if status >= 500:
        return {"result": "uncertain", "code": "server_error",
                "reason": f"HTTP {status} (transient server error)"}

    expired_url = first_match(EXPIRED_URL_PATTERNS, final_url or "")
    if expired_url:
        return {"result": "expired", "code": "expired_url", "reason": f"redirect to {final_url}"}

    expired_body = first_stated_match(HARD_EXPIRED_PATTERNS + EXTRA_HARD_EXPIRED_PATTERNS, body_lines)
    if expired_body:
        return {"result": "expired", "code": "expired_body",
                "reason": f"pattern matched: {expired_body.pattern}"}

    job_id = job_id_token(requested_url or "")
    if job_id and final_url and job_id not in final_url.lower():
        return {"result": "uncertain", "code": "redirected_off_posting",
                "reason": f'redirected to {final_url}, job id "{job_id}" missing from final URL'}

    if has_apply_control(apply_controls):
        return {"result": "active", "code": "apply_control_visible",
                "reason": "visible apply control detected"}

    soft = first_match(SOFT_EXPIRED_PATTERNS, body)
    if soft:
        return {"result": "expired", "code": "expired_body_soft",
                "reason": f"pattern matched: {soft.pattern}"}

    listing = first_match(LISTING_PAGE_PATTERNS, body)
    if listing:
        return {"result": "expired", "code": "listing_page",
                "reason": f"pattern matched: {listing.pattern}"}

    if len(body.strip()) < MIN_CONTENT_CHARS:
        return {"result": "uncertain", "code": "insufficient_content",
                "reason": "insufficient content, likely nav/footer only or not rendered yet"}
    return {"result": "uncertain", "code": "no_apply_control",
            "reason": "content present but no visible apply control found"}


def check_url(url: str) -> dict:
    """Fetch the page and classify it. No JS: a client-rendered page reads as uncertain."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            final = resp.geturl()
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return classify_liveness(status=exc.code, requested_url=url, final_url=url)
    except Exception as exc:  # noqa: BLE001 - advisory tool
        return {"result": "uncertain", "code": "fetch_failed",
                "reason": f"{type(exc).__name__}: {exc}"}

    # Text only: strip scripts/styles/tags so the patterns see prose, not markup.
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return classify_liveness(status=status, requested_url=url, final_url=final, body_text=text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Is this posting still open? Advisory.")
    ap.add_argument("--file")
    ap.add_argument("--url")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.url:
        res = check_url(a.url)
        res["url"] = a.url
    elif a.file:
        res = classify_liveness(body_text=Path(a.file).read_text(errors="replace"))
    else:
        print("usage: liveness_check.py --file <path> | --url <url> [--json]")
        return 2

    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f'{res["result"].upper():9} {res["code"]:22} {res["reason"][:90]}')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
