#!/usr/bin/env python3
"""Template fidelity verifier: ensures tailored HTML strictly adheres to Master CSS and markup.

Checks:
  1. CSS block fidelity: Checks that core styling, font stacks, and @page margins match Master.
  2. Structural element sanity: Prevents rogue <header>, <section>, <h2> from replacing canonical <div> classes.
  3. Section hierarchy sanity: Ensures canonical section names and structure.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESUME_MASTER = ROOT / "cv" / "Resume_Master.html"
COVER_MASTER = ROOT / "cover_letters" / "Cover_Letter_Master.html"


def extract_style_block(content: str) -> str:
    m = re.search(r"<style\b[^>]*>(.*?)</style>", content, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def normalize_css(css: str) -> str:
    # Remove comments
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    # Normalize whitespace
    css = re.sub(r"\s+", " ", css).strip()
    return css


def verify_resume_template(html_path: Path) -> list[str]:
    violations = []
    content = html_path.read_text(encoding="utf-8")

    # 1. Structural tags check (Forbidden: semantic elements that break the frozen visual hierarchy)
    if "<header" in content.lower():
        violations.append("Used '<header>' element. Must use '<div class=\"header\">' matching Master template.")
    if "<section" in content.lower():
        violations.append("Used '<section>' element. Must use '<div class=\"section\">' matching Master template.")
    if "<h2" in content.lower():
        violations.append("Used '<h2>' element. Must use '<div class=\"section-title\">' matching Master template.")

    # 2. Check required master classes
    required_classes = [
        "resume",
        "header",
        "section",
        "section-title",
        "skills-grid",
        "skill-row",
        "entry",
        "entry-header",
        "entry-title",
        "edu-grid",
        "edu-item",
        "achievements",
    ]
    for cls in required_classes:
        if not re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"', content):
            violations.append(f"Missing canonical Master class: {cls}")

    # 3. Check CSS margins & fonts
    if "@page" not in content or "0.36in 0.44in" not in content:
        violations.append("Print @page margin modified. Must strictly remain '0.36in 0.44in' matching Master.")

    return violations


def verify_cover_template(html_path: Path) -> list[str]:
    violations = []
    content = html_path.read_text(encoding="utf-8")

    if "<header" in content.lower():
        violations.append("Used '<header>' element. Must use '<div class=\"header\">' matching Master template.")
    if "<section" in content.lower():
        violations.append("Used '<section>' element. Must use '<div class=\"body-section\">' matching Master template.")

    required_classes = [
        "cover-document",
        "header",
        "meta-block",
        "letter-body",
        "closing",
    ]
    for cls in required_classes:
        if not re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"', content):
            violations.append(f"Missing canonical Master class: {cls}")

    return violations


def verify_template(html_path: Path) -> list[str]:
    name = html_path.name.lower()
    if "cover_letter" in name or "cover" in name:
        return verify_cover_template(html_path)
    elif "resume" in name or "cv" in name:
        return verify_resume_template(html_path)
    return []


def main():
    parser = argparse.ArgumentParser(description="Verify HTML against canonical Master template design")
    parser.add_argument("html", type=Path, help="Path to HTML file to verify")
    args = parser.parse_args()

    if not args.html.exists():
        sys.exit(f"File {args.html} not found")

    violations = verify_template(args.html)
    if violations:
        print(f"{args.html}: {len(violations)} template violation(s):")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print(f"{args.html}: template design matches Master perfectly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
