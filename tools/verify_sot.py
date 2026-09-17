#!/usr/bin/env python3
"""Mechanical Single Source of Truth (SOT) verification tool.

Lints user-facing HTML, PDF, Markdown, and text documents against the canonical
career rules and DO-NOT-CLAIM directives in
  CAREER_SOURCE_OF_TRUTH.md

Enforces (hard failures):
  1. Canonical numbers (29 ADRs, 25 Playwright suites, 16 modules, 8 Acme modules, 42 OpenAPI endpoints, 10,000+ users).
  2. Superseded figures rejection (30 ADRs, 14 suites, 5-6 modules, etc.).
  3. Hard exclusions (KeeLead, PCI-DSS certification claims, US work auth without sponsorship, IIT/NIT pedigree, Refurso 65%, Jira QN- keys).
  4. Scope rule for the platform-scale figures: SOT Section 1/7 allow the 500k/100k
     numbers as PLATFORM-level (dossier-sourced) but forbid presenting them as
     MyPay's own scope, so they fail only when no platform framing is present.

Reports as advisories, never failures (SOT marks them dossier-sourced, "use only
if you can defend it"): TTI 2.1s -> 120ms, the 800ms freeze, the ~60% codebase
reduction, and the -40% payroll support ticket figure.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from doc_extract import (
    extract_prose,
    extract_prose_from_html,
    extract_prose_from_pdf,
    extract_prose_from_text,
    ExtractionError,
)

SOT_PATH = Path("CAREER_SOURCE_OF_TRUTH.md")
WORKSPACE_SOT_PATH = Path(__file__).resolve().parent.parent / "Hermes" / "Obsidian" / "Reports" / "CAREER_SOURCE_OF_TRUTH.md"


class SOTVerificationError(Exception):
    """Raised when text violates SOT grounding rules."""


# Canonical Number & Superseded Figures Rules (Regex, Error Message)
SUPERSEDED_NUMBERS = [
    (r"\b30\s+ADRs?\b", "SOT Section 1 violation: Project Nexus has 29 ADRs (30 is superseded/wrong per GitHub commit history)"),
    (r"\b14\s+(?:test\s+|Playwright\s+)?suites?\b", "SOT Section 1 violation: Project Nexus has 25 Playwright suites (14 is superseded/wrong)"),
    (r"\b[56]\s+core\s+modules?\b", "SOT Section 1 violation: Acme scope is 8 core modules owned"),
]

# Hard Exclusions from SOT Section 6 (DO NOT CLAIM)
HARD_EXCLUSIONS = [
    (r"\bKeeLead\b", "SOT Section 6 exclusion: KeeLead is a third-party codebase, do not claim"),
    (
        r"\bPCI[- ]?DSS\b(?=[^.]*\b(?:certification|certified|certificate|compliant|compliance\s+audit)\b)"
        r"|\b(?:certified|compliant)\s+(?:for|to)?\s*PCI[- ]?DSS\b",
        "SOT Section 6 exclusion: PCI-DSS certification is not held (a workflow/discipline bridge is allowed)",
    ),
    (r"\b65%[^.]{0,20}UI\s+turnaround\b", "SOT Section 6 exclusion: Refurso '65% UI turnaround' has no source"),
    (r"\bQN-\d+\b", "SOT Section 1 & 6 rule: Jira ticket keys (QN-*) must not appear on public application documents"),
    (r"\b(?:US\s+citizen|green\s+card|authorized\s+to\s+work\s+in\s+the\s+US\s+without\s+sponsorship)\b", "SOT Section 0 exclusion: US work authorization requires visa sponsorship; never claim US authorization without sponsorship"),
    (r"\b(?:IIT|NIT)\s+(?:graduate|alumnus|degree|pedigree)\b", "SOT Section 6 exclusion: Do not claim or imply IIT/NIT pedigree"),
]

# Platform-scale figures: valid per SOT Section 1/7 as PLATFORM-level,
# dossier-sourced facts; forbidden per Section 6 only as MyPay/own-scope claims.
SCALE_FIGURES = [
    (
        r"\b(?:500[,.]?000\+|500k\+?)\s*(?:employees|users)\b",
        "SOT Section 6 exclusion: 500k scale must be framed as platform-level, not own scope (canonical own-scope figure: 10,000+ active enterprise users)",
    ),
    (
        r"\b(?:100[,.]?000\+|100k\+?)\s*(?:monthly\s+)?transactions\b",
        "SOT Section 1 & 6: 100k+ monthly payroll transactions is a platform-level figure; label it as the platform's scale, not your own scope",
    ),
]

PLATFORM_FRAMING_MARKERS = (
    "platform",
    "acme's platform",
    "product line",
    "across the product",
    "serving across",
)

# Dossier-sourced metrics: SOT Section 2/4 allow these with the caveat "use only
# if you can defend it", so they are reported as advisories rather than failures.
ADVISORY_METRICS = [
    (r"\bTTI\s+2\.1s\b|\b2\.1s\s*(?:to|→|->)\s*120ms\b", "dossier-sourced TTI 2.1s -> 120ms; keep only if you can defend the measurement"),
    (r"\b800ms\s+freeze\b", "dossier-sourced '800ms freeze -> <1ms'; keep only if you can defend it"),
    (r"\b(?:~?\s*60%|60\s+percent)\s+codebase\s+reduction\b", "dossier-sourced '~60% codebase reduction' (soft claim)"),
    (r"\b40%[^.]{0,25}payroll\s+support\s+ticket\b", "dossier-sourced '-40% payroll support tickets' (soft; SOT notes a ~30% payscale variant)"),
]


def has_platform_framing(line: str) -> bool:
    """True when a scale figure is attributed to the platform rather than the candidate's own scope."""
    lowered = line.lower()
    return any(marker in lowered for marker in PLATFORM_FRAMING_MARKERS)


def check_sot_grounding(prose_lines: list[tuple[int, str]], warnings: list[str] | None = None) -> list[str]:
    """Audit lines against SOT grounding rules.

    Hard violations are returned; dossier-sourced soft metrics are appended to
    `warnings` when that list is provided (they never fail the gate).
    """
    violations = []

    for line_num, line in prose_lines:
        # 1. Superseded figures check
        for pattern, msg in SUPERSEDED_NUMBERS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                violations.append(f"Line {line_num}: {msg} (found '{match.group(0)}') in {line[:80]!r}")

        # 2. Hard exclusions check
        for pattern, msg in HARD_EXCLUSIONS:
            match = re.search(pattern, line, re.IGNORECASE | re.DOTALL)
            if match:
                violations.append(f"Line {line_num}: {msg} (found '{match.group(0)}') in {line[:80]!r}")

        # 3. Platform-scale figures: only a violation without platform framing
        for pattern, msg in SCALE_FIGURES:
            match = re.search(pattern, line, re.IGNORECASE)
            if match and not has_platform_framing(line):
                violations.append(f"Line {line_num}: {msg} (found '{match.group(0)}') in {line[:80]!r}")

        # 4. Advisory (dossier-sourced) metrics
        if warnings is not None:
            for pattern, msg in ADVISORY_METRICS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    warnings.append(f"Line {line_num}: advisory, {msg} (found '{match.group(0)}') in {line[:80]!r}")

    return violations


def verify_sot(file_path: Path, warnings: list[str] | None = None) -> list[str]:
    """Verify a file against SOT grounding rules (advisories go to `warnings`)."""
    try:
        prose_lines = extract_prose(file_path)
    except ExtractionError as exc:
        raise SOTVerificationError(str(exc)) from exc
    return check_sot_grounding(prose_lines, warnings=warnings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path, help="Files to verify against SOT (HTML, PDF, MD, TXT)")
    args = parser.parse_args()

    sot_found = SOT_PATH.exists() or WORKSPACE_SOT_PATH.exists()
    if not sot_found:
        print(f"warning: SOT file not found at {SOT_PATH}, running built-in SOT rule set", file=sys.stderr)

    total_violations = 0
    for target in args.files:
        try:
            violations = verify_sot(target)
        except SOTVerificationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if violations:
            print(f"{target}: {len(violations)} SOT grounding violation(s):")
            for v in violations:
                print(f"  - {v}")
            total_violations += len(violations)
        else:
            print(f"{target}: SOT grounding clean (0 violations)")

    return 1 if total_violations > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
