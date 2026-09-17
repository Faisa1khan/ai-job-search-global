#!/usr/bin/env python3
"""Autonomous Direct ATS Form Submitter Python Wrapper.

Dispatches to tools/ats_submitter.ts via Bun with full environment configuration,
supporting:
  - Dry run mode (form filling, resume upload, validation, preview screenshot).
  - Live submission mode (submits form, captures confirmation screenshot, updates tracker).
  - Automatic integration with job_search_tracker.csv and documents/applications/.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMITTER_TS = ROOT / "tools" / "ats_submitter.ts"

ENV = dict(os.environ)
LOCAL_BIN = str(Path.home() / ".local" / "bin")
BUN_BIN = str(Path.home() / ".bun" / "bin")
ENV["PATH"] = f"{LOCAL_BIN}:{BUN_BIN}:{ENV.get('PATH', '')}"


def run_submitter(
    company: str | None = None,
    role: str | None = None,
    url: str | None = None,
    cv: str | None = None,
    submit: bool = False,
    output_json: bool = False,
) -> int:
    cmd = ["bun", "run", str(SUBMITTER_TS)]
    if company:
        cmd.extend(["--company", company])
    if role:
        cmd.extend(["--role", role])
    if url:
        cmd.extend(["--url", url])
    if cv:
        cmd.extend(["--cv", cv])
    if submit:
        cmd.append("--submit")
    else:
        cmd.append("--dry-run")
    if output_json:
        cmd.append("--json")

    res = subprocess.run(cmd, env=ENV, cwd=str(ROOT))
    return res.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", help="Company name (looks up tracker & tailored CV)")
    parser.add_argument("--role", help="Role title")
    parser.add_argument("--url", help="Direct ATS apply URL (Ashby, Lever, Greenhouse, etc.)")
    parser.add_argument("--cv", help="Custom path to tailored Resume PDF")
    parser.add_argument("--submit", action="store_true", help="Submit live application (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Fill form & capture screenshot without submitting")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args()
    return run_submitter(
        company=args.company,
        role=args.role,
        url=args.url,
        cv=args.cv,
        submit=args.submit,
        output_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
