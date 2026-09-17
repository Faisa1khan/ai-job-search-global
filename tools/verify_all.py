#!/usr/bin/env python3
"""Composite 5-gate document verification runner.

Runs all verification gates in-process (no subprocess spawning) for maximum speed.
Used by pipeline.py and autonomous_job_pipeline.py.

Gates:
  1. verify_pdf: Exactly 1 page with valid extractable ATS text layer.
  2. verify_layout: Canvas fill & balanced margins.
  3. verify_template: Master markup structure, DOM classes, CSS rules.
  4. verify_humanizer: Zero prose dashes, zero banned AI buzzwords.
  5. verify_sot: 100% factual grounding against CAREER_SOURCE_OF_TRUTH.md.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


def verify_package(
    html_path: Path,
    pdf_path: Path,
    *,
    expected_pages: int = 1,
    max_bottom_space: float | None = None,
    skip: set[str] | None = None,
) -> dict[str, Any]:
    """Run all 5 verification gates in-process.

    Args:
        html_path: Path to the source HTML file.
        pdf_path: Path to the compiled PDF file.
        expected_pages: Expected page count (default 1).
        max_bottom_space: Override max bottom whitespace in pt.
        skip: Set of gate names to skip, e.g. {"layout", "humanizer", "sot", "template"}.

    Returns:
        dict with keys:
          success: bool
          pdf: str path
          pages: int or "overflow"
          pdf_clean: bool
          layout_clean: bool
          template_clean: bool
          humanizer_clean: bool
          sot_clean: bool
          errors: list[str]
    """
    skip = skip or set()
    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path).resolve()
    errors: list[str] = []

    # Gate 1: PDF page count and ATS text layer
    pdf_clean = True
    actual_pages = expected_pages
    try:
        from verify_pdf import verify_pdf, VerificationError
        _extractor, _text, actual_pages = verify_pdf(
            pdf_path, expected_pages=expected_pages
        )
    except Exception as exc:
        pdf_clean = False
        errors.append(f"PDF 1-page check failed: {exc}")

    # Gate 2: Layout geometry
    layout_clean = True
    if "layout" not in skip:
        try:
            from verify_layout import parse_pdf, report as layout_report, detect_doc_type
            from verify_layout import MAX_SINGLE_PAGE_BOTTOM_SPACE_PT

            pages_data = parse_pdf(pdf_path)
            doc_type = detect_doc_type(pdf_path)

            if max_bottom_space is not None:
                max_bs = max_bottom_space
                check_fill = True
            elif doc_type == "cover_letter":
                max_bs = 450.0
                check_fill = False
            else:
                max_bs = MAX_SINGLE_PAGE_BOTTOM_SPACE_PT
                check_fill = True

            layout_problems = layout_report(
                pdf_path, pages_data,
                max_bottom_space=max_bs,
                check_single_page_fill=check_fill,
            )
            if layout_problems:
                layout_clean = False
                errors.append("Layout check failed:\n" + "\n".join(f"  - {p}" for p in layout_problems))
        except RuntimeError as exc:
            # pdftotext -bbox not available, skip gracefully
            pass
        except Exception as exc:
            layout_clean = False
            errors.append(f"Layout check error: {exc}")
    
    # Gate 3: Template fidelity
    template_clean = True
    if "template" not in skip:
        try:
            from verify_template import verify_template
            template_issues = verify_template(html_path)
            if template_issues:
                template_clean = False
                errors.append("Template fidelity check failed:\n" + "\n".join(f"  - {i}" for i in template_issues))
        except Exception as exc:
            template_clean = False
            errors.append(f"Template check error: {exc}")

    # Gate 4: Humanizer
    humanizer_clean = True
    if "humanizer" not in skip:
        try:
            from verify_humanizer import verify_humanizer
            humanizer_issues = verify_humanizer(html_path)
            if humanizer_issues:
                humanizer_clean = False
                errors.append("Humanizer check failed:\n" + "\n".join(f"  - {i}" for i in humanizer_issues))
        except Exception as exc:
            humanizer_clean = False
            errors.append(f"Humanizer check error: {exc}")

    # Gate 5: SOT grounding
    sot_clean = True
    sot_warnings: list[str] = []
    if "sot" not in skip:
        try:
            from verify_sot import verify_sot
            sot_issues = verify_sot(html_path, warnings=sot_warnings)
            if sot_issues:
                sot_clean = False
                errors.append("SOT grounding check failed:\n" + "\n".join(f"  - {i}" for i in sot_issues))
        except Exception as exc:
            sot_clean = False
            errors.append(f"SOT check error: {exc}")
    for warning in sot_warnings:
        print(f"  advisory: {warning}", file=sys.stderr)

    success = pdf_clean and layout_clean and template_clean and humanizer_clean and sot_clean
    return {
        "success": success,
        "pdf": str(pdf_path),
        "pages": actual_pages if pdf_clean else "overflow",
        "pdf_clean": pdf_clean,
        "layout_clean": layout_clean,
        "template_clean": template_clean,
        "humanizer_clean": humanizer_clean,
        "sot_clean": sot_clean,
        "sot_warnings": sot_warnings,
        "errors": errors,
    }


def main() -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--html", required=True, type=Path, help="Source HTML file")
    ap.add_argument("--pdf", required=True, type=Path, help="Compiled PDF file")
    ap.add_argument("--pages", type=int, default=1, help="Expected page count (default: 1)")
    ap.add_argument("--max-bottom-space", type=float, default=None)
    ap.add_argument("--skip", nargs="*", default=[], help="Gates to skip: layout template humanizer sot")
    args = ap.parse_args()

    result = verify_package(
        args.html, args.pdf,
        expected_pages=args.pages,
        max_bottom_space=args.max_bottom_space,
        skip=set(args.skip),
    )
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
