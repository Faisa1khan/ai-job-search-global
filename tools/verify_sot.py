#!/usr/bin/env python3
"""Mechanical Single Source of Truth (SOT) verification tool.

Lints user-facing HTML, PDF, Markdown and text documents against the claims a
candidate's own ledger allows. This is gate 5 of `tools/verify_all.py`.

The rules are data, not code: a fork supplies its own rule file so the gate can
check its own ledger instead of somebody else's. That is deliberate. A claim rule
hardcoded in a shared template is either wrong for everyone or a description of
one person's CV.

Rule file (JSON), any class may be omitted:

  {
    "platform_framing_markers": ["platform", "product line"],
    "superseded_figures": [{"pattern": "...", "message": "..."}],
    "hard_exclusions":    [{"pattern": "...", "message": "..."}],
    "scale_figures":      [{"pattern": "...", "message": "..."}],
    "advisory_metrics":   [{"pattern": "...", "message": "..."}]
  }

Four rule classes, in increasing leniency:

  1. `superseded_figures` fail the document. For a count the ledger has replaced:
     the older figure keeps resurfacing out of stale drafts.
  2. `hard_exclusions` fail the document. For anything never claimable: a
     certification not held, work authorization not held, an internal ticket key,
     a figure with no source.
  3. `scale_figures` fail only when the line does not attribute the number to the
     platform. The same six-figure user count is a true platform figure and a false
     own-scope claim, and the difference lives in the sentence.
  4. `advisory_metrics` never fail. They print beside the result, because keeping
     a soft number is a judgement the author makes, not the gate.

Built in, needs no rule entry: internal work-item keys. Set
JOBSEARCH_INTERNAL_KEY_PREFIXES (default `PROJ,TICKET,JIRA`).

Rule file resolution order: `--rules PATH`, then `$JOBSEARCH_SOT_RULES`, then
`./sot_rules.json`, then `tools/sot_rules.example.json`. With none of them the
gate still catches work-item keys, passes everything else, and says so.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from doc_extract import extract_prose, ExtractionError  # noqa: E402  (after the path insert)

SOT_PATH = Path("CAREER_SOURCE_OF_TRUTH.md")
RULES_ENV = "JOBSEARCH_SOT_RULES"
LOCAL_RULES_PATH = Path("sot_rules.json")
EXAMPLE_RULES_PATH = Path(__file__).resolve().parent / "sot_rules.example.json"

RULE_CLASSES = ("superseded_figures", "hard_exclusions", "scale_figures", "advisory_metrics")
DEFAULT_FRAMING_MARKERS = ("platform", "product line", "across the product", "serving across")


class SOTVerificationError(Exception):
    """Raised when a document cannot be read, or a rule file is malformed."""


def _key_exclusion() -> tuple[re.Pattern[str], str]:
    """Internal work-item keys, prefix set by environment. Always enforced."""
    prefixes = tuple(
        p.strip().upper()
        for p in os.environ.get("JOBSEARCH_INTERNAL_KEY_PREFIXES", "PROJ,TICKET,JIRA").split(",")
        if p.strip()
    )
    pattern = r"\b(?:" + "|".join(re.escape(p) for p in prefixes) + r")-\d+\b"
    return (
        re.compile(pattern, re.IGNORECASE),
        "internal work-item keys must not appear on a document that goes to an employer",
    )


def _compile_entries(entries: object, where: str) -> list[tuple[re.Pattern[str], str]]:
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise SOTVerificationError(f"{where}: expected a list of {{pattern, message}} objects")
    compiled = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or "pattern" not in entry:
            raise SOTVerificationError(f"{where}[{i}]: expected an object with 'pattern' and 'message'")
        message = str(entry.get("message", "rule violated"))
        try:
            compiled.append((re.compile(str(entry["pattern"]), re.IGNORECASE | re.DOTALL), message))
        except re.error as exc:
            raise SOTVerificationError(f"{where}[{i}]: invalid regex {entry['pattern']!r}: {exc}") from exc
    return compiled


def load_rules(path: Path | None = None) -> dict[str, object]:
    """Resolve and compile the rule set. Never raises for a missing file."""
    resolved: Path | None = path
    if resolved is None and os.environ.get(RULES_ENV):
        resolved = Path(os.environ[RULES_ENV]).expanduser()
    if resolved is None and LOCAL_RULES_PATH.exists():
        resolved = LOCAL_RULES_PATH
    if resolved is None and EXAMPLE_RULES_PATH.exists():
        resolved = EXAMPLE_RULES_PATH

    rules: dict[str, object] = {name: [] for name in RULE_CLASSES}
    rules["platform_framing_markers"] = list(DEFAULT_FRAMING_MARKERS)
    rules["source"] = None

    if resolved is not None:
        try:
            raw = json.loads(Path(resolved).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SOTVerificationError(f"rule file not found: {resolved}") from exc
        except json.JSONDecodeError as exc:
            raise SOTVerificationError(f"rule file is not valid JSON ({resolved}): {exc}") from exc
        if not isinstance(raw, dict):
            raise SOTVerificationError(f"rule file must be a JSON object: {resolved}")
        for name in RULE_CLASSES:
            rules[name] = _compile_entries(raw.get(name), f"{resolved}:{name}")
        markers = raw.get("platform_framing_markers")
        if isinstance(markers, list) and markers:
            rules["platform_framing_markers"] = [str(m).lower() for m in markers]
        rules["source"] = str(resolved)

    hard = list(rules["hard_exclusions"])  # type: ignore[arg-type]
    hard.append(_key_exclusion())
    rules["hard_exclusions"] = hard
    return rules


def has_platform_framing(line: str, rules: dict[str, object]) -> bool:
    """True when a scale figure is attributed to the platform, not the candidate."""
    lowered = line.lower()
    return any(marker in lowered for marker in rules["platform_framing_markers"])  # type: ignore[union-attr]


def check_sot_grounding(
    prose_lines: list[tuple[int, str]],
    warnings: list[str] | None = None,
    rules: dict[str, object] | None = None,
) -> list[str]:
    """Audit lines against the rule set.

    Hard violations are returned; advisory metrics are appended to `warnings`
    when that list is provided, and never appear in the return value.
    """
    if rules is None:
        rules = load_rules()

    violations: list[str] = []
    for line_num, line in prose_lines:
        for pattern, msg in rules["superseded_figures"] + rules["hard_exclusions"]:  # type: ignore[operator]
            match = pattern.search(line)
            if match:
                violations.append(f"Line {line_num}: {msg} (found {match.group(0)!r}) in {line[:80]!r}")

        for pattern, msg in rules["scale_figures"]:  # type: ignore[union-attr]
            match = pattern.search(line)
            if match and not has_platform_framing(line, rules):
                violations.append(f"Line {line_num}: {msg} (found {match.group(0)!r}) in {line[:80]!r}")

        if warnings is not None:
            for pattern, msg in rules["advisory_metrics"]:  # type: ignore[union-attr]
                match = pattern.search(line)
                if match:
                    warnings.append(f"Line {line_num}: advisory, {msg} (found {match.group(0)!r}) in {line[:80]!r}")

    return violations


def verify_sot(
    file_path: Path,
    warnings: list[str] | None = None,
    rules: dict[str, object] | None = None,
) -> list[str]:
    """Verify one file against the rule set (advisories go to `warnings`)."""
    try:
        prose_lines = extract_prose(file_path)
    except ExtractionError as exc:
        raise SOTVerificationError(str(exc)) from exc
    return check_sot_grounding(prose_lines, warnings=warnings, rules=rules)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("files", nargs="+", type=Path, help="Files to verify (HTML, PDF, MD, TXT)")
    parser.add_argument(
        "--rules",
        type=Path,
        default=None,
        help=f"Rule file to use instead of ${RULES_ENV}, {LOCAL_RULES_PATH} or the example",
    )
    args = parser.parse_args()

    try:
        rules = load_rules(args.rules)
    except SOTVerificationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not SOT_PATH.exists():
        print(
            f"note: no {SOT_PATH} here, checking against "
            f"{rules['source'] or 'the built-in work-item key rule only'}",
            file=sys.stderr,
        )

    total_violations = 0
    for target in args.files:
        warnings: list[str] = []
        try:
            violations = verify_sot(target, warnings=warnings, rules=rules)
        except SOTVerificationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if violations:
            print(f"{target}: {len(violations)} SOT grounding violation(s):")
            for violation in violations:
                print(f"  - {violation}")
            total_violations += len(violations)
        else:
            print(f"{target}: SOT grounding clean (0 violations)")

        for warning in warnings:
            print(f"  ! {warning}")

    return 1 if total_violations > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
