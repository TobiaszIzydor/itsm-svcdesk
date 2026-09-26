# ai-generated: 80% - Claude Code wrote the tests from my list of cases
"""Lab 1 checks, ported one-to-one from the former custom runner (same HTTP calls, same assertions).

The state-machine and SLA checks used to share one ticket in sequence; each test now replays the same
history on its own ticket, so a failure is reported alone and does not cascade.
"""

import pytest

from svc import act, call, create, ticket_body

T1 = "2026-10-14T10:00:00Z"
T2 = "2026-10-16T13:30:00Z"

# id, impact, urgency, created_at, expected ack due, expected resolve due (C1 = wallclock)
VECTORS = [
    ("T1", 1, 1, "2026-10-14T10:00:00Z", "2026-10-14T10:15:00Z", "2026-10-14T14:00:00Z"),
    ("T2", 1, 3, "2026-10-16T13:30:00Z", "2026-10-19T09:30:00Z", "2026-10-21T13:30:00Z"),
    ("T3", 1, 1, "2026-10-16T15:00:00Z", "2026-10-16T15:15:00Z", "2026-10-16T19:00:00Z"),
    ("T4", 1, 2, "2026-10-17T10:00:00Z", "2026-10-19T07:00:00Z", "2026-10-19T14:00:00Z"),
    ("T5", 3, 3, "2027-01-14T14:30:00Z", "2027-01-15T14:30:00Z", "2027-01-27T14:30:00Z"),
    ("T6", 1, 1, "2027-01-15T15:50:00Z", "2027-01-15T16:05:00Z", "2027-01-15T19:50:00Z"),
    ("T7", 1, 2, "2026-10-14T10:00:00Z", "2026-10-14T11:00:00Z", "2026-10-15T10:00:00Z"),
    ("T8", 1, 3, "2026-10-23T13:00:00Z", "2026-10-26T10:00:00Z", "2026-10-28T14:00:00Z"),
]

MATRIX = {(1, 1): "P1", (1, 2): "P2", (1, 3): "P3", (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
          (3, 1): "P3", (3, 2): "P4", (3, 3): "P4"}


# --- health and error shape ----------------------------------------------------------------------

def test_health_body():
    status, health = call("GET", "/health")
    assert status == 200 and health.get("status") == "ok" and health.get("service") == "svcdesk", health


def test_unknown_route_404_with_error_object():
    status, body = call("GET", "/no-such-route-1234")
    assert status == 404 and isinstance(body, dict) and "error" in body, (status, body)


def test_unknown_ticket_404_with_error_object():
    status, body = call("GET", "/tickets/does-not-exist")
    assert status == 404 and "error" in body, (status, body)


@pytest.mark.parametrize("body, clock", [
    pytest.param({k: v for k, v in ticket_body(1, 1).items() if k != "title"}, T1, id="missing title"),
    pytest.param(ticket_body(5, 1), T1, id="impact 5"),
    pytest.param(ticket_body(1, "high"), T1, id="urgency 'high'"),
    pytest.param(ticket_body(1, 1, title="x" * 201), T1, id="201-character title"),
    pytest.param(ticket_body(1, 1), "yesterday", id="malformed clock"),
    pytest.param(ticket_body(1, 1), "2026-10-14T10:00:00", id="naive clock (no offset)"),
])
def test_bad_create_rejected_with_error_object(body, clock):
    status, resp = call("POST", "/tickets", body, clock)
    assert status in (400, 422) and "error" in resp, (status, resp)


# --- create, ids, clock, ignored fields ----------------------------------------------------------

def test_create_state_priority_and_clock():
    t = create(2, 1, T1)
    assert t["state"] == "new" and t["priority"] == "P2" and t["created_at"] == T1, t


def test_create_worked_example_due_instants():
    t = create(2, 1, T1)
    assert t["sla"] == {"ack_due_at": "2026-10-14T11:00:00Z", "resolve_due_at": "2026-10-15T10:00:00Z"}, t["sla"]


def test_distinct_ids():
    t, t2 = create(2, 1, T1), create(2, 1, T1)
    assert t["id"] and t2["id"] and t["id"] != t2["id"]


def test_server_owned_and_unknown_fields_ignored():
    t3 = create(3, 3, T1, id="client-id", priority="P1", state="closed", bogus="field", sla={"ack_due_at": "x"})
    assert t3["id"] != "client-id" and t3["priority"] == "P4" and t3["state"] == "new", t3


# --- priority matrix and VIP (C3 = vip) ----------------------------------------------------------

@pytest.mark.parametrize("impact, urgency, expected", [(i, u, p) for (i, u), p in MATRIX.items()],
                         ids=[f"({i},{u})->{p}" for (i, u), p in MATRIX.items()])
def test_priority_matrix(impact, urgency, expected):
    got = create(impact, urgency, T1)["priority"]
    assert got == expected


@pytest.mark.parametrize("impact, urgency, expected", [
    pytest.param(3, 3, "P2", id="VIP (3,3) raised to P2"),
    pytest.param(2, 2, "P2", id="VIP (2,2) raised to P2"),
    pytest.param(1, 1, "P1", id="VIP (1,1) stays P1"),
    pytest.param(1, 2, "P2", id="VIP (1,2) stays P2"),
])
def test_vip(impact, urgency, expected):
    assert create(impact, urgency, T1, vip=True)["priority"] == expected


# --- read and list -------------------------------------------------------------------------------

def test_get_ticket_by_id():
    t = create(2, 1, T1)
    status, got = call("GET", f"/tickets/{t['id']}")
    assert status == 200 and got["id"] == t["id"] and got["title"] == t["title"], (status, got)


def test_list_filter_priority_p1():
    p1, p4 = create(1, 1, T1), create(3, 3, T1)
    status, listed = call("GET", "/tickets?priority=P1")
    ids = {x["id"] for x in listed}
    assert status == 200 and p1["id"] in ids and p4["id"] not in ids


def test_list_filter_state_new():
    p4 = create(3, 3, T1)
    status, listed = call("GET", "/tickets?state=new")
    assert status == 200 and p4["id"] in {x["id"] for x in listed}


# --- SLA test vectors (C1 = wallclock) -----------------------------------------------------------

@pytest.mark.parametrize("field", ["ack_due_at", "resolve_due_at"])
@pytest.mark.parametrize("vid, impact, urgency, created, ack_due, resolve_due", VECTORS, ids=[v[0] for v in VECTORS])
def test_sla_vector(vid, impact, urgency, created, ack_due, resolve_due, field):
    expected = {"ack_due_at": ack_due, "resolve_due_at": resolve_due}[field]
    got = create(impact, urgency, created)["sla"][field]
    assert got == expected, f"got {got} expected {expected}"


# --- state machine -------------------------------------------------------------------------------

def resolved_ticket():
    """new -> acknowledged 10:05 -> in_progress 10:10 -> resolved 11:00 (the former runner's history)."""
    t = create(1, 1, T1)
    act(t["id"], "ack", "2026-10-14T10:05:00Z")
    act(t["id"], "start", "2026-10-14T10:10:00Z")
    return act(t["id"], "resolve", "2026-10-14T11:00:00Z")


def reresolved_ticket():
    """resolved_ticket, reopened after 6 days, then resolved again on an earlier clock."""
    t = resolved_ticket()
    act(t["id"], "reopen", "2026-10-20T11:00:00Z")
    return act(t["id"], "resolve", "2026-10-14T11:00:00Z")


@pytest.mark.parametrize("action", ["start", "resolve", "close", "reopen"])
def test_action_on_new_409(action):
    s = create(1, 1, T1)
    assert call("POST", f"/tickets/{s['id']}/{action}", clock=T1)[0] == 409


def test_ack_new_to_acknowledged():
    s = create(1, 1, T1)
    status, s = call("POST", f"/tickets/{s['id']}/ack", clock="2026-10-14T10:05:00Z")
    assert status == 200 and s["state"] == "acknowledged" and s["acknowledged_at"] == "2026-10-14T10:05:00Z", (status, s)


def test_ack_twice_409_with_error_object():
    s = create(1, 1, T1)
    act(s["id"], "ack", "2026-10-14T10:05:00Z")
    status, body = call("POST", f"/tickets/{s['id']}/ack", clock="2026-10-14T10:06:00Z")
    assert status == 409 and "error" in body, (status, body)


def test_resolve_from_acknowledged_409():
    s = create(1, 1, T1)
    act(s["id"], "ack", "2026-10-14T10:05:00Z")
    status, body = call("POST", f"/tickets/{s['id']}/resolve", clock="2026-10-14T10:06:00Z")
    assert status == 409 and "error" in body, (status, body)


def test_start_acknowledged_to_in_progress():
    s = create(1, 1, T1)
    act(s["id"], "ack", "2026-10-14T10:05:00Z")
    status, s = call("POST", f"/tickets/{s['id']}/start", clock="2026-10-14T10:10:00Z")
    assert status == 200 and s["state"] == "in_progress", (status, s)


def test_close_from_in_progress_409():
    s = create(1, 1, T1)
    act(s["id"], "ack", "2026-10-14T10:05:00Z")
    act(s["id"], "start", "2026-10-14T10:10:00Z")
    assert call("POST", f"/tickets/{s['id']}/close", clock="2026-10-14T10:11:00Z")[0] == 409


def test_resolve_in_progress_to_resolved():
    s = create(1, 1, T1)
    act(s["id"], "ack", "2026-10-14T10:05:00Z")
    act(s["id"], "start", "2026-10-14T10:10:00Z")
    status, s = call("POST", f"/tickets/{s['id']}/resolve", clock="2026-10-14T11:00:00Z")
    assert status == 200 and s["state"] == "resolved" and s["resolved_at"] == "2026-10-14T11:00:00Z", (status, s)


def test_reopen_resolved_after_6_days_to_in_progress():
    s = resolved_ticket()
    status, r = call("POST", f"/tickets/{s['id']}/reopen", clock="2026-10-20T11:00:00Z")
    assert status == 200 and r["state"] == "in_progress", (status, r)


def test_reopen_clears_resolved_at_and_closed_at():
    s = resolved_ticket()
    _, r = call("POST", f"/tickets/{s['id']}/reopen", clock="2026-10-20T11:00:00Z")
    assert r["resolved_at"] is None and r["closed_at"] is None, r


def test_reopen_keeps_resolve_due_at():
    s = resolved_ticket()
    _, r = call("POST", f"/tickets/{s['id']}/reopen", clock="2026-10-20T11:00:00Z")
    assert r["sla"]["resolve_due_at"] == s["sla"]["resolve_due_at"], r["sla"]


def test_resolve_again_after_reopen_earlier_clock_accepted():
    s = resolved_ticket()
    act(s["id"], "reopen", "2026-10-20T11:00:00Z")
    status, s = call("POST", f"/tickets/{s['id']}/resolve", clock="2026-10-14T11:00:00Z")
    assert status == 200 and s["state"] == "resolved", (status, s)


def test_reopen_resolved_after_7_days_plus_1s_409():
    s = reresolved_ticket()
    status, body = call("POST", f"/tickets/{s['id']}/reopen", clock="2026-10-21T11:00:01Z")
    assert status == 409 and "error" in body, (status, body)


def test_close_resolved_to_closed():
    s = reresolved_ticket()
    status, s = call("POST", f"/tickets/{s['id']}/close", clock="2026-10-14T12:00:00Z")
    assert status == 200 and s["state"] == "closed" and s["closed_at"] == "2026-10-14T12:00:00Z", (status, s)


def test_reopen_closed_after_1_day_409_c2_immutable():
    s = reresolved_ticket()
    act(s["id"], "close", "2026-10-14T12:00:00Z")
    status, body = call("POST", f"/tickets/{s['id']}/reopen", clock="2026-10-15T12:00:00Z")
    assert status == 409 and "error" in body, (status, body)


def test_action_on_unknown_id_404():
    assert call("POST", "/tickets/does-not-exist/ack", clock=T1)[0] == 404


# --- breach and pause flags on a T2 ticket (P3: ack due Mon 09:30Z, resolve due Wed 13:30Z) -------

def sla_at(clock):
    shared = create(1, 3, T2)
    status, sla = call("GET", f"/tickets/{shared['id']}/sla", clock=clock)
    assert status == 200, (status, sla)
    return sla


def test_ack_breached_after_due_resolve_not():
    sla = sla_at("2026-10-19T09:31:00Z")
    assert sla["ack_breached"] is True and sla["resolve_breached"] is False, sla


def test_ack_not_breached_before_due():
    sla = sla_at("2026-10-19T09:00:00Z")
    assert sla["ack_breached"] is False, sla


def test_ack_at_exactly_due_is_not_a_breach():
    sla = sla_at("2026-10-19T09:30:00Z")
    assert sla["ack_breached"] is False, sla


def test_paused_on_saturday():
    sla = sla_at("2026-10-17T10:00:00Z")
    assert sla["paused"] is True, sla


def test_not_paused_on_monday_morning():
    sla = sla_at("2026-10-19T09:00:00Z")
    assert sla["paused"] is False, sla


def test_resolve_breached_after_due_while_unresolved():
    sla = sla_at("2026-10-21T13:30:01Z")
    assert sla["resolve_breached"] is True, sla


def test_sla_block_fields():
    sla = sla_at("2026-10-21T13:30:01Z")
    assert (sla["priority"] == "P3" and sla["ack_due_at"] == "2026-10-19T09:30:00Z"
            and sla["resolve_due_at"] == "2026-10-21T13:30:00Z"), sla


def test_ack_in_time_is_not_breached_later():
    fresh = create(1, 3, T2)
    call("POST", f"/tickets/{fresh['id']}/ack", clock="2026-10-16T13:45:00Z")
    status, sla = call("GET", f"/tickets/{fresh['id']}/sla", clock="2026-10-19T12:00:00Z")
    assert sla["ack_breached"] is False, sla


def test_resolved_ticket_is_not_paused_on_saturday():
    fresh = create(1, 3, T2)
    call("POST", f"/tickets/{fresh['id']}/ack", clock="2026-10-16T13:45:00Z")
    call("POST", f"/tickets/{fresh['id']}/start", clock="2026-10-16T13:50:00Z")
    call("POST", f"/tickets/{fresh['id']}/resolve", clock="2026-10-16T14:00:00Z")
    status, sla = call("GET", f"/tickets/{fresh['id']}/sla", clock="2026-10-17T10:00:00Z")
    assert sla["paused"] is False and sla["resolve_breached"] is False, sla


def wall_clock_sla():
    wall = create(1, 1, "2026-10-16T15:00:00Z")  # T3: P1, wall-clock under C1 = wallclock
    status, sla = call("GET", f"/tickets/{wall['id']}/sla", clock="2026-10-17T10:00:00Z")
    return sla


def test_p1_wall_clock_ticket_never_paused():
    sla = wall_clock_sla()
    assert sla["paused"] is False, sla


def test_p1_wall_clock_ticket_breached_on_saturday():
    sla = wall_clock_sla()
    assert sla["ack_breached"] is True and sla["resolve_breached"] is True, sla
