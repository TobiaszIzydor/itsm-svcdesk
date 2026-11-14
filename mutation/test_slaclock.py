# ai-generated: 80% - Claude Code wrote the tests from the docstrings of slaclock.py; the choice of boundaries to pin is mine
"""Tests of slaclock.py: every boundary its docstrings specify (Lab 5, Stretch 1, P-29).

Behaviour only - no test reads the module's text - and every call happens inside a test function, so a mutant that
raises makes a test fail instead of breaking collection.
"""

from datetime import datetime, timedelta

import pytest

from slaclock import (
    add_business_minutes,
    business_minutes_between,
    escalation_tier,
    is_business_time,
    parse_duration,
    priority_of,
    sla_state,
    targets,
)

# 2026-11-16 is a Monday; the week runs to Sunday 2026-11-22.
MON, TUE, WED, THU, FRI, SAT, SUN = (datetime(2026, 11, 16 + d) for d in range(7))


def at(day: datetime, hh: int, mm: int = 0, ss: int = 0, us: int = 0) -> datetime:
    return day.replace(hour=hh, minute=mm, second=ss, microsecond=us)


# --- priority_of --------------------------------------------------------------------------------

@pytest.mark.parametrize("impact,urgency,expected", [
    (1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (1, 3, "P3"), (2, 2, "P3"), (3, 1, "P3"),
    (2, 3, "P4"), (3, 2, "P4"), (3, 3, "P4"),
])
def test_priority_matrix(impact, urgency, expected):
    assert priority_of(impact, urgency) == expected
    assert priority_of(impact, urgency, False) == expected
    assert priority_of(impact, urgency, vip=False) == expected


@pytest.mark.parametrize("impact,urgency,expected", [
    (1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (1, 3, "P2"), (2, 2, "P2"), (3, 1, "P2"),
    (2, 3, "P2"), (3, 2, "P2"), (3, 3, "P2"),
])
def test_priority_vip_never_below_p2(impact, urgency, expected):
    assert priority_of(impact, urgency, vip=True) == expected
    assert priority_of(impact, urgency, True) == expected


@pytest.mark.parametrize("impact,urgency", [
    (0, 1), (1, 0), (4, 1), (1, 4), (-1, 2), (2.0, 1), (1, 2.0), (True, 1), (1, True), ("1", 1), (1, "1"),
    (None, 1), (3, 4), (4, 3), (0, 0),
])
def test_priority_rejects(impact, urgency):
    with pytest.raises(ValueError):
        priority_of(impact, urgency)
    with pytest.raises(ValueError):
        priority_of(impact, urgency, vip=True)


def test_priority_returns_string():
    assert isinstance(priority_of(2, 2), str)


# --- targets --------------------------------------------------------------------------------------

def test_targets_exact():
    assert targets("P1") == (15, 240)
    assert targets("P2") == (60, 480)
    assert targets("P3") == (240, 1440)
    assert targets("P4") == (480, 4320)
    assert tuple(targets("P1")) == (15, 240)


@pytest.mark.parametrize("bad", ["p1", " P1", "P1 ", "P5", "P0", "", "P", "p4"])
def test_targets_rejects(bad):
    with pytest.raises(ValueError):
        targets(bad)


# --- sla_state ------------------------------------------------------------------------------------

@pytest.mark.parametrize("elapsed,target,expected", [
    (0, 15, "ok"), (11, 15, "ok"), (12, 15, "warning"), (15, 15, "warning"), (16, 15, "breached"),
    (74, 100, "ok"), (75, 100, "warning"), (76, 100, "warning"), (99, 100, "warning"), (100, 100, "warning"),
    (101, 100, "breached"), (1000, 100, "breached"),
    (0, 1, "ok"), (1, 1, "warning"), (2, 1, "breached"),
    (2, 4, "ok"), (3, 4, "warning"), (4, 4, "warning"), (5, 4, "breached"),
    (179, 240, "ok"), (180, 240, "warning"), (240, 240, "warning"), (241, 240, "breached"),
])
def test_sla_state(elapsed, target, expected):
    assert sla_state(elapsed, target) == expected


@pytest.mark.parametrize("elapsed,target", [(-1, 15), (0, 0), (5, 0), (5, -1), (-1, -1), (0, -15)])
def test_sla_state_rejects(elapsed, target):
    with pytest.raises(ValueError):
        sla_state(elapsed, target)


def test_sla_state_zero_elapsed_is_ok():
    assert sla_state(0, 1) == "ok"
    assert sla_state(0, 4320) == "ok"


# --- is_business_time -----------------------------------------------------------------------------

@pytest.mark.parametrize("moment,expected", [
    (at(MON, 8, 0), True), (at(MON, 7, 59), False), (at(MON, 15, 59), True), (at(MON, 16, 0), False),
    (at(MON, 12, 0), True), (at(MON, 0, 0), False), (at(MON, 23, 59), False), (at(MON, 16, 1), False),
    (at(FRI, 8, 0), True), (at(FRI, 15, 59), True), (at(FRI, 16, 0), False),
    (at(SAT, 12, 0), False), (at(SUN, 12, 0), False), (at(SAT, 8, 0), False), (at(SUN, 15, 59), False),
    (at(TUE, 9, 30), True), (at(WED, 7, 0), False), (at(THU, 14, 0), True),
    (at(MON, 7, 59, 59), False), (at(MON, 15, 59, 59), True),
])
def test_is_business_time(moment, expected):
    assert is_business_time(moment) is expected


# --- add_business_minutes -------------------------------------------------------------------------

@pytest.mark.parametrize("start,minutes,expected", [
    (at(MON, 9), 0, at(MON, 9)),
    (at(MON, 9), 1, at(MON, 9, 1)),
    (at(MON, 9), 60, at(MON, 10)),
    (at(MON, 8), 480, at(MON, 16)),             # ends exactly at closing: 16:00 that day
    (at(MON, 8), 481, at(TUE, 8, 1)),
    (at(MON, 15), 60, at(MON, 16)),
    (at(MON, 15), 61, at(TUE, 8, 1)),
    (at(MON, 15, 59), 1, at(MON, 16)),
    (at(MON, 15, 59), 2, at(TUE, 8, 1)),
    (at(MON, 6), 0, at(MON, 8)),                # before opening -> 08:00 the same day
    (at(MON, 6), 30, at(MON, 8, 30)),
    (at(MON, 7, 59), 1, at(MON, 8, 1)),
    (at(MON, 16), 0, at(TUE, 8)),               # at closing -> next business day
    (at(MON, 17), 15, at(TUE, 8, 15)),
    (at(FRI, 15), 120, at(MON + timedelta(days=7), 9)),
    (at(FRI, 16), 0, at(MON + timedelta(days=7), 8)),
    (at(SAT, 10), 0, at(MON + timedelta(days=7), 8)),
    (at(SUN, 23, 59), 10, at(MON + timedelta(days=7), 8, 10)),
    (at(MON, 8), 960, at(TUE, 16)),
    (at(MON, 8), 2400, at(FRI, 16)),
    (at(MON, 8), 2401, at(MON + timedelta(days=7), 8, 1)),
    (at(MON, 9, 0, 59, 999), 30, at(MON, 9, 30)),  # seconds and microseconds ignored
    (at(MON, 15, 59, 30), 1, at(MON, 16)),
])
def test_add_business_minutes(start, minutes, expected):
    assert add_business_minutes(start, minutes) == expected


def test_add_business_minutes_result_has_no_seconds():
    due = add_business_minutes(at(MON, 9, 0, 45, 123), 5)
    assert due.second == 0 and due.microsecond == 0


def test_add_business_minutes_rejects_negative():
    with pytest.raises(ValueError):
        add_business_minutes(at(MON, 9), -1)


def test_add_business_minutes_long_but_allowed():
    # about 250 business days fit in 366 calendar days; 200 days * 480 minutes stays inside the limit
    due = add_business_minutes(at(MON, 8), 200 * 480)
    assert (due - at(MON, 8)).days <= 366
    assert business_minutes_between(at(MON, 8), due) == 200 * 480


def test_add_business_minutes_beyond_max_days():
    with pytest.raises(ValueError):
        add_business_minutes(at(MON, 8), 400 * 480)


# --- business_minutes_between ---------------------------------------------------------------------

@pytest.mark.parametrize("start,end,expected", [
    (at(MON, 9), at(MON, 9), 0),
    (at(MON, 9), at(MON, 9, 1), 1),
    (at(MON, 9), at(MON, 10), 60),
    (at(MON, 8), at(MON, 16), 480),
    (at(MON, 7), at(MON, 9), 60),
    (at(MON, 15), at(MON, 17), 60),
    (at(MON, 16), at(MON, 18), 0),
    (at(MON, 6), at(MON, 7), 0),
    (at(MON, 15), at(TUE, 9), 120),
    (at(MON, 8), at(TUE, 8), 480),
    (at(FRI, 15), at(MON + timedelta(days=7), 9), 120),
    (at(SAT, 0), at(SUN, 23, 59), 0),
    (at(MON, 8), at(MON + timedelta(days=7), 8), 2400),
    (at(MON, 9, 0, 59), at(MON, 9, 1, 1), 1),     # seconds ignored on both ends
    (at(MON, 15, 59), at(MON, 16), 1),
    (at(MON, 8), at(MON, 8, 1), 1),
])
def test_business_minutes_between(start, end, expected):
    assert business_minutes_between(start, end) == expected


def test_business_minutes_between_rejects_reversed():
    with pytest.raises(ValueError):
        business_minutes_between(at(MON, 10), at(MON, 9))
    with pytest.raises(ValueError):
        business_minutes_between(at(TUE, 9), at(MON, 9))


def test_business_minutes_between_max_days():
    start = at(MON, 9)
    assert business_minutes_between(start, start + timedelta(days=366)) > 0
    with pytest.raises(ValueError):
        business_minutes_between(start, start + timedelta(days=367))


@pytest.mark.parametrize("start", [at(MON, 9), at(MON, 6), at(FRI, 15, 30), at(SAT, 11), at(WED, 16)])
@pytest.mark.parametrize("minutes", [0, 1, 59, 480, 481, 1000, 2401])
def test_round_trip(start, minutes):
    assert business_minutes_between(start, add_business_minutes(start, minutes)) == minutes


# --- escalation_tier -------------------------------------------------------------------------------

@pytest.mark.parametrize("priority,breached,reopens,expected", [
    ("P1", False, 0, 1), ("P2", False, 0, 1), ("P3", False, 0, 0), ("P4", False, 0, 0),
    ("P1", True, 0, 3), ("P2", True, 0, 2), ("P3", True, 0, 1), ("P4", True, 0, 1),
    ("P1", False, 1, 1), ("P1", False, 2, 2), ("P2", False, 2, 2), ("P3", False, 2, 1), ("P4", False, 3, 1),
    ("P3", False, 1, 0), ("P4", True, 2, 2), ("P2", True, 2, 3), ("P1", True, 2, 3), ("P1", True, 5, 3),
    ("P3", True, 2, 2), ("P2", True, 1, 2),
])
def test_escalation_tier(priority, breached, reopens, expected):
    assert escalation_tier(priority, breached, reopens) == expected


@pytest.mark.parametrize("priority,reopens", [("P5", 0), ("p1", 0), ("", 0), ("P1", -1), ("P3", -5)])
def test_escalation_rejects(priority, reopens):
    with pytest.raises(ValueError):
        escalation_tier(priority, False, reopens)


# --- parse_duration --------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("90m", 90), ("4h", 240), ("1h30m", 90), ("2d", 2880), ("1d4h", 1680), ("1d0h5m", 1445),
    ("1h59m", 119), ("60m", 60), ("0h60m", 60), ("1m", 1), ("1h", 60), ("1d", 1440), ("1d1m", 1441),
    ("  90m  ", 90), ("\t2h\n", 120), ("0d0h1m", 1), ("10h", 600), ("100m", 100), ("1d59m", 1499),
    ("0d1h", 60), ("2d3h4m", 3064),
])
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", [
    "", "   ", "0m", "0h", "0d", "0d0h0m", "1.5h", "30m1h", "-5m", "1 h", "1h60m", "1d60m", "1H", "1M", "h", "m",
    "1h 30m", "abc", "5", "1h1h", "1d0h60m", "1x",
])
def test_parse_duration_rejects(text):
    with pytest.raises(ValueError):
        parse_duration(text)

