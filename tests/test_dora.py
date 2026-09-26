# ai-generated: 80% - Claude Code wrote the tests from my list of cases
"""Lab 2: POST /dora/metrics on small synthetic logs (METRIC-SPEC.md) and GET /dora/ticket-events ordering.

Every expected number below is worked out by hand from the rules cited next to it.
"""

import random
from datetime import datetime

from svc import act, call, create

WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}  # 21 days


def commit(eid, at, sha, change_id=None, reverts=None, branch="main"):
    return {"event_id": eid, "type": "commit", "at": at, "sha": sha, "branch": branch,
            "change_id": change_id, "reverts": reverts}


def deployment(eid, at, dep_id, commits, outcome="success", environment="production", unplanned=False,
               caused_by=None):
    return {"event_id": eid, "type": "deployment", "at": at, "deployment_id": dep_id, "environment": environment,
            "outcome": outcome, "commits": commits, "unplanned": unplanned, "caused_by": caused_by}


def incident(eid, at, inc_id, phase, deployments):
    return {"event_id": eid, "type": "incident", "at": at, "incident_id": inc_id, "phase": phase,
            "deployments": deployments}


def metrics(events, window=WINDOW):
    status, body = call("POST", "/dora/metrics", {"window": window, "events": events})
    assert status == 200, (status, body)
    return body


# --- the six edge cases ------------------------------------------------------------------------

def e1_log():
    return [
        commit("e1-c1", "2026-09-02T12:00:00Z", "e1-s1", "E1-A"),   # after its deployment: skew, -7200 s
        commit("e1-c2", "2026-09-02T09:00:00Z", "e1-s2", "E1-B"),   # +3600 s
        deployment("e1-d1", "2026-09-02T10:00:00Z", "E1-DEP-1", ["e1-s1", "e1-s2"]),
    ]


def test_e1_negative_lead_time_is_clamped_and_counted():
    m = metrics(e1_log())
    assert m["anomalies"]["negative_lead_time_pairs"] == 1
    assert m["counts"]["lead_time_pairs"] == 2
    # median of [0, 3600]; discarding would give 3600, not clamping would give -1800 (R-08, R-03)
    assert m["change_lead_time_seconds_p50"] == 1800


def e2_log():
    return [
        commit("e2-c1", "2026-09-01T10:00:00Z", "e2-s1", "E2-A"),
        commit("e2-c2", "2026-09-02T10:00:00Z", "e2-s2", reverts="e2-s1"),
        commit("e2-c3", "2026-09-03T10:00:00Z", "e2-s3", reverts="e2-s2"),   # revert of a revert
        deployment("e2-d1", "2026-09-03T12:00:00Z", "E2-DEP-1", ["e2-s1", "e2-s2", "e2-s3"]),
    ]


def test_e2_revert_chain_resolves_to_one_change():
    m = metrics(e2_log())
    assert m["anomalies"]["revert_chains_collapsed"] == 2
    assert m["counts"]["changes"] == 1                       # one change, not three (R-06)
    assert m["ground_truth"]["changes_delivered"] == 1
    assert m["ground_truth"]["true_change_lead_time_seconds_p50"] == 2 * 86400 + 7200   # from e2-c1 (R-07)
    assert m["counts"]["lead_time_pairs"] == 3


def e3_log():
    return [
        commit("e3-c1", "2026-09-05T10:00:00Z", "e3-s1", "E3-H", branch="hotfix/login"),
        commit("e3-c2", "2026-09-05T10:00:00Z", "e3-s2", "E3-F", branch="feature/x"),
        commit("e3-c3", "2026-09-05T10:00:00Z", "e3-s3", "E3-M"),
        commit("e3-c4", "2026-09-05T10:00:00Z", "e3-s4", "E3-S", branch="staging-only"),
        deployment("e3-d1", "2026-09-05T11:00:00Z", "E3-DEP-1", ["e3-s1"]),
        deployment("e3-d2", "2026-09-05T12:00:00Z", "E3-DEP-2", ["e3-s2", "e3-s3"], outcome="failure"),
        deployment("e3-d3", "2026-09-05T13:00:00Z", "E3-DEP-3", ["e3-s4"], environment="staging"),
    ]


def test_e3_off_main_commits_counted_and_still_paired():
    m = metrics(e3_log())
    # hotfix (success) and feature (failed deployment) count; the staging-only commit does not (R-01)
    assert m["anomalies"]["commits_never_on_main"] == 2
    assert m["counts"]["lead_time_pairs"] == 1                # the hotfix still pairs: branch ignored (R-09)
    assert m["change_lead_time_seconds_p50"] == 3600


def test_e4_deployment_without_commits_still_counts():
    m = metrics([
        commit("e4-c1", "2026-09-04T09:00:00Z", "e4-s1", "E4-A"),
        deployment("e4-d1", "2026-09-04T10:00:00Z", "E4-DEP-1", ["e4-s1"]),
        deployment("e4-d2", "2026-09-04T11:00:00Z", "E4-DEP-2", []),
    ])
    assert m["anomalies"]["deployments_without_commits"] == 1
    assert m["counts"]["deployments"] == 2                    # in frequency and both denominators (R-10)
    assert m["deployment_frequency_per_day"] == 0.095238      # 2 / 21
    assert m["change_fail_rate"] == 0.0
    assert m["counts"]["lead_time_pairs"] == 1
    assert m["change_lead_time_seconds_p50"] == 3600


def e5_log():
    return [
        deployment("e5-d0", "2026-09-06T09:00:00Z", "E5-DEP-0", []),
        deployment("e5-d1", "2026-09-06T10:00:00Z", "E5-DEP-1", [], outcome="failure"),   # incident never resolves
        deployment("e5-d2", "2026-09-07T10:00:00Z", "E5-DEP-2", [], outcome="failure"),   # no incident at all
        deployment("e5-d3", "2026-09-08T10:00:00Z", "E5-DEP-3", [], outcome="failure"),   # recovered in 1 h
        incident("e5-i1", "2026-09-06T10:10:00Z", "E5-INC-1", "opened", ["E5-DEP-1"]),
        incident("e5-i2", "2026-09-08T10:05:00Z", "E5-INC-2", "opened", ["E5-DEP-3"]),
        incident("e5-i3", "2026-09-08T11:00:00Z", "E5-INC-2", "resolved", ["E5-DEP-3"]),
    ]


def test_e5_open_failures_excluded_from_recovery_but_counted_in_fail_rate():
    m = metrics(e5_log())
    assert m["counts"]["open_failures"] == 2
    assert m["counts"]["recovered_failures"] == 1
    assert m["failed_deployment_recovery_time_seconds_p50"] == 3600
    assert m["change_fail_rate"] == 0.75                      # 3 / 4, open failures included (R-14)


def e6_log():
    return [
        deployment("e6-d1", "2026-09-10T10:00:00Z", "E6-DEP-1", [], outcome="failure"),
        deployment("e6-d2", "2026-09-10T11:00:00Z", "E6-DEP-2", [], outcome="failure"),
        # INC-1 covers both; INC-2 also names DEP-2 but opened later, so it is not DEP-2's covering incident
        incident("e6-i1", "2026-09-10T10:05:00Z", "E6-INC-1", "opened", ["E6-DEP-1", "E6-DEP-2"]),
        incident("e6-i2", "2026-09-10T11:30:00Z", "E6-INC-2", "opened", ["E6-DEP-2"]),
        incident("e6-i3", "2026-09-10T12:00:00Z", "E6-INC-2", "resolved", ["E6-DEP-2"]),
        incident("e6-i4", "2026-09-10T13:00:00Z", "E6-INC-1", "resolved", ["E6-DEP-1", "E6-DEP-2"]),
        # INC-3 opens exactly when INC-1 ends: half-open intervals touch, they do not intersect
        incident("e6-i5", "2026-09-10T13:00:00Z", "E6-INC-3", "opened", []),
        incident("e6-i6", "2026-09-10T14:00:00Z", "E6-INC-3", "resolved", []),
    ]


def test_e6_overlapping_incidents_per_deployment_recovery():
    m = metrics(e6_log())
    assert m["anomalies"]["overlapping_incident_pairs"] == 1
    assert m["counts"]["recovered_failures"] == 2
    # DEP-1: 13:00 - 10:00 = 10800; DEP-2: 13:00 - 11:00 = 7200 (not INC-2's 12:00); median 9000 (R-13)
    assert m["failed_deployment_recovery_time_seconds_p50"] == 9000


# --- empty log and rejections ------------------------------------------------------------------

def test_empty_log():
    m = metrics([])
    assert m["spec_version"] == "1.0.0"
    assert m["deployment_frequency_per_day"] == 0.0
    for key in ("change_lead_time_seconds_p50", "failed_deployment_recovery_time_seconds_p50",
                "change_fail_rate", "deployment_rework_rate"):
        assert m[key] is None, key
    assert all(v == 0 for v in m["counts"].values()), m["counts"]
    assert all(v == 0 for v in m["anomalies"].values()), m["anomalies"]


def test_missing_window_rejected():
    status, body = call("POST", "/dora/metrics", {"events": []})
    assert status in (400, 422) and isinstance(body, dict) and "error" in body, (status, body)


def test_empty_window_rejected():
    status, body = call("POST", "/dora/metrics", {"window": {"from": WINDOW["to"], "to": WINDOW["to"]}, "events": []})
    assert status in (400, 422) and "error" in body, (status, body)


def test_events_missing_or_not_an_array_rejected():
    for body in ({"window": WINDOW}, {"window": WINDOW, "events": {"a": 1}}):
        status, resp = call("POST", "/dora/metrics", body)
        assert status in (400, 422) and "error" in resp, (body, status, resp)


def test_reverts_unknown_sha_rejected():
    status, body = call("POST", "/dora/metrics", {"window": WINDOW, "events": [
        commit("bad-c1", "2026-09-02T10:00:00Z", "bad-s1", reverts="no-such-sha")]})
    assert status in (400, 422) and "error" in body, (status, body)


# --- determinism -------------------------------------------------------------------------------

def rich_log():
    return e1_log() + e2_log() + e3_log() + e5_log() + e6_log()


def test_order_independence():
    events = rich_log()
    shuffled = events[:]
    random.Random(2026).shuffle(shuffled)
    base = metrics(events)
    assert metrics(events[::-1]) == base
    assert metrics(shuffled) == base


def test_duplicate_event_id_ingested_once():
    events = rich_log()
    base = metrics(events)
    assert metrics(events + events) == base
    # a later duplicate that differs, even a malformed one, is ignored: the first occurrence wins (R-05)
    flipped = [dict(ev, outcome="failure") if ev["type"] == "deployment" else ev for ev in events]
    assert metrics(events + flipped) == base
    assert metrics(events + [{"event_id": events[0]["event_id"], "type": "nonsense"}]) == base


# --- window, scope and rounding ----------------------------------------------------------------

def test_window_echo_scope_and_half_open_window():
    m = metrics([
        deployment("w-d1", "2026-09-01T00:00:00Z", "W-DEP-1", []),                          # at from: in
        deployment("w-d2", "2026-09-22T00:00:00Z", "W-DEP-2", []),                          # at to: out
        deployment("w-d3", "2026-09-10T00:00:00Z", "W-DEP-3", [], environment="staging"),   # not production
    ], window={"from": "2026-09-01T02:00:00+02:00", "to": "2026-09-22T00:00:00Z"})
    assert m["window"] == {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}
    assert m["counts"]["deployments"] == 1


def test_rounding_is_half_up():
    events = [
        commit("r-c1", "2026-09-03T09:59:58Z", "r-s1", "R-A"),                     # pair 2 s
        commit("r-c2", "2026-09-03T09:59:57Z", "r-s2", "R-B"),                     # pair 3 s
        deployment("r-d1", "2026-09-03T10:00:00Z", "R-DEP-1", ["r-s1", "r-s2"]),
        deployment("r-d2", "2026-09-04T10:00:00Z", "R-DEP-2", [], outcome="failure"),
    ] + [deployment(f"r-d{i}", f"2026-09-0{i}T10:00:00Z", f"R-DEP-{i}", []) for i in range(3, 7)]
    m = metrics(events)
    assert m["change_lead_time_seconds_p50"] == 3        # 2.5 rounds half-up, not to even
    assert m["change_fail_rate"] == 0.166667             # 1 / 6
    assert m["deployment_frequency_per_day"] == 0.285714  # 6 / 21


# --- GET /dora/ticket-events -------------------------------------------------------------------

def test_ticket_events_ordering_and_phases():
    resolved = create(1, 1, "2026-10-14T10:00:00Z")
    new = create(3, 3, "2026-10-14T09:30:00Z")
    acked = create(2, 2, "2026-10-14T12:05:00+02:00")
    act(acked["id"], "ack", "2026-10-14T10:20:00Z")
    act(resolved["id"], "ack", "2026-10-14T10:10:00Z")
    act(resolved["id"], "start", "2026-10-14T10:15:00Z")
    act(resolved["id"], "resolve", "2026-10-14T11:00:00Z")

    status, stream = call("GET", "/dora/ticket-events")
    assert status == 200 and isinstance(stream, list)
    keys = [(datetime.fromisoformat(e["at"]), e["ticket_id"]) for e in stream]
    assert keys == sorted(keys)

    def phases(ticket):
        return [(e["phase"], e["state"]) for e in stream if e["ticket_id"] == ticket["id"]]

    assert phases(new) == [("created", "new")]
    assert phases(acked) == [("created", "new"), ("acknowledged", "acknowledged")]
    assert phases(resolved) == [("created", "new"), ("acknowledged", "acknowledged"), ("resolved", "resolved")]
    created = next(e for e in stream if e["ticket_id"] == acked["id"])
    assert created["at"] == "2026-10-14T10:05:00Z" and created["priority"] == acked["priority"]
