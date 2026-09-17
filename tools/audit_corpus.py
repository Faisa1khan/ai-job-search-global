#!/usr/bin/env python3
"""Audit every CV / cover-letter pair in the workspace against the 5 gates.

`tools/pipeline.py compile` verifies one document at a time, when it is
generated. Nothing re-checks documents that were shipped before a gate was
tightened, so "verified" drifts away from reality. This tool sweeps the whole
corpus in one pass and, with --write-state, records the verification state of
every pair (content hashes + gate results + timestamp) so a later claim about a
document can be checked instead of believed.

Usage:
    python3 tools/audit_corpus.py                     # matrix + summary
    python3 tools/audit_corpus.py --only-failing      # just the failures
    python3 tools/audit_corpus.py --json              # machine-readable
    python3 tools/audit_corpus.py --write-state       # persist state, flag drift
    python3 tools/audit_corpus.py --company Weave     # one company
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

STATE_FILE = ROOT / "documents" / "verification_state.json"

GATES = (
    ("pdf", "pdf_clean"),
    ("layout", "layout_clean"),
    ("template", "template_clean"),
    ("humanizer", "humanizer_clean"),
    ("sot", "sot_clean"),
)

PAIR_GLOBS = (
    ("cv", "Resume_*.html"),
    ("cover_letters", "Cover_Letter_*.html"),
)


def sha256(path: Path) -> str:
    """Content hash of a file, hex-encoded."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_pairs(root: Path, company: str | None = None) -> list[tuple[Path, Path]]:
    """Return (html, pdf) pairs that exist on disk, sorted by file name."""
    pairs: list[tuple[Path, Path]] = []
    for subdir, pattern in PAIR_GLOBS:
        for html in sorted((root / subdir).glob(pattern)):
            pdf = html.with_suffix(".pdf")
            if not pdf.exists():
                continue
            if company and company.lower() not in html.stem.lower():
                continue
            pairs.append((html, pdf))
    return pairs


def summarize(results: list[dict]) -> dict:
    """Aggregate per-gate pass counts and failing gate names."""
    summary = {
        "pairs": len(results),
        "passing": sum(1 for r in results if not r["failed_gates"]),
        "failing": sum(1 for r in results if r["failed_gates"]),
        "per_gate_failures": {gate: 0 for gate, _ in GATES},
    }
    for result in results:
        for gate in result["failed_gates"]:
            summary["per_gate_failures"][gate] += 1
    return summary


def audit_pair(html: Path, pdf: Path) -> dict:
    """Run all 5 gates on one pair and normalise the outcome.

    verify_package() prints progress lines; they are forwarded to stderr so
    --json output stays machine-readable.
    """
    from verify_all import verify_package

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        res = verify_package(html, pdf, expected_pages=1)
    detail = buffer.getvalue().strip()
    if detail:
        print(detail, file=sys.stderr)

    failed = [gate for gate, key in GATES if not res.get(key)]
    return {
        "html": str(html.relative_to(ROOT)) if html.is_relative_to(ROOT) else str(html),
        "pdf": str(pdf.relative_to(ROOT)) if pdf.is_relative_to(ROOT) else str(pdf),
        "success": bool(res.get("success")),
        "pages": res.get("pages"),
        "failed_gates": failed,
        "errors": res.get("errors", []),
    }


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def write_state(results: list[dict], previous: dict) -> dict:
    """Persist per-document verification state; report drift since last run."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state = {}
    drift = []
    for result in results:
        html = ROOT / result["html"]
        pdf = ROOT / result["pdf"]
        html_hash = sha256(html)
        pdf_hash = sha256(pdf)
        old = previous.get(result["pdf"])
        if old and (old.get("pdf_sha256") != pdf_hash or old.get("html_sha256") != html_hash):
            drift.append(
                {
                    "pdf": result["pdf"],
                    "was_verified": old.get("verified_at"),
                    "was_clean": old.get("success"),
                }
            )
        state[result["pdf"]] = {
            "html_sha256": html_hash,
            "pdf_sha256": pdf_hash,
            "verified_at": now,
            "success": result["success"],
            "failed_gates": result["failed_gates"],
        }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"written": str(STATE_FILE), "documents": len(state), "changed_since_last_run": drift}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    parser.add_argument("--only-failing", action="store_true", help="Hide passing pairs")
    parser.add_argument("--write-state", action="store_true", help=f"Update {STATE_FILE.name} and report drift")
    parser.add_argument("--company", help="Only pairs whose file name contains this string")
    args = parser.parse_args()

    pairs = collect_pairs(ROOT, args.company)
    if not pairs:
        print("No CV/cover-letter pairs found.", file=sys.stderr)
        return 1

    results = [audit_pair(html, pdf) for html, pdf in pairs]
    summary = summarize(results)

    if args.json:
        payload = {"summary": summary, "results": results}
        if args.write_state:
            payload["state"] = write_state(results, load_state())
        print(json.dumps(payload, indent=2))
        return 0 if summary["failing"] == 0 else 1

    print("=" * 92)
    print(f"  CORPUS AUDIT: {summary['pairs']} pairs | {summary['passing']} pass | {summary['failing']} fail")
    print("=" * 92)
    for result in results:
        if args.only_failing and not result["failed_gates"]:
            continue
        status = "PASS" if not result["failed_gates"] else "FAIL:" + ",".join(result["failed_gates"])
        print(f"  {status:28} {result['pdf']}")
        for error in result["errors"][:2]:
            print(f"        {error.replace(chr(10), ' | ')[:150]}")
    print("-" * 92)
    for gate, count in summary["per_gate_failures"].items():
        print(f"  gate {gate:10} failures: {count}")

    if args.write_state:
        info = write_state(results, load_state())
        print(f"\n  state written: {info['written']} ({info['documents']} documents)")
        if info["changed_since_last_run"]:
            print(f"  changed since last run: {len(info['changed_since_last_run'])}")
            for item in info["changed_since_last_run"]:
                print(f"    - {item['pdf']} (was verified {item['was_verified']}, clean={item['was_clean']})")

    return 0 if summary["failing"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
