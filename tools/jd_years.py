#!/usr/bin/env python3
"""The years-of-experience bar a job description asks for, and whether it is in reach.

Advisory only. Nothing here can fail a run: a missing node binary, a crash in the
vendored parser or an unreadable posting all return verdict "unknown" with a reason,
because a wrong DROP silently costs a real job while a wrong KEEP costs one glance
at a row. That is the upstream design rule, kept deliberately.

Why this exists: /scrape's screen reads geography, title family, discipline and
language, and nothing else. Three of the five postings reviewed when this landed carried
a stated floor above the candidate's own record (8+, 7-10), and each one was found by
reading the JD by hand.

The parser is vendored from career-ops-hq/career-ops (MIT) at `tools/vendor/jd-years.mjs`,
with its network half removed. JD text is fetched on this side by tools/jd_body.py, so
the posting body is clean of page chrome before it reaches the parser. That matters:
the same UltaHost posting reads "preferred-only 4+" from raw LinkedIn page text and
"stated 4+" from the extracted body.

Usage:
  python3 tools/jd_years.py --url <posting-url>
  python3 tools/jd_years.py --text-file <path>
  python3 tools/jd_years.py --url <url> --json
"""
from __future__ import annotations

import argparse
import os
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VENDORED = REPO / "tools" / "vendor" / "jd-years.mjs"

# The candidate's own record, in years, and the stretch a fork is willing to
# argue (a 1.2-year stretch reaches an "8+ years" bar from a 6.8-year record).
# Neutral by default so a public clone carries nobody's number: set
# JOBSEARCH_CANDIDATE_YEARS / JOBSEARCH_STRETCH_YEARS, or pass --years/--stretch.
CANDIDATE_YEARS = float(os.environ.get("JOBSEARCH_CANDIDATE_YEARS") or 0.0)
STRETCH_YEARS = float(os.environ.get("JOBSEARCH_STRETCH_YEARS") or 0.0)


def _node() -> str | None:
    return shutil.which("node")


def band_for_text(text: str, years: float = CANDIDATE_YEARS,
                  stretch: float = STRETCH_YEARS) -> dict:
    """Parse a JD body. Never raises; returns verdict 'unknown' on any failure."""
    blank = {"verdict": "unknown", "label": "", "status": "unread",
             "min": None, "max": None, "confident": False, "reason": ""}
    if not text or not text.strip():
        return {**blank, "reason": "no JD text"}
    node = _node()
    if not node:
        return {**blank, "reason": "node not on PATH"}
    if not VENDORED.exists():
        return {**blank, "reason": f"vendored parser missing at {VENDORED}"}

    payload = json.dumps({"text": text[:60000], "years": years, "stretchYears": stretch})
    try:
        p = subprocess.run([node, str(VENDORED)], input=payload, capture_output=True,
                           text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return {**blank, "reason": "parser timed out"}
    except OSError as exc:
        return {**blank, "reason": f"parser could not start: {exc}"}
    if p.returncode != 0:
        first = (p.stderr or "").strip().splitlines()
        return {**blank, "reason": f"parser exited {p.returncode}: {first[0][:120] if first else ''}"}

    try:
        d = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {**blank, "reason": "parser returned non-JSON"}

    req = d.get("requirement") or {}
    return {
        "verdict": d.get("verdict") or "unknown",
        "label": d.get("label") or req.get("display") or "",
        "status": req.get("status") or "",
        "min": req.get("min"),
        "max": req.get("max"),
        "confident": bool(req.get("confident")),
        "reason": "",
    }


def band_for_url(url: str, years: float = CANDIDATE_YEARS,
                 stretch: float = STRETCH_YEARS) -> dict:
    """Fetch the posting body on this side, then parse it. Advisory; never raises."""
    try:
        sys.path.insert(0, str(REPO / "tools"))
        import jd_body  # local import: keeps the pure path free of network deps
        body, provider = jd_body.body_for(url)
    except Exception as exc:  # noqa: BLE001 - advisory tool, any failure is "unknown"
        return {"verdict": "unknown", "label": "", "status": "unread", "min": None,
                "max": None, "confident": False, "reason": f"fetch failed: {type(exc).__name__}"}
    if not body:
        return {"verdict": "unknown", "label": "", "status": "unread", "min": None,
                "max": None, "confident": False,
                "reason": f"no JD body extracted ({provider or 'unknown source'})"}
    out = band_for_text(body, years, stretch)
    out["provider"] = provider
    out["chars"] = len(body)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Years-of-experience bar from a JD, advisory only.")
    ap.add_argument("--url")
    ap.add_argument("--text-file")
    ap.add_argument("--years", type=float, default=CANDIDATE_YEARS)
    ap.add_argument("--stretch", type=float, default=STRETCH_YEARS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.url:
        res = band_for_url(a.url, a.years, a.stretch)
    elif a.text_file:
        res = band_for_text(Path(a.text_file).read_text(errors="replace"), a.years, a.stretch)
    else:
        print("usage: jd_years.py --url <posting> | --text-file <path> [--json]")
        return 2

    if a.json:
        print(json.dumps(res, indent=1))
    else:
        verdict = {"in": "IN  ", "out": "OUT ", "unknown": "?   "}.get(res["verdict"], "?   ")
        print(f'{verdict} band={res["label"] or "none"}  status={res["status"]}  '
              f'confident={res["confident"]}')
        if res.get("reason"):
            print(f"      reason: {res['reason']}")
        print(f"      candidate {a.years} yrs, stretch {a.stretch} -> reaches {a.years + a.stretch:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
