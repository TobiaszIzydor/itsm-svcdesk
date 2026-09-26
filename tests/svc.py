# ai-generated: 80% - Claude Code wrote the tests from my list of cases
"""HTTP helpers shared by the test modules: standard library only, base URL from SVCDESK_URL."""

import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("SVCDESK_URL", "http://svcdesk:8080").rstrip("/")


def call(method, path, body=None, clock=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if clock is not None:
        req.add_header("X-Test-Clock", clock)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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
    assert status == 201, f"fixture create failed: {status} {ticket}"
    return ticket


def act(ticket_id, action, clock):
    """A transition the test relies on as setup: it must succeed."""
    status, ticket = call("POST", f"/tickets/{ticket_id}/{action}", clock=clock)
    assert status == 200, f"setup {action} failed: {status} {ticket}"
    return ticket
