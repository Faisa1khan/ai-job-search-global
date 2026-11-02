#!/usr/bin/env python3
"""Have I already applied here? Asked BEFORE a CV is built. Advisory, read-only.

Ported from career-ops-hq/career-ops `precheck-duplicate.mjs` (MIT, upstream 3d30cf14).
The matching rules, tier order and the "a lookup with no usable key is not an all-clear"
rule are upstream's. The tracker reader is ours: their rows carry a `url` column and a
dedicated applications file, while ours are `job_search_tracker.csv` with the posting URL
living in `source` or `notes`.

Deliberate reductions, so nobody assumes more fidelity than exists:
  * `parent-org` is not implemented. Upstream needs it because their company cells carry
    bracketed units ("Fabrikam University (East)" vs "(West)"); ours do not. Same-title and
    similar-title cover the cases our tracker actually contains.
  * Title similarity uses upstream's 0.6 Jaccard threshold with their seniority and level
    guards, but not the full stopword table.

Tier order, strongest first:
  1 url          exact normalised posting URL
  1 req          same requisition id at the same or a parent company
  2 same-title   same company, same title identity (word-set equality, order-free)
  3 similar-title same company, Jaccard >= 0.6 with seniority guards

A row whose status is `rejected` still matches, but is flagged warning=True: re-applying
to a company that already turned you down is a decision, not an accident.

Usage:
  python3 tools/precheck_duplicate.py --company "Intellias" --title "Senior React + Next.js Engineer"
  python3 tools/precheck_duplicate.py --url https://... --json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REPO = Path(__file__).resolve().parent.parent
TRACKER = REPO / "job_search_tracker.csv"

# Click/campaign params only. Keep literal: stripping a functional param merges two
# distinct postings, which is the silent failure direction.
TRACKING_PARAMS = [
    re.compile(r"^utm_", re.I), re.compile(r"^gh_src$", re.I), re.compile(r"^fbclid$", re.I),
    re.compile(r"^gclid$", re.I), re.compile(r"^mc_cid$", re.I), re.compile(r"^mc_eid$", re.I),
    re.compile(r"^igshid$", re.I), re.compile(r"^_hsenc$", re.I), re.compile(r"^_hsmi$", re.I),
    re.compile(r"^trk$", re.I), re.compile(r"^trackingid$", re.I),
]

CORPORATE_FORMS = re.compile(
    r"\b(?:pvt|private|ltd|limited|llc|llp|inc|incorporated|corp|corporation|co|company|"
    r"gmbh|plc|ag|sa|bv|technologies|technology|labs?|solutions?|systems?|services?)\b",
    re.I)

SENIORITY = {
    "intern", "trainee", "junior", "jr", "associate", "mid", "senior", "sr",
    "staff", "principal", "lead", "head", "director", "vp", "chief", "distinguished", "fellow",
}
SUB_BASELINE = {"intern", "trainee", "junior", "jr", "associate"}

LEVEL_RE = re.compile(r"\b(?:i{1,3}|iv|v|1|2|3|4|5)$", re.I)

# Location suffixes that may be stripped from a title before comparison. Only positively
# recognised labels are removed, so "Software Engineer (Backend)" is left intact.
REGION_CODES = set("""AB BC MB NB NL NS NT NU ON PE QC SK YT AL AK AZ AR CA CO CT DE FL GA HI ID IL IN
IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA
WV WI WY DC UK USA US CAN CA GB""".split())
REGION_NAMES = {"alberta", "british columbia", "manitoba", "new brunswick", "newfoundland and labrador",
                "nova scotia", "ontario", "prince edward island", "quebec", "saskatchewan",
                "canada", "united states", "usa", "united kingdom", "uk", "north america",
                "emea", "apac", "gta", "greater toronto area", "california", "texas", "new york",
                "florida", "washington", "illinois", "massachusetts", "india", "bangalore",
                "bengaluru", "hyderabad", "pune", "mumbai", "chennai", "gurgaon", "gurugram",
                "noida", "delhi", "ncr"}
BARE_CITIES = {"toronto", "vancouver", "montreal", "ottawa", "calgary", "edmonton", "winnipeg",
               "halifax", "mississauga", "brampton", "markham", "vaughan", "hamilton",
               "kitchener", "waterloo", "london", "victoria", "regina", "saskatoon",
               "quebec city", "new york", "chicago", "austin", "seattle", "boston",
               "san francisco", "los angeles", "denver", "atlanta", "dallas", "houston", "miami"}
WORK_MODE = re.compile(r"^(?:(?:fully |100% )?remote|hybrid|on[- ]?site|in[- ]office|work from home|wfh)$", re.I)


def normalize_url(raw: str) -> str:
    """Canonical posting key. Returns '' when the input is not a usable http(s) URL."""
    if not isinstance(raw, str):
        return ""
    s = raw.strip()
    if not s:
        return ""
    try:
        u = urlsplit(s)
    except ValueError:
        return ""
    if u.scheme.lower() not in ("http", "https") or not u.netloc:
        return ""
    host = u.netloc.lower()
    keep = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
            if not any(p.search(k) for p in TRACKING_PARAMS)]
    path = u.path.rstrip("/")
    return urlunsplit(("https", host, path, urlencode(sorted(keep)), ""))


def norm_req(value: str) -> str:
    """'JR9727' == 'JR-9727' == '9727'; only a leading label is dropped."""
    s = str(value or "").strip().upper()
    m = re.match(r"^(?:REQ|JR|R|JOB|POSTING|ID)[-\s:#_]*(\S*\d\S*)$", s)
    return m.group(1) if m else s


def extract_req_number(text: str) -> str:
    m = re.search(r"\b(?:REQ|JR|R|JOB|POSTING|ID)[-\s:#_]*\S*\d\S*", str(text or ""), re.I)
    return m.group(0) if m else ""


def title_identity_key(title: str) -> str:
    """Accent-free, lowercased, punctuation-collapsed word set, sorted. Order-free."""
    t = unicodedata.normalize("NFD", str(title or ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").lower()
    words = [w for w in re.sub(r"[^a-z0-9]+", " ", t).split() if w]
    if not words:
        return str(title or "").lower()
    return " ".join(sorted(set(words)))


def _is_location_like(text: str) -> bool:
    parts = [p for p in re.split(r"\s*[,/;]\s*", text.strip().lower()) if p]
    if not parts:
        return False
    for p in parts:
        if WORK_MODE.match(p) or p in REGION_NAMES or p in BARE_CITIES or p.upper() in REGION_CODES:
            continue
        return False
    return True


def strip_location_suffix(title: str) -> str:
    m = re.match(r"^(.*\S)\s*\(([^()]*)\)$", str(title or "").strip())
    if not m or LEVEL_RE.search(m.group(2).strip()) or not _is_location_like(m.group(2)):
        return str(title or "").strip()
    return m.group(1).strip()


def company_key(name: str) -> str:
    t = unicodedata.normalize("NFD", str(name or ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").lower()
    t = CORPORATE_FORMS.sub(" ", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def company_relation(a: str, b: str) -> str | None:
    ka, kb = company_key(a), company_key(b)
    if not ka or not kb:
        return None
    if ka == kb:
        return "same"
    ta = [w for w in re.split(r"\s+", re.sub(r"[^a-z0-9]+", " ", str(a or "").lower())) if w]
    tb = [w for w in re.split(r"\s+", re.sub(r"[^a-z0-9]+", " ", str(b or "").lower())) if w]
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(shorter) >= 2 and longer[:len(shorter)] == shorter:
        return "parent"
    return None


def _tokens(title: str) -> set[str]:
    t = unicodedata.normalize("NFD", str(title or ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").lower()
    return {w for w in re.split(r"[^a-z0-9]+", t) if w}


def _seniorities(title: str) -> set[str]:
    return {w for w in _tokens(title) if w in SENIORITY}


def role_fuzzy_match(a: str, b: str) -> bool:
    ta, tb = str(a or "").strip().lower(), str(b or "").strip().lower()
    if ta and ta == tb:
        return True
    sa, sb = _seniorities(a), _seniorities(b)
    if sa and sb:
        if not (sa & sb):
            return False
    elif sa or sb:
        if (sa or sb) & SUB_BASELINE:
            return False
    # token sets excluding seniority words and generic job vocabulary
    stop = SENIORITY | {"engineer", "developer", "software", "the", "and", "of", "a", "an"}
    ja = _tokens(a) - stop
    jb = _tokens(b) - stop
    if not ja or not jb:
        return bool(_tokens(a) & _tokens(b))
    overlap = ja & jb
    union = ja | jb
    return bool(union) and len(overlap) / len(union) >= 0.6


TIER = {"url": 1, "req": 1, "same-title": 2, "similar-title": 3}
DETAIL = {
    "url": "same posting URL",
    "req": "same requisition",
    "same-title": "same company, same title",
    "similar-title": "same company, similar title",
}


def row_url(row: dict) -> str:
    """Our tracker has no url column: the posting URL is in `source`, or in `notes`."""
    for key in ("source", "notes"):
        val = (row.get(key) or "").strip()
        m = re.search(r"https?://\S+", val)
        if m:
            return m.group(0)
    return ""


def find_duplicates(rows: list[dict], company: str = "", title: str = "",
                    req: str = "", url: str = "") -> list[dict]:
    want_url = normalize_url(url)
    want_req = norm_req(req)
    clean = strip_location_suffix(title)
    want_title_key = title_identity_key(clean) if clean else ""

    out: list[dict] = []
    for row in rows:
        rel = company_relation(company, row.get("company", ""))
        reason = None
        if want_url and normalize_url(row_url(row)) == want_url:
            reason = "url"
        elif want_req and rel and norm_req(extract_req_number(row.get("notes", ""))) == want_req:
            reason = "req"
        elif rel == "same" and want_title_key and \
                title_identity_key(strip_location_suffix(row.get("role", ""))) == want_title_key:
            reason = "same-title"
        elif rel == "same" and clean and role_fuzzy_match(clean, strip_location_suffix(row.get("role", ""))):
            reason = "similar-title"
        if not reason:
            continue
        out.append({
            "date": row.get("date", ""),
            "company": row.get("company", ""),
            "role": row.get("role", ""),
            "status": row.get("status", ""),
            "reason": reason,
            "detail": DETAIL[reason],
            "tier": TIER[reason],
            "warning": row.get("status", "") == "rejected",
        })
    # Stable: strongest tier first, then newest date first within a tier.
    out.sort(key=lambda c: str(c["date"]), reverse=True)
    out.sort(key=lambda c: c["tier"])
    return out


def load_rows(path: Path = TRACKER) -> list[dict] | None:
    if not path.exists():
        return None
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Have I applied here before? Advisory, read-only.")
    ap.add_argument("--company", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--req", default="")
    ap.add_argument("--url", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not a.company and not a.url:
        print("precheck_duplicate: --company (or --url) is required.", file=sys.stderr)
        return 1
    if not a.title.strip() and not a.req.strip() and not a.url.strip():
        print("precheck_duplicate: give at least one of --title, --req or --url besides --company.",
              file=sys.stderr)
        return 1
    if a.url and not normalize_url(a.url):
        print(f'precheck_duplicate: --url "{a.url}" is not a usable URL.', file=sys.stderr)
        return 1

    rows = load_rows()
    if rows is None:
        print("No tracker found, nothing to compare against.")
        return 0
    cands = find_duplicates(rows, a.company, a.title, a.req, a.url)

    # Rows at the same company whose role never got recorded cannot be compared on title,
    # so they are reported separately instead of being scored as candidates. Our tracker
    # has these ("Naukri application (role not stated in receipt)") and staying silent about
    # them would read as an all-clear to someone scanning the output.
    matched = {(c["date"], c["company"], c["role"]) for c in cands}
    unresolved = []
    if a.company:
        for row in rows:
            if company_relation(a.company, row.get("company", "")) != "same":
                continue
            if (row.get("date"), row.get("company"), row.get("role")) in matched:
                continue
            role = (row.get("role") or "").strip()
            if not role or re.search(r"not stated|unresolved|unknown", role, re.I):
                unresolved.append(row)

    if a.json:
        print(json.dumps({"tracker": str(TRACKER), "checked": vars(a) | {"json": None},
                          "candidates": cands,
                          "same_company_with_unresolved_role": [
                              {k: r.get(k, "") for k in ("date", "company", "role", "status")}
                              for r in unresolved]}, indent=1, default=str))
        return 0
    if not cands and not unresolved:
        print("No possible duplicate in the tracker.")
        return 0
    if cands:
        print(f"Possible duplicate(s) in the tracker ({len(cands)}), advisory, nothing written:")
        for c in cands:
            flag = "WARN " if c["warning"] else "     "
            print(f'{flag}{c["date"]} | {c["company"]} | {c["role"]} | {c["status"]} | {c["detail"]}')
    if unresolved:
        print("\nSame company, role never recorded, so title cannot be compared:")
        for r in unresolved:
            print(f'     {r.get("date", "")} | {r.get("company", "")} | '
                  f'{r.get("role", "")} | {r.get("status", "")} | check by hand')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
