"""Acceptance checks from CLAUDE.md, run against the real test CSV."""
from datetime import date
from pathlib import Path

import pytest

from boom.barriers import detect_barriers
from boom.load import load_students

CSV = Path(__file__).resolve().parents[1] / "data" / "boom_test_students_50.csv"
AS_OF = date(2026, 11, 19)


def ids(prefix_range):
    return {f"S{n}" for n in prefix_range}


@pytest.fixture(scope="module")
def students():
    return {s["student_id"]: s for s in load_students(CSV)}


@pytest.fixture(scope="module")
def codes(students):
    return {
        sid: {b.code for b in detect_barriers(s, AS_OF)}
        for sid, s in students.items()
    }


def with_code(codes, code):
    return {sid for sid, cs in codes.items() if code in cs}


# --- loader ------------------------------------------------------------------

def test_loads_50_students(students):
    assert len(students) == 50


def test_blank_lms_fields_are_none_not_zero(students):
    for sid in ("S100129", "S100130", "S100131"):
        assert students[sid]["lms_logins_last_14_days"] is None
        assert students[sid]["lms_last_login"] is None
    assert students["S100101"]["lms_logins_last_14_days"] == 0  # a real zero


def test_literal_none_hold_type_is_kept(students):
    assert students["S100138"]["aid_hold_type"] == "None"


# --- acceptance checks -------------------------------------------------------

TOP_SIX = ids(range(100100, 100106))
HOLD_ONLY = ids(range(100106, 100112))
NOT_REG_NO_HOLD = ids(range(100124, 100129))
ACADEMIC_NO_REG_BLOCKER = ids(range(100112, 100120))
REPLIED = {"S100114", "S100118"}
DATA_GAP = {"S100129", "S100130", "S100131"}
LOW_LOGINS_DOING_FINE = ids(range(100120, 100124))


def test_twelve_reg_holds(codes):
    assert with_code(codes, "REG_HOLD") == TOP_SIX | HOLD_ONLY


def test_top_six_have_hold_academic_disengaged_no_reply(codes):
    for sid in TOP_SIX:
        assert {"REG_HOLD", "ACADEMIC", "DISENGAGED", "OUTREACH_NO_REPLY"} <= codes[sid], sid
    full_combo = {
        sid for sid, cs in codes.items()
        if {"REG_HOLD", "ACADEMIC", "DISENGAGED", "OUTREACH_NO_REPLY"} <= cs
    }
    assert full_combo == TOP_SIX


def test_hold_only_students(codes):
    for sid in HOLD_ONLY:
        assert codes[sid] == {"REG_HOLD"}, sid


def test_not_registered_without_hold(codes):
    assert with_code(codes, "NOT_REGISTERED") == NOT_REG_NO_HOLD
    for sid in NOT_REG_NO_HOLD:
        assert "REG_HOLD" not in codes[sid]


def test_academic_without_registration_blocker(codes):
    academic_no_blocker = {
        sid for sid in with_code(codes, "ACADEMIC")
        if not codes[sid] & {"REG_HOLD", "NOT_REGISTERED"}
    }
    assert academic_no_blocker == ACADEMIC_NO_REG_BLOCKER


def test_s100119_academic_but_not_disengaged(codes):
    assert "ACADEMIC" in codes["S100119"]
    assert "DISENGAGED" not in codes["S100119"]  # 4 logins


def test_disengaged_requires_academic(codes):
    for sid in with_code(codes, "DISENGAGED"):
        assert "ACADEMIC" in codes[sid], sid


def test_replied_students_get_follow_up(students):
    replied = {
        sid for sid, s in students.items()
        if any(b.code == "OUTREACH_REPLIED" for b in detect_barriers(s, AS_OF))
    }
    assert replied == REPLIED
    for sid in REPLIED:
        barriers = detect_barriers(students[sid], AS_OF)
        assert "OUTREACH_NO_REPLY" not in {b.code for b in barriers}
        replied_b = next(b for b in barriers if b.code == "OUTREACH_REPLIED")
        assert "follow up on their reply" in replied_b.evidence


def test_data_gap(codes):
    assert with_code(codes, "DATA_GAP") == DATA_GAP
    for sid in DATA_GAP:
        assert "DISENGAGED" not in codes[sid]  # blank != 0 logins


def test_low_logins_but_fine_not_flagged(codes):
    for sid in LOW_LOGINS_DOING_FINE:
        assert codes[sid] == set(), sid


def test_22_students_have_no_flags(codes):
    assert sum(1 for cs in codes.values() if not cs) == 22


# --- evidence cites real values ----------------------------------------------

def test_reg_hold_evidence_has_type_and_age(students):
    b = next(b for b in detect_barriers(students["S100100"], AS_OF) if b.code == "REG_HOLD")
    assert b.evidence == "Unpaid balance hold since 2026-10-12 (38 days)"
    assert b.weight == 40


def test_academic_evidence_keeps_grade_letter(students):
    b = next(b for b in detect_barriers(students["S100101"], AS_OF) if b.code == "ACADEMIC")
    assert b.evidence == "Lowest current grade D; 8 missing assignments"


def test_stale_contact_boundary(students):
    # S100131: last contact 2026-09-20 is exactly 60 days -> not stale.
    assert "STALE_CONTACT" not in {b.code for b in detect_barriers(students["S100131"], AS_OF)}
    # S100101: 2026-07-29 is 113 days -> stale.
    assert "STALE_CONTACT" in {b.code for b in detect_barriers(students["S100101"], AS_OF)}
