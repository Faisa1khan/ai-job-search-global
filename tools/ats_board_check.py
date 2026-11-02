#!/usr/bin/env python3
"""Verify ATS-domain sweep hits against the employer's own board API.

Section 9 of .agents/skills/scrape/search-queries.md is a dork lane: a search
engine finds a posting URL, and the index *lies* - it keeps ranking postings
that are 404 on the live board, and it carries no location, no remote flag and
no date. This script is the deterministic second half of that lane: give it the
dork's URL (or a slug) and it reads the board's own posting API, returning the
structured fields the index cannot supply and a LIVE / GONE / UNKNOWN verdict
matched by the provider's OWN posting id (never company + title).

Providers and endpoints:
    ashby            https://api.ashbyhq.com/posting-api/job-board/<slug>
    greenhouse       https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=false
    lever            https://api.lever.co/v0/postings/<slug>?mode=json
    lever-eu         https://api.eu.lever.co/v0/postings/<slug>?mode=json
    smartrecruiters  https://api.smartrecruiters.com/v1/companies/<slug>/postings?limit=100

Usage:
  python3 tools/ats_board_check.py <url-or-slug> [<url-or-slug> ...]
  python3 tools/ats_board_check.py --format table <url> ...
  python3 tools/ats_board_check.py --list-postings ashby:sarvam

Accepted inputs:
  https://jobs.ashbyhq.com/<slug>/<job-id>[/application][?query]
  https://job-boards.greenhouse.io/<slug>/jobs/<id>   (and boards.greenhouse.io)
    https://jobs.lever.co/<slug>/<job-id>   |   https://jobs.eu.lever.co/<slug>/<job-id>
    https://jobs.smartrecruiters.com/<slug>/<posting-id>
    ashby:<slug> | greenhouse:<slug> | lever:<slug> | lever-eu:<slug> | smartrecruiters:<slug>
  <slug>                                               (bare slug: provider guessed)

Caveats this script exists to encode:
  * An Ashby posting-API 404 is NOT an expiry verdict - some boards serve the
    page while the API 404s (measured: madecard). That reads UNKNOWN, not GONE.
  * Lever `createdAt` is epoch MILLISECONDS; Greenhouse `updated_at` is an
    update stamp, not a post date - both are labelled as such in the output.
  * Aggregator boards (lever/jobgether) re-post other employers' roles; they
    are flagged `aggregator` so a sweep can exclude the double count.
    * SmartRecruiters slugs are CASE-EXACT (`BoschGroup`, not `bosch`): a wrong
      case answers HTTP 200 with an empty content list and totalFound 0, which
      reads like an empty board instead of a bad slug. Read `board_total`.
    * SmartRecruiters paginates. A board listing carries `board_total` from the
      API's own totalFound, so truncation is visible rather than silent.
      `--country <cc>` narrows a smartrecruiters board to one country (e.g. in).

Exit status: 0 when every input resolved, 1 when any input came back UNKNOWN.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HONEST_UA = "Claude-User"  # repo convention (tools/robots_check.py); public board APIs only
TIMEOUT = 45

# Lever boards that re-post OTHER employers' requisitions - a hit here is not a
# hit on that company's own board, and the same posting usually already runs
# through its own portal CLI.
AGGREGATOR_SLUGS = {"jobgether", "hiring-cafe", "himalayas", "remotivejobs"}

ASHBY_RE = re.compile(r"(?:jobs\.)?ashbyhq\.com/([^/?#]+)(?:/([0-9a-fA-F-]{20,}))?", re.I)
GREENHOUSE_RE = re.compile(
    r"(?:job-)?boards\.greenhouse\.io/(?:embed/job_app\?for=)?([^/?#]+)(?:/jobs/(\d+))?", re.I
)
GREENHOUSE_EMBED_RE = re.compile(r"job-boards\.greenhouse\.io/embed/job_app\?for=([^&]+)&token=(\d+)", re.I)
LEVER_RE = re.compile(r"jobs\.lever\.co/([^/?#]+)(?:/([0-9a-fA-F-]{20,}))?", re.I)
LEVER_EU_RE = re.compile(r"jobs\.eu\.lever\.co/([^/?#]+)(?:/([0-9a-fA-F-]{20,}))?", re.I)
# The provider id is a long digit string (e.g. 744000154191149); the optional
# second group is only accepted when it is all digits so a slug is never eaten.
SMARTRECRUITERS_RE = re.compile(r"(?:jobs\.)?smartrecruiters\.com/([A-Za-z0-9._-]+)(?:/(\d{6,}))?", re.I)

# Board-listing query extras set from the CLI (--country). Kept module-level so
# every checker keeps the same (slug, posting_id) signature.
BOARD_QUERY = {}


def fetch_json(url):
    """curl to a file, then parse. urllib hangs on some hosts and curl's own
    output can carry raw control characters that json.loads rejects strictly."""
    fd, path = tempfile.mkstemp(prefix="ats_board_", suffix=".json")
    os.close(fd)
    try:
        proc = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(TIMEOUT), "-A", HONEST_UA,
             "-w", "\n%{http_code}", "-o", path, url],
            capture_output=True, text=True, timeout=TIMEOUT + 15,
        )
        code = (proc.stdout or "").strip().splitlines()[-1:] or [""]
        http_code = int(code[0]) if code[0].isdigit() else 0
        raw = open(path, encoding="utf-8", errors="replace").read()
        if http_code != 200:
            return None, http_code, raw[:200]
        try:
            return json.loads(raw, strict=False), http_code, ""
        except Exception as exc:  # noqa: BLE001 - report, never crash a sweep
            return None, http_code, f"json parse: {exc}"
    except Exception as exc:  # noqa: BLE001
        return None, 0, str(exc)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def parse_target(text):
    """-> (provider, slug, posting_id or None)"""
    text = text.strip()
    m = GREENHOUSE_EMBED_RE.search(text)
    if m:
        return "greenhouse", m.group(1), m.group(2)
    for pattern, provider in ((SMARTRECRUITERS_RE, "smartrecruiters"),
                              (LEVER_EU_RE, "lever-eu"),
                              (ASHBY_RE, "ashby"), (GREENHOUSE_RE, "greenhouse"),
                              (LEVER_RE, "lever")):
        m = pattern.search(text)
        if m:
            return provider, m.group(1), (m.group(2) or None)
    if ":" in text:
        provider, slug = text.split(":", 1)
        if provider.lower() in ("ashby", "greenhouse", "lever", "lever-eu", "smartrecruiters"):
            return provider.lower(), slug.strip(), None
    return None, text, None  # bare slug; provider guessed from the API that answers


def iso_from_ms(value):
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def check_ashby(slug, posting_id):
    data, code, err = fetch_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    )
    if code == 404:
        return {"board_status": "api_404", "verdict": "UNKNOWN", "reason":
                "Ashby posting API 404 - board may still serve the page; confirm on the board page"}
    if data is None:
        return {"board_status": f"http_{code}", "verdict": "UNKNOWN", "reason": err}
    jobs = data.get("jobs") or []
    rows = [{
        "id": j.get("id"), "title": j.get("title"), "location": j.get("location"),
        "is_remote": j.get("isRemote"), "workplace": j.get("workplaceType"),
        "posted_date": (j.get("publishedAt") or "")[:10], "url": j.get("jobUrl"),
        "listed": j.get("isListed"), "team": j.get("team"), "department": j.get("department"),
    } for j in jobs if j.get("isListed") is not False]
    if posting_id:
        hit = [r for r in rows if str(r["id"]).lower() == posting_id.lower()]
        if not hit:
            return {"board_status": "200", "verdict": "GONE", "reason":
                    "posting id absent from the live board listing", "board_size": len(rows)}
        return {"board_status": "200", "verdict": "LIVE", "posting": hit[0], "board_size": len(rows)}
    return {"board_status": "200", "verdict": "LIVE", "postings": rows, "board_size": len(rows)}


def check_greenhouse(slug, posting_id):
    if posting_id:
        data, code, err = fetch_json(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{posting_id}?content=false"
        )
        if code == 404:
            return {"board_status": "api_404", "verdict": "GONE", "reason": "single-requisition 404"}
        if data is None:
            return {"board_status": f"http_{code}", "verdict": "UNKNOWN", "reason": err}
        return {"board_status": "200", "verdict": "LIVE", "posting": {
            "id": str(data.get("id")), "title": data.get("title"),
            "location": (data.get("location") or {}).get("name"),
            "posted_date": (data.get("updated_at") or "")[:10],
            "date_meaning": "updated_at (update stamp, not a post date)",
            "url": data.get("absolute_url"),
        }}
    data, code, err = fetch_json(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
    )
    if data is None:
        return {"board_status": f"http_{code}", "verdict": "UNKNOWN", "reason": err}
    rows = [{
        "id": str(j.get("id")), "title": j.get("title"),
        "location": (j.get("location") or {}).get("name"),
        "posted_date": (j.get("updated_at") or "")[:10],
        "date_meaning": "updated_at (update stamp, not a post date)",
        "url": j.get("absolute_url"),
    } for j in data.get("jobs") or []]
    return {"board_status": "200", "verdict": "LIVE", "postings": rows, "board_size": len(rows)}


def check_lever(slug, posting_id, host="api.lever.co"):
    data, code, err = fetch_json(f"https://{host}/v0/postings/{slug}?mode=json")
    if data is None:
        return {"board_status": f"http_{code}", "verdict": "UNKNOWN", "reason": err}
    rows = [{
        "id": j.get("id"), "title": j.get("text"),
        "location": (j.get("categories") or {}).get("location"),
        "team": (j.get("categories") or {}).get("team"),
        "posted_date": iso_from_ms(j.get("createdAt")), "url": j.get("hostedUrl"),
    } for j in data]
    if posting_id:
        hit = [r for r in rows if str(r["id"]).lower() == posting_id.lower()]
        if not hit:
            return {"board_status": "200", "verdict": "GONE", "reason":
                    "posting id absent from the live board listing", "board_size": len(rows)}
        return {"board_status": "200", "verdict": "LIVE", "posting": hit[0], "board_size": len(rows)}
    return {"board_status": "200", "verdict": "LIVE", "postings": rows, "board_size": len(rows)}


def check_smartrecruiters(slug, posting_id):
    """SmartRecruiters public postings API.

    Two traps this encodes, both measured 2026-10-07:
      * the slug is CASE-EXACT - a wrong-case slug answers 200 with
        content: [] and totalFound: 0, which reads as an empty board;
      * the list endpoint paginates (limit=100 here) while totalFound reports
        the whole board, so a truncated listing is reported as board_total
        rather than passed off as complete.
    """
    base = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    if posting_id:
        data, code, err = fetch_json(f"{base}/{posting_id}")
        if code == 404:
            return {"board_status": "api_404", "verdict": "GONE",
                    "reason": "single-posting 404 on the employer's own board API"}
        if data is None:
            return {"board_status": f"http_{code}", "verdict": "UNKNOWN", "reason": err}
        loc = data.get("location") or {}
        return {"board_status": "200", "verdict": "LIVE", "posting": {
            "id": str(data.get("id")), "title": data.get("name"),
            "location": ", ".join(str(x) for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x),
            "posted_date": (data.get("releasedDate") or "")[:10],
            "date_meaning": "releasedDate (the provider's own publish date)",
            "url": data.get("applyUrl"), "active": data.get("active"),
        }}
    query = "?limit=100"
    if BOARD_QUERY.get("country"):
        query += f"&country={BOARD_QUERY['country']}"
    data, code, err = fetch_json(base + query)
    if data is None:
        return {"board_status": f"http_{code}", "verdict": "UNKNOWN", "reason": err}
    rows = []
    for j in data.get("content") or []:
        loc = j.get("location") or {}
        rows.append({
            "id": str(j.get("id")), "title": j.get("name"),
            "location": ", ".join(str(x) for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x),
            "posted_date": (j.get("releasedDate") or "")[:10], "url": j.get("applyUrl"),
        })
    out = {"board_status": "200", "verdict": "LIVE", "postings": rows, "board_size": len(rows)}
    if data.get("totalFound") is not None:
        out["board_total"] = data.get("totalFound")
    return out


CHECKERS = {"ashby": check_ashby, "greenhouse": check_greenhouse, "lever": check_lever,
            "lever-eu": lambda slug, pid: check_lever(slug, pid, host="api.eu.lever.co"),
            "smartrecruiters": check_smartrecruiters}


def resolve(text):
    provider, slug, posting_id = parse_target(text)
    providers = [provider] if provider else ["ashby", "greenhouse", "lever", "smartrecruiters"]
    last = None
    for candidate in providers:
        result = CHECKERS[candidate](slug, posting_id)
        result.update({"input": text, "provider": candidate, "slug": slug,
                       "posting_id": posting_id})
        if candidate == "lever" and slug.lower() in AGGREGATOR_SLUGS:
            result["aggregator"] = True
            result["reason"] = (result.get("reason") or "") + \
                " aggregator board: re-posts other employers' requisitions; exclude to avoid double counting"
        if result["board_status"] == "200":
            return result
        last = result
    return last


def main():
    ap = argparse.ArgumentParser(description="Verify a sweep hit against the employer's own ATS board API")
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--format", choices=["json", "table"], default="json")
    ap.add_argument("--list-postings", metavar="PROVIDER:SLUG",
                    help="print every live posting on a board instead of one verdict")
    ap.add_argument("--country", metavar="CC",
                      help="narrow a smartrecruiters board listing to one country code, e.g. in")
    args = ap.parse_args()
    if args.country:
        BOARD_QUERY["country"] = args.country.strip().lower()

    results = [resolve(t) for t in args.targets]

    if args.format == "json":
        print(json.dumps({"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "board_query": BOARD_QUERY or None, "results": results}, indent=2))
    else:
        for r in results:
            p = r.get("posting") or {}
            print(f"{r['verdict']:<7} {r['provider']:<15} {r['slug']:<22} "
                  f"{(p.get('title') or '')[:44]:<44} {str(p.get('location'))[:22]:<22} "
                  f"{(p.get('posted_date') or ''):<10} {str(p.get('is_remote')):<5} "
                  f"{(p.get('url') or '')[:78]}")
            if r.get("reason"):
                print(f"        note: {r['reason']}")
            if r.get("board_size") is not None and not r.get("posting"):
                for q in (r.get("postings") or [])[:40]:
                    print(f"        {q.get('posted_date','')[:10]:<10} {(q.get('title') or '')[:48]:<48} "
                          f"{str(q.get('location'))[:24]:<24} {q.get('url')}")

    return 1 if any(r.get("verdict") == "UNKNOWN" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
