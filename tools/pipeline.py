#!/usr/bin/env python3
"""Autonomous pipeline helper: select candidates, compile/verify PDFs, and record tracker state.

Used by the /pipeline skill to provide deterministic execution for the end-to-end flow:
  1. select: finds the highest-scoring unapplied candidate
  2. compile: runs headless Chromium and verifies 1-page bounds
  3. record: updates job_search_tracker.csv safely
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
STATE_FILE = ROOT / "job_scraper" / "seen_jobs.json"
TRACKER_FILE = ROOT / "job_search_tracker.csv"

from tracker_utils import norm, get_tracked_keys


def cmd_next_candidate(args):
    """Find the highest-scoring ranked candidate not yet tracked."""
    if not STATE_FILE.exists():
        sys.exit(f"State file {STATE_FILE} not found")

    with STATE_FILE.open(encoding="utf-8") as fh:
        data = json.load(fh)
    seen = data.get("seen", {})

    tracked = get_tracked_keys(TRACKER_FILE)

    candidates = []
    for key, entry in seen.items():
        comp = entry.get("company")
        title = entry.get("title")
        if not comp or not title:
            continue

        # Skip already tracked
        if (norm(comp), norm(title)) in tracked:
            continue

        # Skip expired or closed jobs
        if entry.get("status") in ("expired", "closed") or entry.get("is_active") is False:
            continue

        loc_v = entry.get("location_verdict") or (
            entry.get("location") if entry.get("location") in ("PASS", "FAIL", "FLAG") else None
        )
        if loc_v != "PASS":
            continue

        score = entry.get("rank_score")
        if score is None:
            continue

        candidates.append(
            {
                "key": key,
                "company": comp,
                "title": title,
                "score": score,
                "verdict": entry.get("rank_verdict", "Unknown"),
                "location": entry.get("location"),
                "url": entry.get("url") or key,
                "portal": entry.get("portal"),
                "strengths": entry.get("strengths", []),
                "gaps": entry.get("gaps", []),
            }
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)

    if not candidates:
        print(json.dumps({"status": "empty", "message": "No eligible unapplied candidates found"}))
        return 0

    selected = candidates[0]
    print(
        json.dumps(
            {
                "status": "ok",
                "candidate": selected,
                "remaining_unapplied": len(candidates),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_compile(args):
    """Compile an HTML file to PDF via Headless Chromium and verify 1-page bounds."""
    html_path = Path(args.html).resolve()
    pdf_path = Path(args.pdf).resolve()

    if not html_path.exists():
        sys.exit(f"HTML source {html_path} does not exist")

    # Locate chrome
    env = dict(os.environ)
    local_bin = str(Path.home() / ".local" / "bin")
    bun_bin = str(Path.home() / ".bun" / "bin")
    env["PATH"] = f"{local_bin}:{bun_bin}:{env.get('PATH', '')}"

    chrome_cmd = [
        "google-chrome-stable",
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        str(html_path),
    ]

    res = subprocess.run(chrome_cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"Chrome compilation failed: {res.stderr.strip() or res.stdout.strip()}",
                }
            )
        )
        return 1

    # Run all 5 verification gates in-process (no subprocess spawning)
    from verify_all import verify_package

    skip_gates: set[str] = set()
    if getattr(args, "no_layout_check", False):
        skip_gates.add("layout")
    if getattr(args, "no_template_check", False):
        skip_gates.add("template")
    if getattr(args, "no_humanizer_check", False):
        skip_gates.add("humanizer")
    if getattr(args, "no_sot_check", False):
        skip_gates.add("sot")

    result = verify_package(
        html_path,
        pdf_path,
        expected_pages=1,
        max_bottom_space=getattr(args, "max_bottom_space", None),
        skip=skip_gates,
    )

    # Map verify_all output to the existing JSON contract
    success = result["success"]
    print(
        json.dumps(
            {
                "success": success,
                "pdf": result["pdf"],
                "pages": result["pages"],
                "layout_clean": result["layout_clean"],
                "template_clean": result["template_clean"],
                "humanizer_clean": result["humanizer_clean"],
                "sot_clean": result["sot_clean"],
                "message": "" if success else "\n\n".join(result["errors"]),
            },
            indent=2,
        )
    )
    return 0 if success else 2


def cmd_record(args):
    """Append a newly drafted application to job_search_tracker.csv."""
    fieldnames = [
        "date",
        "company",
        "sector",
        "role",
        "role_type",
        "channel",
        "status",
        "contact_person",
        "fit_rating",
        "notes",
        "cv_file",
        "cover_letter_file",
        "source",
        "deadline",
    ]

    row = {
        "date": args.date or date.today().isoformat(),
        "company": args.company,
        "sector": args.sector or "",
        "role": args.role,
        "role_type": args.role_type or "Senior Frontend",
        "channel": args.channel or "linkedin",
        "status": args.status or "drafted",
        "contact_person": args.contact_person or "",
        "fit_rating": args.fit_rating or "90",
        "notes": args.notes or "",
        "cv_file": args.cv_file or "",
        "cover_letter_file": args.cover_letter_file or "",
        "source": args.source or "",
        "deadline": args.deadline or "",
    }

    # Write to tracker
    with TRACKER_FILE.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(row)

    print(json.dumps({"success": True, "recorded": row}, indent=2))

    if getattr(args, "archive", False):
        cmd_archive(args)

    return 0


def cmd_archive(args):
    """Archive job details and posting markdown to documents/applications/<company>_<role>/job_posting.md."""
    company = args.company.strip()
    role = args.role.strip()
    slug = re.sub(r"[^\w]+", "_", f"{company}_{role}".lower()).strip("_")

    app_dir = ROOT / "documents" / "applications" / slug
    app_dir.mkdir(parents=True, exist_ok=True)
    job_file = app_dir / "job_posting.md"

    desc = ""
    if getattr(args, "description_file", None):
        df = Path(args.description_file)
        if df.exists():
            desc = df.read_text(encoding="utf-8")
    elif getattr(args, "description", None):
        desc = args.description

    overwrite = getattr(args, "overwrite", False)
    if not job_file.exists() or overwrite:
        lines = [
            f"# {company} — {role}\n",
            f"- **Company:** {company}",
            f"- **Role:** {role}",
        ]
        loc = getattr(args, "location", None)
        if loc:
            lines.append(f"- **Location:** {loc}")
        fit = getattr(args, "fit_rating", None)
        if fit:
            lines.append(f"- **Fit Rating:** {fit} / 100")
        src = getattr(args, "source", None)
        if src:
            lines.append(f"- **Posting URL:** {src}")
        st = getattr(args, "status", None) or "drafted"
        lines.append(f"- **Status:** {st}")
        cv = getattr(args, "cv_file", None)
        if cv:
            lines.append(f"- **Generated CV:** {cv}")
        cl = getattr(args, "cover_letter_file", None)
        if cl:
            lines.append(f"- **Generated Cover Letter:** {cl}")

        lines.append("\n---\n\n## Job Description\n")
        lines.append(desc if desc else "*(Full job description text)*")
        lines.append("\n")

        job_file.write_text("\n".join(lines), encoding="utf-8")

    # Generate tailored recruiter & EM outreach notes
    outreach_file = None
    try:
        from tools.generate_outreach import generate_outreach_package
        outreach_res = generate_outreach_package(
            company=company,
            role=role,
            contact_person=getattr(args, "contact_person", "") or "",
            save=True,
            force=overwrite,
        )
        outreach_file = outreach_res.get("file")
    except Exception as exc:
        pass

    print(
        json.dumps(
            {
                "success": True,
                "archive_dir": str(app_dir),
                "job_file": str(job_file),
                "outreach_file": outreach_file,
                "slug": slug,
            },
            indent=2,
        )
    )
    return 0


def cmd_outreach(args):
    """Generate tailored LinkedIn connection notes and cold emails."""
    from tools.generate_outreach import generate_outreach_package
    res = generate_outreach_package(
        company=args.company,
        role=args.role or "Senior Frontend Engineer",
        contact_person=args.contact_person or "",
        save=True,
        force=getattr(args, "force", False),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args):
    """Show pipeline funnel metrics and application dashboard."""
    from collections import Counter

    # 1. Tracker metrics
    tracker_counts = Counter()
    total_tracked = 0
    recent_applications = []
    if TRACKER_FILE.exists():
        with TRACKER_FILE.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
            total_tracked = len(rows)
            for row in rows:
                st = (row.get("status") or "unknown").lower()
                tracker_counts[st] += 1
            for row in rows[-5:]:
                recent_applications.append({
                    "date": row.get("date", ""),
                    "company": row.get("company", ""),
                    "role": row.get("role", ""),
                    "status": row.get("status", ""),
                })

    # 2. Seen jobs metrics
    seen_counts = Counter()
    portal_counts = Counter()
    total_seen = 0
    if STATE_FILE.exists():
        try:
            doc = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            seen = doc.get("seen", doc) if isinstance(doc, dict) else {}
            total_seen = len(seen)
            for entry in seen.values():
                st = (entry.get("rank_status") or entry.get("status") or "unranked").lower()
                p = (entry.get("portal") or "unknown").lower()
                seen_counts[st] += 1
                portal_counts[p] += 1
        except Exception:
            pass

    # 3. Assets
    cv_count = len(list((ROOT / "cv").glob("Resume_*.pdf")))
    cl_count = len(list((ROOT / "cover_letters").glob("Cover_Letter_*.pdf")))
    app_dir = ROOT / "documents" / "applications"
    app_dirs = len([d for d in app_dir.iterdir() if d.is_dir()]) if app_dir.exists() else 0

    data = {
        "funnel": {
            "scraped_total": total_seen,
            "scraped_by_status": dict(seen_counts.most_common()),
            "scraped_by_portal": dict(portal_counts.most_common()),
            "tracked_total": total_tracked,
            "tracked_by_status": dict(tracker_counts.most_common()),
        },
        "assets": {
            "tailored_resumes": cv_count,
            "tailored_cover_letters": cl_count,
            "archived_applications": app_dirs,
        },
        "recent": recent_applications,
    }

    if getattr(args, "json", False):
        print(json.dumps(data, indent=2))
        return 0

    print("=" * 60)
    print("  AI JOB SEARCH PIPELINE DASHBOARD")
    print("=" * 60)
    print("📊 Application Funnel:")
    print(f"   Scraped Postings : {total_seen}")
    print(f"   Tracked Jobs     : {total_tracked}")
    for status, cnt in tracker_counts.most_common():
        print(f"     • {status.capitalize():<12} : {cnt}")
    print()
    print("📁 Tailored Assets:")
    print(f"   Resume PDFs      : {cv_count}")
    print(f"   Cover Letter PDFs: {cl_count}")
    print(f"   Application Dirs : {app_dirs}")
    print()
    print("🕒 Recent Applications:")
    for app in reversed(recent_applications):
        print(f"   [{app['date']}] {app['company']:<18} | {app['role'][:28]:<28} | {app['status']}")
    print("=" * 60)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status", help="Show pipeline funnel metrics and application dashboard")
    status_parser.add_argument("--json", action="store_true", help="Output metrics as JSON")

    sub.add_parser("next", help="Find highest scoring unapplied candidate")

    comp_parser = sub.add_parser("compile", help="Compile HTML to PDF and verify 1-page bounds and layout fill")
    comp_parser.add_argument("--html", required=True, help="Path to input HTML")
    comp_parser.add_argument("--pdf", required=True, help="Path to output PDF")
    comp_parser.add_argument(
        "--max-bottom-space",
        type=float,
        default=None,
        help="Maximum allowed bottom whitespace in pt (default: 75.0 for resumes, auto for cover letters)",
    )
    comp_parser.add_argument(
        "--no-layout-check",
        action="store_true",
        help="Skip layout geometry and fill verification",
    )
    comp_parser.add_argument(
        "--no-template-check",
        action="store_true",
        help="Skip template fidelity verification",
    )
    comp_parser.add_argument(
        "--no-humanizer-check",
        action="store_true",
        help="Skip humanizer prose verification",
    )
    comp_parser.add_argument(
        "--no-sot-check",
        action="store_true",
        help="Skip SOT grounding verification",
    )

    rec_parser = sub.add_parser("record", help="Record application in tracker")
    rec_parser.add_argument("--company", required=True)
    rec_parser.add_argument("--role", required=True)
    rec_parser.add_argument("--fit-rating", required=True)
    rec_parser.add_argument("--cv-file", required=True)
    rec_parser.add_argument("--cover-letter-file", required=True)
    rec_parser.add_argument("--source", required=True)
    rec_parser.add_argument("--date")
    rec_parser.add_argument("--sector")
    rec_parser.add_argument("--role-type")
    rec_parser.add_argument("--channel")
    rec_parser.add_argument("--status", default="drafted")
    rec_parser.add_argument("--contact-person")
    rec_parser.add_argument("--notes")
    rec_parser.add_argument("--deadline")
    rec_parser.add_argument("--archive", action="store_true", help="Also archive job details to documents/applications/<company>_<role>/job_posting.md")
    rec_parser.add_argument("--location", help="Location of the role")
    rec_parser.add_argument("--description", help="Verbatim job description text")
    rec_parser.add_argument("--description-file", help="Path to file containing job description text")
    rec_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing job_posting.md")

    arch_parser = sub.add_parser("archive", help="Archive job details to documents/applications/<company>_<role>/job_posting.md")
    arch_parser.add_argument("--company", required=True)
    arch_parser.add_argument("--role", required=True)
    arch_parser.add_argument("--source")
    arch_parser.add_argument("--location")
    arch_parser.add_argument("--fit-rating")
    arch_parser.add_argument("--cv-file")
    arch_parser.add_argument("--cover-letter-file")
    arch_parser.add_argument("--status", default="drafted")
    arch_parser.add_argument("--description")
    arch_parser.add_argument("--description-file")
    arch_parser.add_argument("--overwrite", action="store_true")

    out_parser = sub.add_parser("outreach", help="Generate tailored LinkedIn connection notes and cold emails")
    out_parser.add_argument("--company", required=True, help="Company name")
    out_parser.add_argument("--role", default="Senior Frontend Engineer", help="Role title")
    out_parser.add_argument("--contact-person", default="", help="Contact person name/email")
    out_parser.add_argument("--force", action="store_true", help="Force overwrite existing outreach notes")

    args = parser.parse_args()
    if args.command == "status":
        return cmd_status(args)
    elif args.command == "next":
        return cmd_next_candidate(args)
    elif args.command == "compile":
        return cmd_compile(args)
    elif args.command == "record":
        return cmd_record(args)
    elif args.command == "archive":
        return cmd_archive(args)
    elif args.command == "outreach":
        return cmd_outreach(args)


if __name__ == "__main__":
    sys.exit(main())
