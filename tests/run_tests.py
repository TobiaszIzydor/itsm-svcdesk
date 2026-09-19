# ai-generated: 95% - Claude Code wrote the suite from API.md and CHECKS.md; the student reviewed the vectors
"""svcdesk own tests (Stretch S3): standard library only, driven by SVCDESK_URL.

Prints one line per assertion and, as its last line, "ITSMLAB-TESTS: passed=<n> failed=<m>".
Exit code 0 only when nothing failed.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("SVCDESK_URL", "http://svcdesk:8080").rstrip("/")

T1 = "2026-10-14T10:00:00Z"
T2 = "2026-10-16T13:30:00Z"

# id, priority, created_at, expected ack due, expected resolve due (C1 = wallclock: P1 wall-clock, others business)
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

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


def call(method, path, body=None, clock=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if clock is not None:
        req.add_header("X-Test-Clock", clock)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, json.loads(raw)
        except ValueError:
            return err.code, raw.decode(errors="replace")


def ticket_body(impact, urgency, vip=False, **extra):
    body = {
        "title": "Printer on floor 2 is down",
        "description": "Nobody on the floor can print.",
        "reporter": {"name": "Anna Nowak", "email": "anna.nowak@example.com", "vip": vip},
        "impact": impact,
        "urgency": urgency,
    }
    body.update(extra)
    return body


def create(impact, urgency, clock, vip=False, **extra):
    status, ticket = call("POST", "/tickets", ticket_body(impact, urgency, vip, **extra), clock)
    if status != 201:
        raise RuntimeError(f"fixture create failed: {status} {ticket}")
    return ticket


def wait_for_health(seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            status, body = call("GET", "/health")
            if status == 200:
                return body
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    raise RuntimeError("service did not become healthy")


def main():
    health = wait_for_health()
    check("health body", health.get("status") == "ok" and health.get("service") == "svcdesk", health)

    # --- errors carry a top-level "error" object
    status, body = call("GET", "/no-such-route-1234")
    check("unknown route 404 with error object", status == 404 and isinstance(body, dict) and "error" in body, (status, body))
    status, body = call("GET", "/tickets/does-not-exist")
    check("unknown ticket 404 with error object", status == 404 and "error" in body, (status, body))
    status, body = call("POST", "/tickets", {k: v for k, v in ticket_body(1, 1).items() if k != "title"}, T1)
    check("missing title 400/422 with error object", status in (400, 422) and "error" in body, (status, body))
    status, body = call("POST", "/tickets", ticket_body(5, 1), T1)
    check("impact 5 rejected", status in (400, 422) and "error" in body, (status, body))
    status, body = call("POST", "/tickets", ticket_body(1, "high"), T1)
    check("urgency 'high' rejected", status in (400, 422) and "error" in body, (status, body))
    status, body = call("POST", "/tickets", ticket_body(1, 1, title="x" * 201), T1)
    check("201-character title rejected", status in (400, 422) and "error" in body, (status, body))
    status, body = call("POST", "/tickets", ticket_body(1, 1), "yesterday")
    check("malformed clock rejected", status in (400, 422) and "error" in body, (status, body))
    status, body = call("POST", "/tickets", ticket_body(1, 1), "2026-10-14T10:00:00")
    check("naive clock (no offset) rejected", status in (400, 422) and "error" in body, (status, body))

    # --- create, ids, clock, ignored fields
    t = create(2, 1, T1)
    check("create: state new, priority P2, created_at = clock", t["state"] == "new" and t["priority"] == "P2" and t["created_at"] == T1, t)
    check("create: worked example due instants", t["sla"] == {"ack_due_at": "2026-10-14T11:00:00Z", "resolve_due_at": "2026-10-15T10:00:00Z"}, t["sla"])
    t2 = create(2, 1, T1)
    check("distinct ids", t["id"] and t2["id"] and t["id"] != t2["id"])
    t3 = create(3, 3, T1, id="client-id", priority="P1", state="closed", bogus="field", sla={"ack_due_at": "x"})
    check("server-owned and unknown fields ignored", t3["id"] != "client-id" and t3["priority"] == "P4" and t3["state"] == "new", t3)

    # --- priority matrix and VIP (C3 = vip)
    matrix = {(1, 1): "P1", (1, 2): "P2", (1, 3): "P3", (2, 1): "P2", (2, 2): "P3", (2, 3): "P4", (3, 1): "P3", (3, 2): "P4", (3, 3): "P4"}
    for (impact, urgency), expected in matrix.items():
        got = create(impact, urgency, T1)["priority"]
        check(f"matrix ({impact},{urgency}) -> {expected}", got == expected, got)
    check("VIP (3,3) raised to P2", create(3, 3, T1, vip=True)["priority"] == "P2")
    check("VIP (2,2) raised to P2", create(2, 2, T1, vip=True)["priority"] == "P2")
    check("VIP (1,1) stays P1", create(1, 1, T1, vip=True)["priority"] == "P1")
    check("VIP (1,2) stays P2", create(1, 2, T1, vip=True)["priority"] == "P2")

    # --- read and list
    status, got = call("GET", f"/tickets/{t['id']}")
    check("GET ticket by id", status == 200 and got["id"] == t["id"] and got["title"] == t["title"], (status, got))
    p1 = create(1, 1, T1)
    p4 = create(3, 3, T1)
    status, listed = call("GET", "/tickets?priority=P1")
    ids = {x["id"] for x in listed}
    check("list filter priority=P1", status == 200 and p1["id"] in ids and p4["id"] not in ids)
    status, listed = call("GET", "/tickets?state=new")
    check("list filter state=new", status == 200 and p4["id"] in {x["id"] for x in listed})

    # --- SLA test vectors (C1 = wallclock)
    for vid, impact, urgency, created, ack_due, resolve_due in VECTORS:
        v = create(impact, urgency, created)
        check(f"{vid} ack_due_at", v["sla"]["ack_due_at"] == ack_due, f"got {v['sla']['ack_due_at']} expected {ack_due}")
        check(f"{vid} resolve_due_at", v["sla"]["resolve_due_at"] == resolve_due, f"got {v['sla']['resolve_due_at']} expected {resolve_due}")

    # --- state machine
    s = create(1, 1, T1)
    check("start on new 409", call("POST", f"/tickets/{s['id']}/start", clock=T1)[0] == 409)
    check("resolve on new 409", call("POST", f"/tickets/{s['id']}/resolve", clock=T1)[0] == 409)
    check("close on new 409", call("POST", f"/tickets/{s['id']}/close", clock=T1)[0] == 409)
    check("reopen on new 409", call("POST", f"/tickets/{s['id']}/reopen", clock=T1)[0] == 409)
    status, s = call("POST", f"/tickets/{s['id']}/ack", clock="2026-10-14T10:05:00Z")
    check("ack new -> acknowledged", status == 200 and s["state"] == "acknowledged" and s["acknowledged_at"] == "2026-10-14T10:05:00Z", (status, s))
    status, body = call("POST", f"/tickets/{s['id']}/ack", clock="2026-10-14T10:06:00Z")
    check("ack twice 409 with error object", status == 409 and "error" in body, (status, body))
    status, body = call("POST", f"/tickets/{s['id']}/resolve", clock="2026-10-14T10:06:00Z")
    check("resolve from acknowledged 409", status == 409 and "error" in body, (status, body))
    status, s = call("POST", f"/tickets/{s['id']}/start", clock="2026-10-14T10:10:00Z")
    check("start acknowledged -> in_progress", status == 200 and s["state"] == "in_progress", (status, s))
    check("close from in_progress 409", call("POST", f"/tickets/{s['id']}/close", clock="2026-10-14T10:11:00Z")[0] == 409)
    status, s = call("POST", f"/tickets/{s['id']}/resolve", clock="2026-10-14T11:00:00Z")
    check("resolve in_progress -> resolved", status == 200 and s["state"] == "resolved" and s["resolved_at"] == "2026-10-14T11:00:00Z", (status, s))
    resolve_due_before = s["sla"]["resolve_due_at"]
    status, r = call("POST", f"/tickets/{s['id']}/reopen", clock="2026-10-20T11:00:00Z")
    check("reopen resolved after 6 days -> in_progress", status == 200 and r["state"] == "in_progress", (status, r))
    check("reopen clears resolved_at and closed_at", r["resolved_at"] is None and r["closed_at"] is None, r)
    check("reopen keeps resolve_due_at", r["sla"]["resolve_due_at"] == resolve_due_before, r["sla"])
    status, s = call("POST", f"/tickets/{s['id']}/resolve", clock="2026-10-14T11:00:00Z")
    check("resolve again after reopen (earlier clock accepted)", status == 200 and s["state"] == "resolved", (status, s))
    status, body = call("POST", f"/tickets/{s['id']}/reopen", clock="2026-10-21T11:00:01Z")
    check("reopen resolved after 7 days + 1 s 409", status == 409 and "error" in body, (status, body))
    status, s = call("POST", f"/tickets/{s['id']}/close", clock="2026-10-14T12:00:00Z")
    check("close resolved -> closed", status == 200 and s["state"] == "closed" and s["closed_at"] == "2026-10-14T12:00:00Z", (status, s))
    status, body = call("POST", f"/tickets/{s['id']}/reopen", clock="2026-10-15T12:00:00Z")
    check("reopen closed after 1 day 409 (C2 = immutable)", status == 409 and "error" in body, (status, body))
    check("action on unknown id 404", call("POST", "/tickets/does-not-exist/ack", clock=T1)[0] == 404)

    # --- breach and pause flags on a T2 ticket (P3: ack due Mon 09:30Z, resolve due Wed 13:30Z)
    shared = create(1, 3, T2)
    status, sla = call("GET", f"/tickets/{shared['id']}/sla", clock="2026-10-19T09:31:00Z")
    check("ack breached after due, resolve not", status == 200 and sla["ack_breached"] is True and sla["resolve_breached"] is False, sla)
    status, sla = call("GET", f"/tickets/{shared['id']}/sla", clock="2026-10-19T09:00:00Z")
    check("ack not breached before due", sla["ack_breached"] is False, sla)
    status, sla = call("GET", f"/tickets/{shared['id']}/sla", clock="2026-10-19T09:30:00Z")
    check("ack at exactly due is not a breach", sla["ack_breached"] is False, sla)
    status, sla = call("GET", f"/tickets/{shared['id']}/sla", clock="2026-10-17T10:00:00Z")
    check("paused on Saturday", sla["paused"] is True, sla)
    status, sla = call("GET", f"/tickets/{shared['id']}/sla", clock="2026-10-19T09:00:00Z")
    check("not paused on Monday morning", sla["paused"] is False, sla)
    status, sla = call("GET", f"/tickets/{shared['id']}/sla", clock="2026-10-21T13:30:01Z")
    check("resolve breached after due while unresolved", sla["resolve_breached"] is True, sla)
    check("sla block fields", sla["priority"] == "P3" and sla["ack_due_at"] == "2026-10-19T09:30:00Z" and sla["resolve_due_at"] == "2026-10-21T13:30:00Z", sla)

    fresh = create(1, 3, T2)
    call("POST", f"/tickets/{fresh['id']}/ack", clock="2026-10-16T13:45:00Z")
    status, sla = call("GET", f"/tickets/{fresh['id']}/sla", clock="2026-10-19T12:00:00Z")
    check("ack in time is not breached later", sla["ack_breached"] is False, sla)
    call("POST", f"/tickets/{fresh['id']}/start", clock="2026-10-16T13:50:00Z")
    call("POST", f"/tickets/{fresh['id']}/resolve", clock="2026-10-16T14:00:00Z")
    status, sla = call("GET", f"/tickets/{fresh['id']}/sla", clock="2026-10-17T10:00:00Z")
    check("resolved ticket is not paused on Saturday", sla["paused"] is False and sla["resolve_breached"] is False, sla)

    wall = create(1, 1, "2026-10-16T15:00:00Z")  # T3: P1, wall-clock under C1 = wallclock
    status, sla = call("GET", f"/tickets/{wall['id']}/sla", clock="2026-10-17T10:00:00Z")
    check("P1 wall-clock ticket never paused", sla["paused"] is False, sla)
    check("P1 wall-clock ticket breached on Saturday", sla["ack_breached"] is True and sla["resolve_breached"] is True, sla)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # a fixture failure is a failed run, still with the summary line
        failed += 1
        print(f"FAIL suite aborted: {exc}")
    print(f"ITSMLAB-TESTS: passed={passed} failed={failed}")
    sys.exit(0 if failed == 0 else 1)
