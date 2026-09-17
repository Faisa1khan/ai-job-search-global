#!/usr/bin/env python3
"""Shared document text extraction utilities for verification gates.

Provides a unified extraction interface for HTML, PDF, Markdown, and plain text
files. Used by verify_sot.py, verify_humanizer.py, and verify_all.py.
"""

from __future__ import annotations

import html as html_mod
import re
import subprocess
import sys
from pathlib import Path


class ExtractionError(Exception):
    """Raised when text cannot be extracted from a document."""


# Canonical Master design separators. The em dash in these positions is a
# design token from the locked Master markup, not a sentence dash: stripping it
# before the prose rules run keeps Gate 4 (verify_humanizer) honest without
# forcing a redesign of the frozen templates.
#   <div class="entry-title">Acme Corp <span class="role">— Senior Engineer</span></div>
#   <div class="edu-name">State University <span>— B.Tech in Computer Science</span></div>
#   <li><strong>Award</strong> — Issuer, year</li>
_DESIGN_DASH_PATTERNS = [
    (re.compile(r'(<span class="role">)\s*—\s*'), r"\1"),
    (re.compile(r'(<div class="edu-name">[^<]*<span>)\s*—\s*'), r"\1"),
    (re.compile(r"(<li>.*?</strong>)\s*—\s*"), r"\1 "),
]


def neutralize_design_dashes(html_text: str) -> str:
    """Remove em dashes that are Master design separator tokens, not prose.

    Line structure is preserved so reported line numbers still match the source.
    """
    out = html_text
    for pattern, repl in _DESIGN_DASH_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def _blank_preserving_newlines(match: "re.Match[str]") -> str:
    """Replace a match with the same number of newlines so line numbers hold."""
    return "\n" * match.group(0).count("\n")


def extract_prose_from_html(html_text: str) -> list[tuple[int, str]]:
    """Extract human-facing text lines from HTML, skipping script/style/comments."""
    # Remove script and style blocks
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
    # Remove comments
    cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)

    lines_out = []
    for line_num, line in enumerate(cleaned.splitlines(), start=1):
        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", line)
        # Unescape HTML entities
        text = html_mod.unescape(text).strip()
        if text:
            lines_out.append((line_num, text))
    return lines_out


def extract_prose_for_humanizer(file_path: Path) -> list[tuple[int, str]]:
    """Extract prose for the humanizer gate.

    Two HTML-specific refinements over extract_prose():
      1. <head> metadata (<title>, <meta description>) is not page prose, so it
         is blanked out; a role title there is metadata, not a sentence.
      2. Canonical Master design separators are neutralized before tag
         stripping, so the frozen design's own dashes are not reported as
         prose violations.
    Line numbers are preserved in both cases.
    """
    file_path = Path(file_path).resolve()
    if file_path.suffix.lower() != ".html":
        return extract_prose(file_path)

    content = file_path.read_text(encoding="utf-8")
    content = re.sub(r"<head\b.*?</head>", _blank_preserving_newlines, content, flags=re.DOTALL | re.IGNORECASE)
    content = neutralize_design_dashes(content)
    return extract_prose_from_html(content)


def extract_prose_from_pdf(pdf_path: Path) -> list[tuple[int, str]]:
    """Extract text from PDF using pdftotext or pypdf."""
    text = ""
    try:
        res = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        text = res.stdout
    except Exception:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ExtractionError(f"Could not extract text from PDF {pdf_path}: {exc}") from exc

    return [(i, line.strip()) for i, line in enumerate(text.splitlines(), start=1) if line.strip()]


def extract_prose_from_text(text: str) -> list[tuple[int, str]]:
    """Extract lines from markdown or plain text, skipping code blocks."""
    lines_out = []
    in_code_block = False
    for line_num, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        # Skip markdown link URLs, inline code tokens
        clean_line = re.sub(r"`[^`]+`", " ", line)
        clean_line = re.sub(r"https?://\S+", " ", clean_line)
        if clean_line.strip():
            lines_out.append((line_num, clean_line.strip()))
    return lines_out


def extract_prose(file_path: Path) -> list[tuple[int, str]]:
    """Auto-dispatch text extraction based on file extension."""
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        raise ExtractionError(f"File {file_path} does not exist")

    suffix = file_path.suffix.lower()
    if suffix == ".html":
        content = file_path.read_text(encoding="utf-8")
        return extract_prose_from_html(content)
    elif suffix == ".pdf":
        return extract_prose_from_pdf(file_path)
    else:
        content = file_path.read_text(encoding="utf-8")
        return extract_prose_from_text(content)
