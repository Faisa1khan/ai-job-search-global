#!/usr/bin/env python3
"""Shared tracker and state utilities for the job search pipeline.

Consolidates duplicated norm(), get_tracked_keys(), and slug utilities
used across pipeline.py, autonomous_job_pipeline.py, rank_state.py,
and generate_outreach.py.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKER_FILE = ROOT / "job_search_tracker.csv"
STATE_FILE = ROOT / "job_scraper" / "seen_jobs.json"


def norm(s: str | None) -> str:
    """Normalize a string for dedup comparison: lowercase, strip non-alphanumeric."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def get_tracked_keys(tracker_path: Path | None = None) -> set[tuple[str, str]]:
    """Return set of (company, role) normalized pairs from the tracker CSV."""
    tracker_path = tracker_path or TRACKER_FILE
    tracked: set[tuple[str, str]] = set()
    if not tracker_path.exists():
        return tracked
    with tracker_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            c, r = norm(row.get("company")), norm(row.get("role"))
            if c:
                tracked.add((c, r))
    return tracked


def clean_slug(s: str) -> str:
    """Filesystem-safe slug from a string."""
    return re.sub(r"[^\w]+", "_", s.lower()).strip("_")
