#!/usr/bin/env python3
"""Tailored Recruiter & Hiring Manager Outreach Generator.

Generates 4 high-converting, humanized outreach messages for any tracked or target role:
  1. LinkedIn Connection Request Note (strictly <= 300 characters).
  2. Technical Recruiter / Talent Acquisition InMail & Cold Email.
  3. Engineering Manager / Tech Lead Technical Outreach.
  4. 7-Day Application Follow-Up Email.

Strictly follows:
  - Career Source of Truth (6.8 YOE, 45d notice, 29 ADRs, 25 Playwright suites, 42 OpenAPI endpoints).
  - Humanizer rules (zero em dashes, zero AI filler words).
  - Saves to documents/applications/<slug>/outreach_notes.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
TRACKER_FILE = ROOT / "job_search_tracker.csv"
COMPANY_RESEARCH_DIR = ROOT / "company_research"
DOCUMENTS_APP_DIR = ROOT / "documents" / "applications"

from candidate_profile import CANDIDATE_PROFILE as CANDIDATE
from verify_humanizer import BANNED_AI_WORDS as BANNED_WORDS
from tracker_utils import clean_slug


def load_company_research(company: str) -> Dict[str, Any]:
    slug = clean_slug(company)
    # Direct match or scan directory
    direct_file = COMPANY_RESEARCH_DIR / f"{slug}.json"
    if direct_file.exists():
        try:
            return json.loads(direct_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    for file in COMPANY_RESEARCH_DIR.glob("*.json"):
        if slug in file.stem or file.stem in slug:
            try:
                return json.loads(file.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def load_job_posting_text(company: str, role: str) -> str:
    slug = clean_slug(f"{company}_{role}")
    posting_file = DOCUMENTS_APP_DIR / slug / "job_posting.md"
    if posting_file.exists():
        try:
            return posting_file.read_text(encoding="utf-8")
        except Exception:
            pass

    # Try fuzzy matching folder
    for app_dir in DOCUMENTS_APP_DIR.glob("*"):
        if app_dir.is_dir() and clean_slug(company) in app_dir.name:
            p_file = app_dir / "job_posting.md"
            if p_file.exists():
                try:
                    return p_file.read_text(encoding="utf-8")
                except Exception:
                    pass
    return ""


def extract_first_name(contact: str) -> str:
    if not contact:
        return ""
    # Remove titles / parentheticals like "Nikky Sharma (nikky.sharma@benthonlabs.com)"
    clean = re.sub(r"\(.*?\)", "", contact).strip()
    clean = re.sub(r"^(mr\.|ms\.|dr\.)\s+", "", clean, flags=re.IGNORECASE)
    parts = clean.split()
    return parts[0] if parts else ""


def build_linkedin_connection_note(
    company: str,
    role: str,
    contact_name: str = "",
    research: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a high-signal LinkedIn connection invite strictly <= 300 characters."""
    first_name = extract_first_name(contact_name)
    greeting = f"Hi {first_name}," if first_name else f"Hi {company} team,"

    # Find relevant tech focus
    tech_stack = []
    if research:
        tech_stack = research.get("tech_stack", [])
    
    focus_tech = "React 19 & Next.js"
    if any("Next" in t for t in tech_stack):
        focus_tech = "Next.js App Router & React 19"
    elif any("State" in t or "Redux" in t for t in tech_stack):
        focus_tech = "React, TypeScript & state architecture"

    # Candidate variation A: direct applicant hook
    note_a = (
        f"{greeting} I applied for the {role} role. I bring 6.8y building high-performance "
        f"frontend systems ({focus_tech}, 29 ADRs, 25 Playwright suites). Would love to connect "
        f"and share my work at example.com."
    )
    if len(note_a) <= 300:
        return note_a

    # Candidate variation B: tighter conciseness
    note_b = (
        f"{greeting} Applied for {role} at {company}. I bring 6.8y in {focus_tech}, "
        f"42 OpenAPI endpoints, and 25 Playwright suites. Would love to connect. "
        f"Details at example.com."
    )
    if len(note_b) <= 300:
        return note_b

    # Candidate variation C: ultra concise fallback
    note_c = (
        f"{greeting} Applied for {role}. 6.8y frontend experience (React 19, Next.js, TS, "
        f"29 ADRs, 45d notice). Would love to connect: example.com"
    )
    return note_c[:300]


def build_recruiter_email(
    company: str,
    role: str,
    contact_name: str = "",
    research: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Generate recruiter/TA focused cold outreach email & InMail."""
    first_name = extract_first_name(contact_name)
    salutation = f"Hi {first_name}," if first_name else f"Hi {company} Recruiting Team,"

    subject = f"Application: {role} - Alex Doe (6.8 YOE | React/Next.js | 45d Notice)"

    tech_overlap = "React 19, Next.js (App Router), TypeScript, and automated testing"
    if research and research.get("tech_stack"):
        stack_items = [s for s in research["tech_stack"][:4] if isinstance(s, str)]
        if stack_items:
            tech_overlap = ", ".join(stack_items)

    body = f"""{salutation}

I recently submitted my application for the {role} position at {company} and wanted to reach out directly to share context on my background.

Key qualifications from my 6.8 years in frontend engineering:
- Architecture & Scale: Shipped 8 core HRMS modules and 42 OpenAPI endpoints serving 10,000+ active enterprise users at Acme. Engineered virtualized interfaces rendering 50,000+ data cells with sub-150ms response times.
- Modern Web Stack: Built Project Nexus (example.com), a multi-tenant SaaS with Next.js 16, React 19, TypeScript, and Tailwind CSS, backed by 29 Architecture Decision Records (ADRs) and 25 Playwright test suites.
- Tech Overlap: Hands-on depth across {tech_overlap}.
- Logistics: Based in San Francisco (open to Remote / Hybrid), notice period is 45 days.

I have attached my tailored resume for your review. If my profile aligns with what the team is looking for, I would welcome the chance for a brief screening conversation.

Portfolio: {CANDIDATE['portfolio']}
GitHub: {CANDIDATE['github']}
LinkedIn: {CANDIDATE['linkedin']}

Best regards,
{CANDIDATE['name']}
{CANDIDATE['phone']} | {CANDIDATE['email']}"""

    return subject, body


def build_eng_manager_email(
    company: str,
    role: str,
    contact_name: str = "",
    research: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Generate peer-level Engineering Manager / Tech Lead technical outreach."""
    first_name = extract_first_name(contact_name)
    salutation = f"Hi {first_name}," if first_name else f"Hi {company} Engineering Team,"

    subject = f"Frontend Architecture & Scale - Alex Doe (re: {role})"

    domain_pain = "frontend performance, modular state architectures, and robust test coverage"
    if research and research.get("key_pain_points"):
        points = research["key_pain_points"]
        if points:
            domain_pain = points[0].lower()

    body = f"""{salutation}

I saw that {company} is looking for a {role} to work on {domain_pain}.

Over the past 6.8 years, my focus has been on frontend architecture, state machine predictability, and client-side performance. Most recently:
1. Project Nexus (example.com): Built a multi-tenant SaaS on Next.js 16 and React 19 from ground up. Documented 29 Architecture Decision Records (ADRs) and authored 25 Playwright end-to-end test suites covering all critical state workflows.
2. Enterprise Scale: Integrated 42 OpenAPI endpoints across cross-service boundaries and optimized complex data grids to virtualize 50,000+ cells with zero UI freezing.
3. Quality & Reliability: Enforce strict TypeScript generics, deterministic state transitions, and automated regression testing.

I would love to learn more about the technical challenges your engineering team is solving at {company} and see if my background can help accelerate your roadmap.

Live Work & ADRs: {CANDIDATE['portfolio']}
Codebase / GitHub: {CANDIDATE['github']}

Best regards,
{CANDIDATE['name']}
{CANDIDATE['email']}"""

    return subject, body


def build_followup_email(
    company: str,
    role: str,
    contact_name: str = "",
) -> Tuple[str, str]:
    """Generate polite 7-day follow-up message."""
    first_name = extract_first_name(contact_name)
    salutation = f"Hi {first_name}," if first_name else f"Hi {company} Team,"

    subject = f"Following up: {role} Application - Alex Doe"

    body = f"""{salutation}

I am following up on my application for the {role} role at {company} from last week.

I remain very interested in the work your team is doing. If you would like to inspect my engineering standards or system design artifacts, you can review my live platform at {CANDIDATE['portfolio']} (featuring 29 documented ADRs and 25 Playwright suites) or my GitHub at {CANDIDATE['github']}.

Please let me know if there are any additional details or work samples I can provide.

Best regards,
{CANDIDATE['name']}
{CANDIDATE['email']} | {CANDIDATE['phone']}"""

    return subject, body


def verify_text(text: str) -> List[str]:
    """Ensure generated outreach passes humanizer and anti-AI rules."""
    violations = []
    if "\u2014" in text:  # em dash
        violations.append("Contains em dash ('\u2014')")
    for pat, msg in BANNED_WORDS:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            violations.append(f"Contains AI stock word: {match.group(0)}")
    return violations


def generate_outreach_package(
    company: str,
    role: str,
    contact_person: str = "",
    save: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    """Generate all 4 outreach message formats for a company and role."""
    research = load_company_research(company)
    posting_text = load_job_posting_text(company, role)

    # 1. LinkedIn connection note
    li_note = build_linkedin_connection_note(company, role, contact_person, research)
    # 2. Recruiter email
    rec_subj, rec_body = build_recruiter_email(company, role, contact_person, research)
    # 3. Engineering manager email
    eng_subj, eng_body = build_eng_manager_email(company, role, contact_person, research)
    # 4. Follow-up email
    fol_subj, fol_body = build_followup_email(company, role, contact_person)

    # Format Markdown document
    slug = clean_slug(f"{company}_{role}")
    doc_dir = DOCUMENTS_APP_DIR / slug
    outreach_file = doc_dir / "outreach_notes.md"

    md_content = f"""# Recruiter & Hiring Manager Outreach Notes: {company}

- **Company:** {company}
- **Role:** {role}
- **Contact Person:** {contact_person or "Hiring Team / Engineering Leadership"}
- **Candidate:** Alex Doe (6.8 YOE | San Francisco / Remote | 45d Notice)

---

## 1. LinkedIn Connection Request Note (<= 300 Characters)

> **Character Count:** {len(li_note)} / 300 characters (Strict limit verified)

```text
{li_note}
```

---

## 2. Technical Recruiter / Talent Acquisition InMail & Cold Email

**Subject:** `{rec_subj}`

```text
{rec_body}
```

---

## 3. Engineering Manager / Tech Lead Outreach

**Subject:** `{eng_subj}`

```text
{eng_body}
```

---

## 4. 7-Day Application Follow-Up

**Subject:** `{fol_subj}`

```text
{fol_body}
```
"""

    all_warnings = (
        verify_text(li_note)
        + verify_text(rec_body)
        + verify_text(eng_body)
        + verify_text(fol_body)
    )

    if save:
        doc_dir.mkdir(parents=True, exist_ok=True)
        if not outreach_file.exists() or force:
            outreach_file.write_text(md_content, encoding="utf-8")

    return {
        "company": company,
        "role": role,
        "slug": slug,
        "file": str(outreach_file) if save else None,
        "linkedin_note": li_note,
        "linkedin_char_count": len(li_note),
        "recruiter_email": {"subject": rec_subj, "body": rec_body},
        "eng_manager_email": {"subject": eng_subj, "body": eng_body},
        "followup_email": {"subject": fol_subj, "body": fol_body},
        "warnings": all_warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", type=str, help="Company name")
    parser.add_argument("--role", type=str, default="Senior Frontend Engineer", help="Role title")
    parser.add_argument("--contact", type=str, default="", help="Contact person name/email")
    parser.add_argument("--latest", type=int, default=0, help="Generate for latest N applications in tracker")
    parser.add_argument("--all-applied", action="store_true", help="Generate for all applied/drafted jobs in tracker")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outreach_notes.md files")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    results = []

    if args.latest > 0 or args.all_applied:
        if not TRACKER_FILE.exists():
            sys.exit(f"Tracker file {TRACKER_FILE} not found")
        with TRACKER_FILE.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        target_rows = []
        for r in rows:
            status = (r.get("status") or "").lower()
            if args.all_applied or status in ("applied", "drafted", "tailored"):
                target_rows.append(r)

        if args.latest > 0:
            target_rows = target_rows[-args.latest:]

        for r in target_rows:
            comp = r.get("company", "").strip()
            role = r.get("role", "").strip()
            contact = r.get("contact_person", "").strip()
            if comp and role:
                res = generate_outreach_package(comp, role, contact, save=True, force=args.force)
                results.append(res)
    elif args.company:
        res = generate_outreach_package(args.company, args.role, args.contact, save=True, force=args.force)
        results.append(res)
    else:
        parser.print_help()
        return 1

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*70}")
        print(f"Generated Outreach Packages ({len(results)} companies)")
        print(f"{'='*70}\n")
        for pkg in results:
            print(f"🏢 Company: {pkg['company']} | Role: {pkg['role']}")
            print(f"📁 Saved to: {pkg['file']}")
            print(f"🔗 LinkedIn Note ({pkg['linkedin_char_count']}/300 chars):")
            print(f"   \"{pkg['linkedin_note']}\"")
            print(f"✉️  Recruiter Subject: {pkg['recruiter_email']['subject']}")
            print(f"⚙️  EM Subject: {pkg['eng_manager_email']['subject']}")
            print(f"{'-'*70}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
