#!/usr/bin/env python3
"""Deterministic implementation of /scrape Step 3's screen.

The screen was prose in .agents/skills/scrape/SKILL.md, and prose gets skipped: the
second clean sweep (2026-09-30) still presented 10 foreign non-remote rows (Singapore,
Vietnam, Indonesia, Hong Kong, Riyadh) and 7 out-of-discipline titles (C++, Python
x2, .NET, PHP, Salesforce, Data Platform). This tool makes the same rules checkable,
so a run can be gated on them instead of trusted.

Rules (kept in sync with Step 3 - if you change one, change both):

  geography   eligible = anywhere in India (remote or NCR on-site/hybrid) OR genuinely
              remote-eligible wherever the employer sits. A foreign place on a posting
              that is not remote-eligible is out; so is an Indian city outside NCR when
              the posting is not remote-eligible. A country-locked foreign remote
              ("Remote (US)", "Canada EOR") is out. A blank location is NOT screened -
              the portal reported nothing and guessing is forbidden; it is reported.
  title-family  manager|director|head of|vp|architect|principal|analyst|sales|
              business development|product manager|recruiter
  discipline  mobile|ios|android|react native|backend|devops|sre|qa|support, plus
              data/ml/nlp/data platform as multi-word forms ("data" alone is a
              frontend title word - "Frontend Engineer, Data Product Experiences")
  language    a non-JS primary stack (c++, c#, .net, python, php, ruby, golang, rust,
              salesforce, sap, spark) with NO JS/frontend token in the title
  non-english-title  Developpeur, Desenvolvedora, Entwickler, Desarrollador, ...

With --liveness, every surviving `new` entry that carries a URL is also classified by
tools/liveness_check.py, which can only ever prove a posting CLOSED:

  expired     real closure evidence (HTTP 404/410, an expired URL, a closure banner whose
              own clause is not opened by "until"/"if"/"once"). With --apply it becomes
              status=expired. Nothing else is ever written as a drop.
  uncertain   everything else - no render, no apply control, bot wall, fetch failure, no
              URL. Recorded with its code, and the row KEEPS status=new so the next run
              re-checks it. `uncertain` is a result, never a pass, and never a removal.

The asymmetry is the point: a false `expired` writes a real job out of every future scan,
while a false `uncertain` costs one more look.

Usage:
  python3 tools/screen_jobs.py                 # report violations (exit 1 if any)
  python3 tools/screen_jobs.py --apply         # flip violating `new` entries to `skipped`
  python3 tools/screen_jobs.py --liveness      # also prove closure (one fetch per entry)
  python3 tools/screen_jobs.py --state <path>  # non-default state file
  python3 tools/screen_jobs.py --json          # machine-readable report

Only entries whose status is `new` are ever considered or written. Nothing else in
the file is touched. The liveness pass is opt-in because it is the only part of this
tool that touches the network; the screen itself stays deterministic and offline.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

DEFAULT_STATE = Path("job_scraper/seen_jobs.json")

_LIVENESS = None

NCR = re.compile(
    r"gurgaon|gurugram|noida|greater noida|new delhi|delhi|faridabad|ghaziabad|\bncr\b",
    re.I,
)
INDIA = re.compile(
    r"india|\bin\b|bangalore|bengaluru|hyderabad|pune|chennai|mumbai|ahmedabad|jaipur|"
    r"kolkata|kochi|cochin|indore|coimbatore|lucknow|chandigarh|trivandrum|"
    r"thiruvananthapuram|mysore|nagpur|surat|vadodara|karnataka|maharashtra|telangana|"
    r"tamil nadu|gujarat|haryana|uttar pradesh|kerala|punjab|rajasthan|west bengal",
    re.I,
)
# A country-level India location ("India", "in") is ambiguous: aggregators label
# remote-India roles that way. It is kept; only a named non-NCR Indian city is screened.
INDIA_COUNTRY_ONLY = re.compile(r"^\s*(india|in|bharat)\s*$", re.I)
REMOTE = re.compile(
    r"remote|work from home|wfh|work from anywhere|anywhere|distributed team|"
    r"worldwide|global\b",
    re.I,
)
GLOBAL_OK = re.compile(r"remote|anywhere|worldwide|global|distributed", re.I)
# A real "no country restriction" signal for the remote-eligibility test: "remote" alone
# is NOT one, or "Remote: Vietnam" would read as open-to-anywhere.
WORLDWIDE = re.compile(r"worldwide|anywhere|global|distributed|no restriction", re.I)
FOREIGN = re.compile(
    r"singapore|vietnam|hanoi|ho chi minh|indonesia|jakarta|hong kong|riyadh|saudi|dubai|"
    r"uae|abu dhabi|qatar|singapore|malaysia|kuala lumpur|thailand|bangkok|philippines|"
    r"manila|japan|tokyo|korea|seoul|taiwan|taipei|china|shanghai|beijing|australia|"
    r"sydney|melbourne|new zealand|auckland|poland|krakow|warsaw|germany|berlin|munich|"
    r"hamburg|france|paris|montpellier|spain|madrid|barcelona|portugal|lisbon|romania|"
    r"bucharest|bulgaria|sofia|ukraine|kyiv|hungary|budapest|czech|prague|slovakia|"
    r"slovenia|serbia|belgrade|croatia|zagreb|greece|athens|austria|vienna|switzerland|"
    r"zurich|netherlands|amsterdam|belgium|brussels|denmark|copenhagen|sweden|stockholm|"
    r"norway|oslo|finland|helsinki|estonia|latvia|lithuania|ireland|dublin|united kingdom|"
    r"\buk\b|london|england|scotland|edinburgh|manchester|canada|toronto|vancouver|ontario|"
    r"quebec|united states|\busa\b|\bus\b|new york|san francisco|bay area|boston|austin|"
    r"seattle|bellevue|chicago|denver|atlanta|washington|texas|california|mexico|brazil|"
    r"sao paulo|argentina|colombia|chile|peru|nigeria|lagos|kenya|nairobi|egypt|cairo|"
    r"israel|tel aviv|turkiye|turkey|istanbul|karachi|pakistan|lahore|bangladesh|dhaka|"
    r"south africa|durban|johannesburg|cape town|latam|emea|europe",
    re.I,
)
COUNTRY_LOCKED_REMOTE = re.compile(
    r"remote\s*[\(\[]?\s*(us|usa|united states|canada|ca|uk|eu|europe|germany|singapore|"
    r"australia|japan|brazil|mexico|india only)\s*[\)\]]?\s*(only)?",
    re.I,
)
TITLE_FAMILY = re.compile(
    r"\b(manager|director|head of|vp|vice president|architect|principal|analyst|sales|"
    r"business development|product manager|recruiter|marketing)\b",
    re.I,
)
DISCIPLINE = re.compile(
    r"\b(mobile|ios|android|react native|backend|back-end|devops|sre|site reliability|"
    r"qa|quality assurance|support engineer|security engineer)\b|"
    r"data engineer|data scientist|data platform|data pipeline|machine learning|"
    r"\bml engineer\b|\bnlp\b",
    re.I,
)
NON_JS_STACK = re.compile(
    r"c\+\+|\bc#\b|\.net|python|php|ruby|golang|\bgo\b|rust|salesforce|\bsap\b|spark|scala|"
    r"\bjava\b(?!script)",
    re.I,
)
JS_TOKEN = re.compile(
    r"react|next\.?js|javascript|\bjs\b|typescript|\bts\b|frontend|front-end|front end|"
    r"\bui\b|\bweb\b|node|angular|vue|svelte|ember",
    re.I,
)
NON_ENGLISH_TITLE = re.compile(
    r"developpeur|développeur|desenvolvedor|desenvolvedora|entwickler|desarrollador|"
    r"ingenieur|ingénieur|ingegnere|sviluppatore|разработчик|프론트엔드|開発",
    re.I,
)


def screen_entry(title: str | None, location: str | None) -> list[str]:
    """Return the list of rule names this entry violates (empty = keep)."""
    title = title or ""
    location = location or ""
    hits: list[str] = []

    if TITLE_FAMILY.search(title):
        hits.append("title-family")
    if DISCIPLINE.search(title):
        hits.append("discipline")
    if NON_JS_STACK.search(title) and not JS_TOKEN.search(title):
        hits.append("non-js-stack")
    if NON_ENGLISH_TITLE.search(title):
        hits.append("non-english-title")

    # Geography: decided last, and only when the title rules did not already drop it.
    # A remote signal in the title counts too - "Senior Full Stack Engineer (Remote)" with
    # a Bangalore location is a remote posting, not a Bangalore on-site one. But a remote
    # posting tied to a foreign place ("Remote: Vietnam", "Remote, Singapore") is
    # country-scoped and is screened like any other country-locked remote.
    if location:
        remote_eligible = bool(REMOTE.search(location) or REMOTE.search(title))
        worldwide = bool(WORLDWIDE.search(location) or WORLDWIDE.search(title))
        foreign_place = bool(FOREIGN.search(location))
        if COUNTRY_LOCKED_REMOTE.search(location) and not worldwide:
            hits.append("geography-country-locked")
        elif remote_eligible and foreign_place and not worldwide and not INDIA.search(location):
            # "Remote: Vietnam" / "Remote, Singapore" - country-scoped remote. An India
            # mention keeps it ("Remote - India / Singapore" is India-eligible).
            hits.append("geography-country-locked")
        elif remote_eligible:
            pass  # remote-eligible anywhere is in scope
        elif NCR.search(location) and not foreign_place:
            pass  # NCR on-site/hybrid is in scope (Manila's NCR is not India's)
        elif INDIA_COUNTRY_ONLY.match(location):
            pass  # country-only India: ambiguous, kept (see INDIA_COUNTRY_ONLY)
        else:
            # Default-deny: not remote-eligible, not NCR, not country-only India - so a
            # named place that is out, whether or not its country is in the FOREIGN list.
            # Listing foreign countries instead leaked Costa Rica, Wellington, Manila and
            # Charlotte, NC (all presented as new on 2026-09-30). India non-NCR cities
            # (Bengaluru, Pune...) land here too, which is the rule.
            hits.append("geography")
    return hits


def _liveness_module():
    """Import tools/liveness_check.py lazily: the screen itself must stay offline."""
    global _LIVENESS
    if _LIVENESS is None:
        here = str(Path(__file__).resolve().parent)
        if here not in sys.path:
            sys.path.insert(0, here)
        import liveness_check  # noqa: PLC0415 - lazy on purpose (network module)
        _LIVENESS = liveness_check
    return _LIVENESS


def liveness_for(url, fetch=None) -> dict:
    """Classify one posting. Anything short of proven closure comes back `uncertain`.

    This wrapper is the safety boundary: a missing URL, a missing module, a crash or a
    fetch failure all return `uncertain`, so no failure path can ever write a row out of
    the pipeline. Only liveness_check's own `expired` verdict is passed through.
    """
    if not str(url or "").strip():
        return {"result": "uncertain", "code": "no_url",
                "reason": "entry carries no posting URL"}
    try:
        check = fetch or _liveness_module().check_url
        res = check(str(url))
    except Exception as exc:  # noqa: BLE001 - advisory tool, never fatal
        return {"result": "uncertain", "code": "check_failed",
                "reason": f"{type(exc).__name__}: {exc}"}
    if not isinstance(res, dict) or not res.get("result"):
        return {"result": "uncertain", "code": "check_failed",
                "reason": "liveness check returned no verdict"}
    return res


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--apply", action="store_true", help="flip violating new entries to skipped")
    parser.add_argument("--liveness", action="store_true",
                        help="also prove closure via tools/liveness_check.py (network)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    path = Path(args.state)
    data = json.loads(path.read_text(encoding="utf-8"))
    seen = data.get("seen", {})

    violations = []
    blank_location = []
    expired = []
    unproven = []
    for key, entry in seen.items():
        if entry.get("status") != "new":
            continue
        rules = screen_entry(entry.get("title"), entry.get("location"))
        if rules:
            violations.append((key, entry, rules))
            continue
        if not entry.get("location"):
            blank_location.append((key, entry))
        if args.liveness:
            res = liveness_for(entry.get("url"))
            if res.get("result") == "expired":
                expired.append((key, entry, res))
            else:
                unproven.append((key, entry, res))

    if args.json:
        report = {
            "violations": [
                {"key": k, "rules": r, "title": e.get("title"), "company": e.get("company"),
                 "location": e.get("location"), "url": e.get("url")}
                for k, e, r in violations
            ],
            "blank_location": [
                {"key": k, "title": e.get("title"), "company": e.get("company")}
                for k, e in blank_location
            ],
            "counts": {
                "violations": len(violations),
                "by_rule": {rule: sum(1 for _, _, rs in violations if rule in rs)
                            for rule in sorted({r for _, _, rs in violations for r in rs})},
                "blank_location": len(blank_location),
            },
        }
        if args.liveness:
            report["expired"] = [
                {"key": k, "code": r.get("code"), "reason": r.get("reason"),
                 "title": e.get("title"), "company": e.get("company"), "url": e.get("url")}
                for k, e, r in expired
            ]
            report["liveness_unproven"] = [
                {"key": k, "result": r.get("result"), "code": r.get("code"),
                 "title": e.get("title"), "company": e.get("company"), "url": e.get("url")}
                for k, e, r in unproven
            ]
            report["counts"]["expired"] = len(expired)
            report["counts"]["liveness_unproven"] = len(unproven)
        print(json.dumps(report, indent=2))
    else:
        print(f"scanned {sum(1 for e in seen.values() if e.get('status') == 'new')} entries with status=new")
        if violations:
            print(f"\n{len(violations)} entries violate Step 3's screen "
                  f"(they should be status=skipped, never presented):\n")
            for key, entry, rules in violations:
                print(f"  [{','.join(rules)}] {str(entry.get('title'))[:52]:52s} "
                      f"{str(entry.get('company'))[:16]:16s} {str(entry.get('location'))[:30]}")
        else:
            print("\nno violations: every presented entry passes Step 3's screen")
        if blank_location:
            print(f"\n{len(blank_location)} presented entries have no location "
                  f"(portal reported none - not screened, listed for visibility):")
            for key, entry in blank_location:
                print(f"  {str(entry.get('title'))[:52]:52s} {str(entry.get('company'))[:20]}")
        if args.liveness:
            if expired:
                print(f"\n{len(expired)} entries prove CLOSED "
                      f"(status=expired with --apply, never presented):\n")
                for key, entry, res in expired:
                    print(f"  [{res.get('code')}] {str(entry.get('title'))[:52]:52s} "
                          f"{str(entry.get('company'))[:16]:16s} {str(entry.get('url'))[:48]}")
            else:
                print("\nno entry proves closed: every checked posting stays in the pipeline")
            if unproven:
                by_code = {}
                for _, _, res in unproven:
                    by_code[str(res.get("code"))] = by_code.get(str(res.get("code")), 0) + 1
                detail = ", ".join(f"{code} x{n}" for code, n in sorted(by_code.items()))
                print(f"\n{len(unproven)} entries not proven expired and KEPT as new "
                      f"(uncertain is a result, never a drop): {detail}")
        print()

    if args.apply:
        changed = bool(violations)
        for key, entry, _ in violations:
            entry["status"] = "skipped"
        checked = datetime.date.today().isoformat()
        for key, entry, res in expired:
            entry["status"] = "expired"
            entry["liveness"] = {"result": "expired", "code": res.get("code", ""),
                                 "checked": checked}
            changed = True
        for key, entry, res in unproven:
            entry["liveness"] = {"result": res.get("result", ""), "code": res.get("code", ""),
                                 "checked": checked}
            changed = True
        if changed:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            if violations:
                print(f"applied: {len(violations)} entries flipped to status=skipped in {path}")
            if expired:
                print(f"applied: {len(expired)} entries flipped to status=expired in {path}")
            if unproven:
                print(f"applied: {len(unproven)} entries kept as new, "
                      f"liveness code recorded in {path}")

    return 1 if (violations or expired) and not args.apply else 0


if __name__ == "__main__":
    sys.exit(main())
