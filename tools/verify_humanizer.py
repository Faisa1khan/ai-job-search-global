#!/usr/bin/env python3
"""Mechanical Humanizer and SOT Grounding verification tool.

Lints user-facing HTML, PDF, Markdown, and text files against the humanizer rules
defined in .agents/skills/humanizer/SKILL.md and grounding rules in AGENTS.md:
  1. Em dashes (—) and en dashes (–) in prose sentences (except date ranges, bullet tokens, and the canonical Master design separators normalized by doc_extract.neutralize_design_dashes).
  2. Banned stock AI vocabulary (e.g., 'align with', 'leverage', 'delve', 'testament', 'pivotal', 'spearheaded').
  3. Staged openers and rhetorical transitions ('Let's dive in', 'Real talk', 'Here is how').
  4. Chatbot residue ('I hope this helps', 'Great question!', 'Certainly!').
  5. Not-X-but-Y formulas in prose ('not just X, but Y').
  6. Prohibited or superseded SOT claims (30 ADRs -> 29, 14 suites -> 25, 500k claims, Jira QN keys).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from doc_extract import (
    extract_prose,
    extract_prose_for_humanizer,
    extract_prose_from_html,
    extract_prose_from_pdf,
    extract_prose_from_text,
    ExtractionError,
)
from verify_sot import SCALE_FIGURES, has_platform_framing


class HumanizerError(Exception):
    """Raised when text violates humanizer or grounding rules."""


# Prohibited SOT claims & superseded figures
# (platform-scale figures are handled by SCALE_FIGURES below: SOT Section 1/7
# allow them when framed as platform-level, Section 6 forbids own-scope use.)
SOT_PROHIBITED = [
    (r"\b30\s+ADRs?\b", "Superseded SOT figure: Project Nexus has 29 ADRs (never 30)"),
    (r"\b14\s+(?:test\s+)?suites?\b", "Superseded SOT figure: Project Nexus has 25 Playwright test suites (never 14)"),
    (r"\bQN-\d+\b", "Prohibited internal key: Jira ticket QN- keys must not appear on public documents"),
]


# Prohibited AI stock vocabulary
BANNED_AI_WORDS = [
    (r"\b(leverage|leveraging|leveraged|leverages)\b", "AI stock vocabulary: 'leverage' (use 'use', 'build', 'apply', or direct verb)"),
    (r"\b(align with|aligns with|aligned with|aligning with)\b", "AI stock vocabulary: 'align with' (use 'matches', 'supports', 'fits', or state concrete connection)"),
    (r"\b(delve|delves|delving|delved)\b", "AI stock vocabulary: 'delve' (use 'explore', 'examine', 'investigate', or plain verb)"),
    (r"\b(testament|stands as a testament)\b", "AI stock inflation: 'testament' (state concrete fact directly)"),
    (r"\b(pivotal|pivotal role)\b", "AI stock inflation: 'pivotal' (state specific contribution directly)"),
    (r"\b(spearheaded|spearheading|spearhead)\b", "AI stock vocabulary: 'spearhead' (use 'led', 'built', 'directed', 'engineered')"),
    (r"\b(intricate|intricacies)\b", "AI stock vocabulary: 'intricate' (use 'complex', 'detailed', or name the specific complexity)"),
    (r"\b(tapestry)\b", "AI stock metaphor: 'tapestry' (drop figurative metaphor)"),
    (r"\b(seamless|seamlessly)\b", "AI stock buzzword: 'seamless' (describe concrete integration mechanics)"),
    (r"\b(cutting-edge|cutting edge)\b", "AI stock buzzword: 'cutting-edge' (state modern stack/tools specifically)"),
    (r"\b(game-changer|game changer)\b", "AI stock buzzword: 'game-changer' (state measurable impact)"),
    (r"\b(bolstered|bolstering)\b", "AI stock vocabulary: 'bolster' (use 'strengthened', 'improved', 'increased')"),
    (r"\b(meticulous|meticulously)\b", "AI stock vocabulary: 'meticulous' (describe thoroughness through specific tests/ADRs)"),
    (r"\b(interplay)\b", "AI stock vocabulary: 'interplay' (use 'interaction', 'relationship', or describe connection)"),
    (r"\b(fostering|fosters)\b", "AI stock vocabulary: 'fostering' (use 'encouraging', 'supporting', 'driving')"),
    (r"\b(groundbreaking)\b", "AI stock inflation: 'groundbreaking' (state concrete outcome)"),
]

# Staged openers and conversational cliches
STAGED_OPENERS = [
    (r"\b(let's dive in|let's explore|let's break this down)\b", "Staged opener: announce point directly without warm-up"),
    (r"\b(here's what you need to know|here is what you need to know)\b", "Staged opener: eliminate conversational run-up"),
    (r"\b(without further ado)\b", "Staged opener: remove cliché transition"),
    (r"\b(real talk|honestly\?|let's be honest|here's the thing)\b", "Staged candor: state claim plainly"),
    (r"\b(at its core|what really matters|the deeper issue)\b", "Aphoristic staging: state technical fact directly"),
]

# Chatbot residue
CHATBOT_RESIDUE = [
    (r"\b(i hope this helps|hope this helps)\b", "Chatbot residue: remove assistant sign-off"),
    (r"\b(great question|of course|certainly|you're absolutely right)[!.]?", "Chatbot residue: remove conversational praise"),
    (r"\b(let me know if you(?:'d| would)? like me to)\b", "Chatbot residue: remove interactive prompt"),
    (r"\b(would you like me to|want me to continue)\b", "Chatbot residue: remove interactive prompt"),
]


def check_dashes_in_prose(line: str) -> list[str]:
    """Check for improper em dashes or en dashes in prose sentences.
    
    Allowed:
      - Starting bullet symbol: '–' or '-' at index 0 (e.g. '– Bullet text')
      - Date ranges: '2019 – Present', 'Dec 2019 – Present', '2015 – 2019', '10,000+'
      - Role separator in headers: 'Alex Doe — Frontend SDE-2'
    Forbidden:
      - Em dashes (—) in prose sentences (e.g. 'delivered modules — payroll, attendance')
      - Double hyphens (-- or ' -- ') in prose sentences
    """
    problems = []

    # Em dash (—) inside body sentences
    # Allow if it is a title/header line or role separator (e.g. Acme Corp — Senior Software Engineer)
    is_header_separator = bool(re.search(r"^[A-Z][\w\s.&/]+(\s*[-—–]\s*)[A-Z][\w\s.&/()]+$", line))
    is_title_line = "title" in line.lower() or "resume" in line.lower() or "cover letter" in line.lower()

    if "—" in line and not is_header_separator and not is_title_line:
        # Check if it's inside regular prose
        problems.append(f"Prose contains em dash ('—'). Replace with comma, colon, period, or clean phrasing: {line[:80]!r}")

    if " -- " in line or " --- " in line:
        problems.append(f"Prose contains spaced double hyphen (' -- '). Replace with comma or period: {line[:80]!r}")

    return problems


def check_humanizer(
    source_path: Path,
    prose_lines: list[tuple[int, str]],
    strict_dashes: bool = True,
) -> list[str]:
    """Run all humanizer rule checks on extracted prose lines."""
    violations = []

    for line_num, line in prose_lines:
        # 1. Dashes check
        if strict_dashes:
            for dash_err in check_dashes_in_prose(line):
                violations.append(f"Line {line_num}: {dash_err}")

        # 2. Banned AI words
        for pattern, msg in BANNED_AI_WORDS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                violations.append(f"Line {line_num}: {msg} (found '{match.group(0)}') in {line[:80]!r}")

        # 3. Staged openers
        for pattern, msg in STAGED_OPENERS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                violations.append(f"Line {line_num}: {msg} in {line[:80]!r}")

        # 4. Chatbot residue
        for pattern, msg in CHATBOT_RESIDUE:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                violations.append(f"Line {line_num}: {msg} in {line[:80]!r}")

        # 5. Prohibited SOT claims
        for pattern, msg in SOT_PROHIBITED:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                violations.append(f"Line {line_num}: {msg} in {line[:80]!r}")

        # 5b. Platform-scale figures: only a violation without platform framing
        # (SOT Section 1/7 allow 500k/100k as platform-level figures).
        for pattern, msg in SCALE_FIGURES:
            match = re.search(pattern, line, re.IGNORECASE)
            if match and not has_platform_framing(line):
                violations.append(f"Line {line_num}: {msg} in {line[:80]!r}")

        # 6. Not-X-but-Y formulas in prose
        if re.search(r"\bnot just\b.+?\bbut\b", line, re.IGNORECASE) or re.search(r"\bnot only\b.+?\bbut\b", line, re.IGNORECASE):
            violations.append(f"Line {line_num}: Not-X-but-Y contrast formula in {line[:80]!r}")

    return violations


def verify_humanizer(file_path: Path, strict_dashes: bool = True) -> list[str]:
    """Verify a file (HTML, PDF, MD, TXT) against humanizer rules.

    HTML sources go through extract_prose_for_humanizer(): <head> metadata is
    not prose, and the canonical Master design separators (entry-title role
    spans, education spans, award list lead-ins) are design tokens rather than
    sentence dashes. Everything else stays on the strict prose rule.
    """
    try:
        prose_lines = extract_prose_for_humanizer(file_path)
    except ExtractionError as exc:
        raise HumanizerError(str(exc)) from exc
    return check_humanizer(file_path, prose_lines, strict_dashes=strict_dashes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path, help="Files to verify (HTML, PDF, MD, TXT)")
    parser.add_argument("--no-strict-dashes", action="store_true", help="Allow em dashes in prose")
    args = parser.parse_args()

    total_violations = 0
    for target in args.files:
        try:
            violations = verify_humanizer(target, strict_dashes=not args.no_strict_dashes)
        except HumanizerError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if violations:
            print(f"{target}: {len(violations)} humanizer violation(s):")
            for v in violations:
                print(f"  - {v}")
            total_violations += len(violations)
        else:
            print(f"{target}: humanizer clean (0 violations)")

    return 1 if total_violations > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
