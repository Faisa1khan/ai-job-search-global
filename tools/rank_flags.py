#!/usr/bin/env python3
"""Three triage flags the rank step was missing: compensation, timezone, years bar.

Provenance: both ideas come from career-ops-plugin's `references/scoring-rubric.md`
(compensation is a scored dimension; a target 30%+ above the band is flagged, not
fatal) and its graded location/remote dimension. Neither ported as a score weight:
they are FLAGS that print beside the score and never exclude a job, following the
rule this repo already uses for India eligibility.

Where the band comes from - measured, not assumed (2026-10-07):
  * Ashby `?includeCompensation=true`: 0 bands across 5 boards (sarvam 41 jobs,
    plane 33, ramp 160, notion 133, openai 817).
  * Lever `salaryRange`: 0 across 2 boards (jobgether 3,280 postings, meesho 60).
  * SmartRecruiters posting objects carry no compensation field.
So the board APIs are NOT a compensation source in practice. The flag therefore
reads the posting text (and any band a board row does happen to carry) and
answers UNKNOWN when neither states one. It never estimates a band, and it never
converts one currency to another to manufacture a comparison.

Target ladder (canonical - SOT line 36, mirrored in 01-candidate-profile.md):
  floor (never accept below) · anchor · target range · stretch — set your own via
  JOBSEARCH_FLOOR_INR / JOBSEARCH_ANCHOR_INR / JOBSEARCH_TARGET_HIGH_INR.

The years flag is the third (2026-10-30): /scrape's screen never read how many years a
posting asks for, and three of five postings reviewed by hand that day carried a floor
above the 6.8-year record. It delegates to tools/jd_years.py so there is one parser
rather than two, and like the other two it only annotates - a parser miss must never
become a silent drop.

Usage:
  python3 tools/rank_flags.py comp --band "20-24 LPA"
  python3 tools/rank_flags.py comp --text posting.txt
  python3 tools/rank_flags.py tz --text posting.txt
  python3 tools/rank_flags.py years --text posting.txt
  python3 tools/rank_flags.py both --text posting.txt --band-low 1800000 --band-high 2600000

Exit status: 0 unless an argument is unusable (2).
"""

import argparse
import os
import json
import re
import sys
from pathlib import Path

# Compensation ladder, in rupees. Neutral (0 = unset) by default so a public
# clone carries nobody's number; a fork sets JOBSEARCH_FLOOR_INR,
# JOBSEARCH_ANCHOR_INR and JOBSEARCH_TARGET_HIGH_INR from its own ledger, or
# passes --target. With them unset no band can read BELOW_FLOOR.
FLOOR_INR = int(os.environ.get("JOBSEARCH_FLOOR_INR") or 0)
ANCHOR_INR = int(os.environ.get("JOBSEARCH_ANCHOR_INR") or 0)
TARGET_HIGH_INR = int(os.environ.get("JOBSEARCH_TARGET_HIGH_INR") or 0)
MISMATCH_RATIO = 1.3       # target more than 30% above the band's top
LPA = 100_000

# IST working day used for the overlap test (09:30-18:30 IST).
IST_DAY_START = 9.5
IST_DAY_END = 18.5
TIGHT_OVERLAP_HOURS = 3.0
LATE_END_IST = 22.0  # a shared day ending after 22:00 IST is a late-night role

TZ_OFFSETS = {
    "utc": 0.0, "gmt": 0.0, "bst": 1.0, "cet": 1.0, "cest": 2.0, "eet": 2.0,
    "eest": 3.0, "est": -5.0, "edt": -4.0, "cst": -6.0, "cdt": -5.0,
    "mst": -7.0, "mdt": -6.0, "pst": -8.0, "pdt": -7.0, "ist": 5.5,
    "sgt": 8.0, "hkt": 8.0, "jst": 9.0, "aest": 10.0, "aedt": 11.0,
}
IST_OFFSET = 5.5


def to_int_inr(amount, unit=None):
    """'12' + LPA -> 1200000 ; '800000' -> 800000 ; None -> None."""
    if amount is None:
        return None
    value = float(str(amount).replace(",", ""))
    if unit and unit.lower() == "lpa":
        return int(round(value * LPA))
    return int(round(value))


def parse_band(text):
    """Pull an INR band out of posting text.

    Recognises, in order of specificity:
      "₹20-24 LPA" / "20 to 24 LPA" / "₹18 LPA"          (LPA unit)
      "₹12,00,000 - ₹18,00,000" / "1200000-1800000"      (absolute)
    Returns (low, high, currency, raw) - low/high None when nothing was stated.
    A non-INR symbol short-circuits to currency-only so no conversion is faked.
    """
    if not text:
        return None, None, None, None
    flat = re.sub(r"\s+", " ", text)

    # A currency SYMBOL is not a band. Measured 2026-10-07: a posting reading
    # "accelerate toward our $50M goal" was reported as "band stated in USD",
    # which is a false positive - the symbol has to carry an AMOUNT, and the
    # amount has to sit in salary context, before this is a band at all.
    if not re.search(r"₹|INR|Rs\.?|LPA", flat):
        for sym, code in (("$", "USD"), ("€", "EUR"), ("£", "GBP"), ("S$", "SGD")):
            amount = re.search(re.escape(sym) + r"\s?\d[\d,.]{2,}", flat)
            if amount:
                near = flat[max(0, amount.start() - 90):amount.end() + 90]
                if re.search(r"salary|compensation|base|per annum|annual|CTC|remuneration|package|band|range|lakhs?|LPA",
                             near, re.I):
                    return None, None, code, f"non-INR band present ({amount.group(0).strip()}), not compared"

    lpa = re.search(
        r"(?:₹|INR|Rs\.?)?\s*([0-9]{1,3}(?:\.[0-9]{1,2})?)\s*(?:-|–|to|—)\s*"
        r"([0-9]{1,3}(?:\.[0-9]{1,2})?)\s*(?:LPA|lakhs?|lacs?)",
        flat, re.I,
    )
    if lpa:
        lo, hi = to_int_inr(lpa.group(1), "lpa"), to_int_inr(lpa.group(2), "lpa")
        return lo, hi, "INR", lpa.group(0).strip()

    single = re.search(r"(?:₹|INR|Rs\.?)?\s*([0-9]{1,3}(?:\.[0-9]{1,2})?)\s*(?:LPA|lakhs?|lacs?)", flat, re.I)
    if single:
        v = to_int_inr(single.group(1), "lpa")
        return v, v, "INR", single.group(0).strip()

    absolute = re.search(
        r"(?:₹|INR|Rs\.?)\s*([0-9][0-9,]{4,})\s*(?:-|–|to|—)\s*(?:₹|INR|Rs\.?)?\s*([0-9][0-9,]{4,})",
        flat, re.I,
    )
    if absolute:
        return (to_int_inr(absolute.group(1)), to_int_inr(absolute.group(2)), "INR",
                absolute.group(0).strip())

    single_abs = re.search(r"(?:₹|INR|Rs\.?)\s*([0-9][0-9,]{4,})", flat, re.I)
    if single_abs:
        v = to_int_inr(single_abs.group(1))
        return v, v, "INR", single_abs.group(0).strip()

    return None, None, None, None


def comp_flag(band_low, band_high, currency="INR", target=ANCHOR_INR):
    """OK / BELOW_FLOOR / MISMATCH_ABOVE / MISMATCH_BELOW / UNKNOWN / UNKNOWN_CURRENCY.

    Never excludes a job: the caller prints the flag beside the score. The floor is
    the SOT's never-accept-below line, so it is the one verdict worth acting on.
    """
    if currency and currency != "INR":
        return {"flag": "UNKNOWN_CURRENCY",
                "reason": f"band stated in {currency}; not compared to INR (no conversion is faked)",
                "currency": currency, "target_inr": target}
    if band_high is None and band_low is None:
        return {"flag": "UNKNOWN", "reason": "no band stated in the posting text or board row",
                "target_inr": target}
    top = band_high if band_high is not None else band_low
    out = {"target_inr": target, "band_low_inr": band_low, "band_high_inr": band_high,
           "floor_inr": FLOOR_INR}
    if top < FLOOR_INR:
        out["flag"] = "BELOW_FLOOR"
        out["reason"] = (f"band top ₹{top:,} is below the ₹{FLOOR_INR:,} floor "
                         "(2.0x, never accept below)")
        return out
    if target > MISMATCH_RATIO * top:
        out["flag"] = "MISMATCH_ABOVE"
        out["reason"] = (f"anchor ₹{target:,} is more than {int((MISMATCH_RATIO - 1) * 100)}% "
                         f"above the band top ₹{top:,}; flag, do not exclude")
        return out
    if band_low is not None and band_low > target:
        out["flag"] = "MISMATCH_BELOW"
        out["reason"] = (f"band starts at ₹{band_low:,}, above the anchor ₹{target:,}; "
                         "strong money for the level")
        return out
    out["flag"] = "OK"
    out["reason"] = f"band overlaps the target range (anchor ₹{target:,})"
    return out


YEARS_WARNING_FLAGS = ("YEARS_OUT",)


def years_flag(text, years=None, stretch=None):
    """IN / OUT / UNKNOWN for the years bar the posting states. Annotates, never filters.

    Delegates to tools/jd_years.py, which vendors the parser, so there is one definition
    of "how many years does this ask for" rather than two. A posting that states nothing,
    states it inside a preferred-only section, or scopes it to a single skill returns
    YEARS_UNKNOWN - the absent case is the normal case, and an advisory flag that guesses
    is worse than one that abstains.

    YEARS_OUT is never a drop: the parser reads text, and a parser miss that excluded a
    job would be silent. Same rule as comp_flag - print the flag beside the score.
    """
    try:
        here = str(Path(__file__).resolve().parent)
        if here not in sys.path:
            sys.path.insert(0, here)
        import jd_years
    except Exception as exc:  # noqa: BLE001 - advisory tool, never fatal
        return {"flag": "YEARS_UNKNOWN", "verdict": "unknown", "band": "", "status": "unread",
                "reason": f"years parser unavailable: {type(exc).__name__}: {exc}"}

    ys = jd_years.CANDIDATE_YEARS if years is None else years
    st = jd_years.STRETCH_YEARS if stretch is None else stretch
    try:
        res = jd_years.band_for_text(text or "", ys, st)
    except Exception as exc:  # noqa: BLE001 - a parser crash is an abstention, not a verdict
        return {"flag": "YEARS_UNKNOWN", "verdict": "unknown", "band": "", "status": "unread",
                "reason": f"years parser failed: {type(exc).__name__}: {exc}"}

    label = str(res.get("label") or "")
    status = str(res.get("status") or "unread")
    verdict = str(res.get("verdict") or "unknown").lower()
    out = {"verdict": verdict, "band": label, "status": status,
           "min": res.get("min"), "max": res.get("max"),
           "confident": bool(res.get("confident")),
           "candidate_years": ys, "stretch_reaches": round(ys + st, 2)}

    if verdict == "in":
        out["flag"] = "YEARS_IN"
        floor = out.get("min")
        # "IN" is not "comfortable": an 8+ bar passes only because the stretch reaches it,
        # and saying "inside the record" there would overstate a borderline posting.
        reach = (f"in reach only on the stretch to {ys + st:g}"
                 if isinstance(floor, (int, float)) and floor > ys
                 else f"inside the {ys:g} yr record")
        out["reason"] = (f"posting states {label or 'a reachable floor'} ({status}); {reach}")
    elif verdict == "out":
        out["flag"] = "YEARS_OUT"
        out["reason"] = (f"posting states {label or 'a floor'} ({status}), above the {ys:g} yr "
                         f"record and the {ys + st:g} yr stretch; flag, never a drop")
    else:
        out["flag"] = "YEARS_UNKNOWN"
        default_detail = {"none": "no years bar stated",
                          "unread": "posting not read",
                          "preferred-only": "preferred-only years bar, does not gate",
                          "skill-only": "skill-scoped years bar, does not gate"}.get(
                              status, f"{status} years bar")
        detail = str(res.get("reason") or default_detail)
        if label and label != "none stated":
            detail += f" (read as {label})"
        out["reason"] = detail
    return out


def find_windows(text):
    """Find stated working windows with a timezone label, e.g. '9am-6pm GMT'."""
    if not text:
        return []
    flat = re.sub(r"\s+", " ", text)
    hits = []
    pattern = re.compile(
        r"([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)?\s*(?:-|–|to|—)\s*"
        r"([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)?\s*"
        r"(UTC|GMT|BST|CET|CEST|EET|EEST|EST|EDT|CST|CDT|MST|MDT|PST|PDT|IST|SGT|HKT|JST|AEST|AEDT)"
        r"(?:\s*([+-][0-9]{1,2})(?::([0-9]{2}))?)?",
        re.I,
    )
    for m in pattern.finditer(flat):
        start = _to_hours(m.group(1), m.group(2), m.group(3))
        end = _to_hours(m.group(4), m.group(5), m.group(6))
        if start is None or end is None:
            continue
        label = m.group(7).upper()
        offset = TZ_OFFSETS.get(label.lower())
        if m.group(8):  # explicit numeric offset wins over the label
            sign = -1 if m.group(8).startswith("-") else 1
            offset = sign * (abs(float(m.group(8))) + (float(m.group(9) or 0) / 60.0))
        if offset is None:
            continue
        # local -> UTC is a SUBTRACTION (offset is local-minus-UTC): 09:00 PST
        # (offset -8) is 17:00 UTC, not 01:00. Measured: the inverted sign made a
        # PST role read as 06:30-15:30 IST.
        hits.append({"raw": m.group(0).strip(), "label": label, "offset": offset,
                     "start": start - offset, "end": end - offset})
    return hits


def _to_hours(hh, mm, meridiem):
    try:
        h = int(hh) + (int(mm) / 60.0 if mm else 0.0)
    except (TypeError, ValueError):
        return None
    if meridiem:
        if meridiem.lower() == "pm" and h < 12:
            h += 12
        elif meridiem.lower() == "am" and h == 12:
            h = 0
    return h if 0 <= h <= 24 else None


def tz_flag(text, candidate_offset=IST_OFFSET):
    """OK / TIGHT / UNKNOWN for each stated working window, measured against IST.

    The point is the Easyship shape: 'Remote - Global' with 9am-6pm GMT hours is
    not a location failure, but it is a real constraint from IST, and a binary
    location veto reports it as fine.
    """
    windows = find_windows(text)
    if not windows:
        return {"flag": "UNKNOWN", "reason": "no working window with a timezone stated",
                "candidate_offset": candidate_offset, "windows": []}
    best = None
    for w in windows:
        # w["start"]/w["end"] are already expressed in UTC by find_windows, so the
        # local hour is UTC + the candidate's own offset. Subtracting w["offset"]
        # here as well double-counts the zone (measured: PST 9-18 read as GMT+IST).
        start_local = w["start"] + candidate_offset
        end_local = w["end"] + candidate_offset
        start_local %= 24
        end_local %= 24
        if end_local <= start_local:
            end_local += 24
        overlap = max(0.0, min(end_local, IST_DAY_END) - max(start_local, IST_DAY_START))
        w_out = dict(w)
        w_out.update({"in_ist": f"{_hhmm(start_local)}-{_hhmm(end_local % 24)}",
                      "overlap_hours_with_0930_1830_ist": round(overlap, 1)})
        if best is None or overlap > best["overlap_hours_with_0930_1830_ist"]:
            best = w_out
    if best is None:  # every window lacked a usable offset
        return {"flag": "UNKNOWN", "reason": "stated hours carry no resolvable timezone",
                "candidate_offset": candidate_offset, "windows": windows}
    late_end = _end_hour(best["in_ist"]) > LATE_END_IST
    flag = "TIGHT" if (best["overlap_hours_with_0930_1830_ist"] < TIGHT_OVERLAP_HOURS or late_end) else "OK"
    return {"flag": flag, "candidate_offset": candidate_offset, "windows": windows,
            "best_overlap": best,
            "late_end_ist": late_end,
            "reason": (f"stated hours {best['raw']} = {best['in_ist']} IST, "
                       f"{best['overlap_hours_with_0930_1830_ist']}h inside a 09:30-18:30 IST day"
                       + ("; ends after 22:00 IST, so a late-night overlap" if late_end else ""))}


def _end_hour(in_ist):
    """The end hour of a rendered 'HH:MM-HH:MM' IST window, unwrapping past midnight."""
    try:
        end = in_ist.split("-")[1]
        h, m = (int(x) for x in end.split(":"))
    except (IndexError, ValueError):
        return 0.0
    return h + (m / 60.0)


def _hhmm(hours):
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 60:
        h, m = h + 1, 0
    return f"{h % 24:02d}:{m:02d}"


# The flags that earn a line in a report. UNKNOWN is the honest absence of a
# stated band or window and is the normal case (measured 2026-10-08: five of five
# archived postings returned UNKNOWN on both), and OK is fine - so neither is a
# warning, and printing them would lengthen every daily report for no signal.
COMP_WARNING_FLAGS = ("BELOW_FLOOR", "MISMATCH_ABOVE", "MISMATCH_BELOW")
TZ_WARNING_FLAGS = ("TIGHT",)


def warning_line(comp, tz, years=None):
    """One line for the warning(s) in a stored comp_flag/tz_flag/years_flag set, or None.

    This is the single definition of "worth printing": the daily pick list and the
    rank report both call it and print nothing when it returns None, so a quiet day
    stays as short as it was before the flags existed.
    """
    parts = []
    if isinstance(comp, dict) and comp.get("flag") in COMP_WARNING_FLAGS:
        parts.append("pay: " + str(comp.get("reason") or comp["flag"]))
    if isinstance(years, dict) and years.get("flag") in YEARS_WARNING_FLAGS:
        parts.append("years: " + str(years.get("reason") or years["flag"]))
    if isinstance(tz, dict) and tz.get("flag") in TZ_WARNING_FLAGS:
        best = tz.get("best_overlap") or {}
        if best:
            line = (f"hours: {best.get('raw')} = {best.get('in_ist')} IST, "
                    f"{best.get('overlap_hours_with_0930_1830_ist')}h inside a 09:30-18:30 IST day")
            if tz.get("late_end_ist"):
                line += ", ends after 22:00 IST"
        else:
            line = "hours: " + str(tz.get("reason") or tz["flag"])
        parts.append(line)
    if not parts:
        return None
    return " | ".join(dict.fromkeys(parts))


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser(description="Compensation and timezone flags for rank triage")
    ap.add_argument("mode", choices=["comp", "tz", "years", "both"])
    ap.add_argument("--text", help="posting text file to read the band and/or hours from")
    ap.add_argument("--band", help='a stated band, e.g. "20-24 LPA"')
    ap.add_argument("--band-low", type=int, help="explicit band floor in INR")
    ap.add_argument("--band-high", type=int, help="explicit band top in INR")
    ap.add_argument("--target", type=int, default=ANCHOR_INR,
                    help=f"candidate anchor in INR (default {ANCHOR_INR})")
    ap.add_argument("--years", type=float, default=None,
                    help="candidate years of experience (default: tools/jd_years.py's 6.8)")
    ap.add_argument("--stretch", type=float, default=None,
                    help="years of stretch above the record (default: tools/jd_years.py's 1.2)")
    args = ap.parse_args()

    text = read_text(args.text) if args.text else ""
    out = {}
    if args.mode in ("comp", "both"):
        low, high, currency, raw = (args.band_low, args.band_high, "INR", None)
        if low is None and high is None:
            low, high, currency, raw = parse_band(args.band or text)
        res = comp_flag(low, high, currency or "INR", target=args.target)
        if raw:
            res["band_raw"] = raw
        out["compensation"] = res
    if args.mode in ("tz", "both"):
        out["timezone"] = tz_flag(text)
    if args.mode in ("years", "both"):
        out["years"] = years_flag(text, args.years, args.stretch)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
