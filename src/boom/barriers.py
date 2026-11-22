"""Rules-based barrier detectors. One small function per detector.

Each detector takes a loaded student row (see load.py) and the as-of date and
returns a Barrier or None. Evidence strings are built only from real field
values; they are for the advisor, not for student-facing messages.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from boom.load import Student

STALE_CONTACT_DAYS = 60
LOW_LOGINS_MAX = 3
MISSING_ASSIGNMENTS_MIN = 3
FAILING_GRADES = {"D", "F"}


@dataclass(frozen=True)
class Barrier:
    code: str
    label: str
    weight: int
    evidence: str


def _days(since: date, as_of: date) -> int:
    return (as_of - since).days


# --- predicates shared between detectors -----------------------------------

def has_reg_hold(s: Student) -> bool:
    return s["registration_hold"] == "Y"


def is_academic(s: Student) -> bool:
    missing = s["missing_assignments"]
    return s["lowest_current_grade"] in FAILING_GRADES or (
        missing is not None and missing >= MISSING_ASSIGNMENTS_MIN
    )


def has_lms_gap(s: Student) -> bool:
    return s["lms_logins_last_14_days"] is None or s["lms_last_login"] is None


# --- detectors ---------------------------------------------------------------

def detect_reg_hold(s: Student, as_of: date) -> Barrier | None:
    if not has_reg_hold(s):
        return None
    hold_type = s["aid_hold_type"]
    if hold_type in (None, "None"):
        hold_type = "Unspecified"
    since = s["aid_hold_since"]
    if since is not None:
        evidence = f"{hold_type} hold since {since.isoformat()} ({_days(since, as_of)} days)"
    else:
        evidence = f"{hold_type} hold (start date not recorded)"
    return Barrier("REG_HOLD", "Registration hold", 40, evidence)


def detect_not_registered(s: Student, as_of: date) -> Barrier | None:
    if s["registered_for_spring"] != "N" or has_reg_hold(s):
        return None
    return Barrier(
        "NOT_REGISTERED", "Not registered for spring", 20,
        "Not registered for spring; no registration hold on file",
    )


def detect_academic(s: Student, as_of: date) -> Barrier | None:
    if not is_academic(s):
        return None
    parts = []
    if s["lowest_current_grade"] in FAILING_GRADES:
        parts.append(f"lowest current grade {s['lowest_current_grade']}")
    missing = s["missing_assignments"]
    if missing is not None and missing >= MISSING_ASSIGNMENTS_MIN:
        parts.append(f"{missing} missing assignments")
    evidence = "; ".join(parts)
    evidence = evidence[0].upper() + evidence[1:]  # not .capitalize(): keeps "D"/"F" uppercase
    return Barrier("ACADEMIC", "Academic struggle", 20, evidence)


def detect_disengaged(s: Student, as_of: date) -> Barrier | None:
    # Low logins alone is NOT a flag; it only counts alongside ACADEMIC.
    logins = s["lms_logins_last_14_days"]
    if logins is None or logins > LOW_LOGINS_MAX or not is_academic(s):
        return None
    evidence = f"{logins} LMS login{'' if logins == 1 else 's'} in last 14 days"
    if s["lms_last_login"] is not None:
        last = s["lms_last_login"]
        evidence += f"; last login {last.isoformat()} ({_days(last, as_of)} days ago)"
    return Barrier("DISENGAGED", "Disengaged from coursework", 15, evidence)


def detect_data_gap(s: Student, as_of: date) -> Barrier | None:
    if not has_lms_gap(s):
        return None
    return Barrier(
        "DATA_GAP", "LMS data missing", 0,
        "LMS login fields blank; can't assess engagement; check Canvas sync",
    )


def detect_outreach_no_reply(s: Student, as_of: date) -> Barrier | None:
    if s["outreach_response"] != "No reply":
        return None
    channel = s["last_outreach_channel"] or "unknown channel"
    when = s["last_outreach_date"]
    evidence = f"No reply to {channel}"
    if when is not None:
        evidence += f" sent {when.isoformat()} ({_days(when, as_of)} days ago)"
    return Barrier("OUTREACH_NO_REPLY", "No reply to outreach", 10, evidence + "; try a different channel")


def detect_outreach_replied(s: Student, as_of: date) -> Barrier | None:
    if s["outreach_response"] != "Replied":
        return None
    channel = s["last_outreach_channel"] or "unknown channel"
    when = s["last_outreach_date"]
    evidence = f"Replied to {channel}"
    if when is not None:
        evidence += f" sent {when.isoformat()}"
    return Barrier("OUTREACH_REPLIED", "Replied to outreach", 0, evidence + "; follow up on their reply")


def detect_stale_contact(s: Student, as_of: date) -> Barrier | None:
    last = s["last_advisor_contact"]
    if last is None or _days(last, as_of) <= STALE_CONTACT_DAYS:
        return None
    return Barrier(
        "STALE_CONTACT", "No recent advisor contact", 10,
        f"Last advisor contact {last.isoformat()} ({_days(last, as_of)} days ago)",
    )


DETECTORS: tuple[Callable[[Student, date], Barrier | None], ...] = (
    detect_reg_hold,
    detect_not_registered,
    detect_academic,
    detect_disengaged,
    detect_data_gap,
    detect_outreach_no_reply,
    detect_outreach_replied,
    detect_stale_contact,
)


def detect_barriers(s: Student, as_of: date) -> list[Barrier]:
    return [b for b in (d(s, as_of) for d in DETECTORS) if b is not None]
