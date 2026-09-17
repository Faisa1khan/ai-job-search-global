---
framework_version: 1.0.0
---

# Agent Guidelines: AI Job Search

This workspace is structured to manage job search activities, scraper tools, CVs, cover letters, and interview preparation.

## Thin-Pointer Design (Single Source of Truth)

All agent runtimes should load the canonical specifications and candidate profiles:
1. **Master Resume Template:** `cv/Resume_Master.html`
2. **Master Cover Letter Template:** `cover_letters/Cover_Letter_Master.html`
3. **Mandatory 5-Gate Verification:**
   - Gate 1: Exactly 1 page with ATS text layer (`verify_pdf.py`).
   - Gate 2: Canvas fill and balanced margins (`verify_layout.py`).
   - Gate 3: Master markup structure & CSS fidelity (`verify_template.py`).
   - Gate 4: Zero prose dashes, zero banned AI words (`verify_humanizer.py`).
   - Gate 5: Factual grounding (`verify_sot.py`).
