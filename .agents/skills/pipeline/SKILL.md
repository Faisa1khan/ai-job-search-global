---
name: pipeline
description: "Autonomous end-to-end job application pipeline: triage backlog, select top unapplied match, research company, generate tailored 1-page HTML CV & Cover Letter on Master templates, enforce SOT grounding and humanizer rules, compile PDF via headless Chromium, verify 1 page, and update tracker."
---

# /pipeline - Autonomous End-to-End Application Pipeline

> Antigravity note: this skill is invoked as `/pipeline`. Any text, URL, or argument passed after the command is referred to below as `$ARGUMENTS`.

This skill runs the complete job application workflow autonomously in a single execution turn: candidate selection, company research, Master HTML CV/Cover Letter tailoring, strict Single Source of Truth (SOT) audit, humanizer prose polishing, headless Chromium 1-page compilation, and tracker recording.

---

## Execution Steps

### Step 0: Candidate Selection

1. **If `$ARGUMENTS` contains a specific URL or job description:**
   - Use that posting directly as the target application.
2. **If `$ARGUMENTS` is empty (default mode):**
   - Run the candidate selector helper:
     ```bash
     python3 tools/pipeline.py next
     ```
   - If a candidate is returned, select it as the target.
   - If no candidate is returned, inform the user to run `/scrape` or `/rank` first to populate the backlog.

---

### Step 1: Ingestion & Company Research

1. Fetch the complete job details:
   - For LinkedIn URLs:
     ```bash
     bun run .agents/skills/linkedin-search/cli/src/cli.ts detail "<url>" --format json
     ```
   - For other URLs: use `read_url_content`.
2. Check `company_research/<normalized_company>.json`. If missing or stale, research company mission, engineering focus, and recent initiatives via `search_web` and write findings to the cache.

---

### Step 2: Master Document Tailoring

Target output filenames:
- Resume HTML: `cv/Resume_<Company>.html`
- Resume PDF: `cv/Resume_<Company>.pdf`
- Cover Letter HTML: `cover_letters/Cover_Letter_<Company>.html`
- Cover Letter PDF: `cover_letters/Cover_Letter_<Company>.pdf`
*(Where `<Company>` is filesystem-safe: spaces to underscores, punctuation removed).*

#### Canonical Rules (STRICT):
1. **Design System:** Use canonical templates `cv/Resume_Master.html` and `cover_letters/Cover_Letter_Master.html`. Never switch fonts, margins, or CSS structure.
2. **Strict Factual Grounding (`CAREER_SOURCE_OF_TRUTH.md`):**
   - Project Nexus: **29 ADRs**, **25 Playwright test suites**, **16 feature modules** (never 30 or 14).
   - Acme: **8 core HRMS modules** owned.
   - MyPay: **4 modules / 42 OpenAPI endpoints**, **10,000+ active enterprise users** (QN-4633).
   - **DO NOT CLAIM 500k/100k:** 500,000+ employees or 100k+ transactions are strictly forbidden (unauthenticated).
   - **DO NOT PRINT Jira counts:** Zero Jira ticket counts or QN keys printed on documents.
   - Notice period: **45 days**.
   - AI Tooling: Reference **Claude Code** by name.
   - Work Authorization: Never claim US work authorization.

---

### Step 3: Mandatory Final Humanizer Gate (for EVERYTHING)

Every piece of output text—Resume bullets, Cover Letter prose, summary blurbs, screening questions, and outreach messages—MUST pass the humanizer audit against `.agents/skills/humanizer/SKILL.md` before compilation:
1. **No em dashes (—) or en dashes (–) in prose:** Only standard punctuation (commas, periods, semicolons, colons). The en-dash `–` is permitted exclusively as the visual bullet prefix in HTML lists. **Design-token exception:** the canonical Master separator dashes inside `<span class="role">` entry titles, `<div class="edu-name">…<span>` education lines, and award `<li><strong>…</strong>` lead-ins belong to the frozen design, not to prose; Gate 4 normalizes them before checking. Do not remove them from the templates.
2. **Strip AI vocabulary:** Eliminate "align with", "leverage", "delve", "testament", "pivotal", "spearheaded", "intricate", "tapestry", "seamless", "cutting-edge", "game-changer", and "robust" (when figurative).
3. **No staged transitions or candor:** Eliminate "Here is how my background...", "Let's dive in", "Real talk", or rhetorical openers.
4. **Active voice & grounded facts only:** Keep every claim strictly tied to `CAREER_SOURCE_OF_TRUTH.md`. No exaggerated impacts or vague corporate fillers.
5. **Location calibration:** Note San Francisco base, Local / Remote commute, or remote availability accurately.

---

### Step 4: Headless Chromium PDF Compilation & Layout Fill Verification

Compile and verify that both documents fit strictly onto **exactly 1 page each** and are **well-filled** with balanced margins:

```bash
python3 tools/pipeline.py compile --html cv/Resume_<Company>.html --pdf cv/Resume_<Company>.pdf
python3 tools/pipeline.py compile --html cover_letters/Cover_Letter_<Company>.html --pdf cover_letters/Cover_Letter_<Company>.pdf
```

`tools/pipeline.py compile` automatically validates all 5 quality gates:
1. **Gate 1 (`verify_pdf.py`):** Page count strictly 1 page without overflow, ATS-extractable text layer.
2. **Gate 2 (`verify_layout.py`):** Layout fill & balanced margins (max bottom whitespace ≤ 75pt / ~9.5%).
3. **Gate 3 (`verify_template.py`):** 100% exact Master markup, DOM class hierarchy, CSS styling, and print margins.
4. **Gate 4 (`verify_humanizer.py`):** Zero prose dashes (—), zero banned AI vocabulary, active voice.
5. **Gate 5 (`verify_sot.py`):** 100% factual grounding against `CAREER_SOURCE_OF_TRUTH.md`.

- If either document overflows 1 page, adjust content conciseness (trim bullet length or whitespace) and re-compile.
- If underfilled (excessive bottom whitespace), restore relevant evidence/bullets from Master.
- If template/humanizer/SOT violations occur, fix the source HTML and re-compile until all 5 gates pass cleanly.

---

### Step 5: Archive Job Posting, Tracker Update & Git Commit

1. **Archive the job details & posting description:**
   Save the full job posting and role metadata to `documents/applications/<company>_<role>/job_posting.md` for historical reference, interview prep (`/interview`), and outcome tracking (`/outcome`):
   ```bash
   python3 tools/pipeline.py archive \
     --company "<Company>" \
     --role "<Role>" \
     --source "<URL>" \
     --location "<Location>" \
     --fit-rating "<Score>" \
     --cv-file "cv/Resume_<Company>.pdf" \
     --cover-letter-file "cover_letters/Cover_Letter_<Company>.pdf" \
     --description "<Full Job Description Text>"
   ```
   *(Alternatively, pass `--archive --location "..." --description "..."` directly to `tools/pipeline.py record`).*

2. **Record the application in `job_search_tracker.csv`:**
   ```bash
   python3 tools/pipeline.py record \
     --company "<Company>" \
     --role "<Role>" \
     --fit-rating "<Score>" \
     --cv-file "cv/Resume_<Company>.pdf" \
     --cover-letter-file "cover_letters/Cover_Letter_<Company>.pdf" \
     --source "<URL>" \
     --sector "<Sector>" \
     --notes "<Grounded summary bullets>" \
     --status "drafted"
   ```

3. **Commit the generated package to git:**
   ```bash
   git add cv/Resume_<Company>.html cv/Resume_<Company>.pdf cover_letters/Cover_Letter_<Company>.html cover_letters/Cover_Letter_<Company>.pdf job_search_tracker.csv
   git commit -m "feat(apply): add <Company> application package (<Role>)"
   git push origin master
   ```
   *(Note: Tailored PDFs are whitelisted in `.gitignore` so they sync to GitHub and can be pulled or downloaded on your laptop immediately).*

---

### Step 6: Present Final Summary (Humanized)

Present the user with:
- Target company, role, location, and fit score.
- Direct clickable links to the compiled PDFs, source HTML files, and archived `job_posting.md`.
- Grounded highlights tailored for the role (strictly humanized, free of em dashes and AI fluff).
- Tailored application screening question answers and compensation/notice period details (45 days, ₹25–32 LPA target ₹28 LPA).
