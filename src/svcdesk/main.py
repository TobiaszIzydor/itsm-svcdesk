# ai-generated: 95% - Claude Code wrote the service from REQUIREMENTS.md / API.md; the student chose the
# three decisions, reviewed the SLA clock against the T1..T8 vectors and the checker output.
"""svcdesk - Lab 1 service desk API (FastAPI, SQLite in a named volume)."""

# The three contradictions of REQUIREMENTS.md, resolved. These values must equal the front matter of
# DECISIONS.md; the checker compares the declared values with what the running service does.
DECISIONS = {
    "C1": "wallclock",   # R-13 vs R-14: P1 targets are wall-clock, P2..P4 run on business hours
    "C2": "immutable",   # R-09 vs R-10: a closed ticket is immutable; reopen only from resolved
    "C3": "vip",         # R-05 vs R-06: a VIP ticket at P3/P4 is raised to P2
}

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.exceptions import HTTPException as StarletteHTTPException

from svcdesk.dora.router import router as dora_router

WARSAW = ZoneInfo("Europe/Warsaw")
OPENING = time(8, 0)
CLOSING = time(16, 0)
BUSINESS_DAY = timedelta(hours=8)
REOPEN_WINDOW = timedelta(days=7)

PRIORITY_MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}

SLA_TARGETS = {  # priority -> (acknowledge within, resolve within)
    "P1": (timedelta(minutes=15), timedelta(hours=4)),
    "P2": (timedelta(hours=1), timedelta(hours=8)),
    "P3": (timedelta(hours=4), timedelta(hours=24)),
    "P4": (timedelta(hours=8), timedelta(hours=72)),
}

TRANSITIONS = {  # action -> (from state, to state)
    "ack": ("new", "acknowledged"),
    "start": ("acknowledged", "in_progress"),
    "resolve": ("in_progress", "resolved"),
    "close": ("resolved", "closed"),
}


# --- time helpers -------------------------------------------------------------------------------

def to_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def fmt(dt: datetime | None) -> str | None:
    """RFC 3339 instant in UTC with a Z suffix."""
    if dt is None:
        return None
    return to_utc(dt).isoformat().replace("+00:00", "Z")


def parse_instant(value: str) -> datetime:
    """RFC 3339 instant with an offset; a naive timestamp is malformed (ValueError)."""
    text = value.strip()
    if text.endswith(("z", "Z")):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp has no offset")
    return to_utc(dt)


def test_clock_enabled() -> bool:
    return os.environ.get("SVCDESK_TEST_CLOCK", "").strip().lower() in ("1", "true")


def compute_priority(impact: int, urgency: int, vip: bool) -> str:
    priority = PRIORITY_MATRIX[(impact, urgency)]
    if DECISIONS["C3"] == "vip" and vip and priority in ("P3", "P4"):
        priority = "P2"
    return priority


def uses_business_clock(priority: str) -> bool:
    if priority == "P1":
        return DECISIONS["C1"] == "business"
    return True


def is_business_moment(local: datetime) -> bool:
    """Inside the half-open window Mon-Fri [08:00, 16:00) Europe/Warsaw (local is a Warsaw datetime)."""
    return local.weekday() < 5 and OPENING <= local.time() < CLOSING


def next_opening(local: datetime) -> datetime:
    """Move a Warsaw wall-clock moment forward to the next opening if it is outside a business window."""
    if is_business_moment(local):
        return local
    day = local.date()
    if local.weekday() < 5 and local.time() < OPENING:
        pass  # before opening today: open today
    else:
        day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return datetime.combine(day, OPENING)


def business_due(created_at: datetime, target: timedelta) -> datetime:
    """Consume `target` from consecutive business windows starting at created_at (API.md section 4).

    Arithmetic runs on naive Warsaw wall-clock time: both DST transitions fall on Sundays, outside any
    business window, so no window ever spans a transition. The result is localised and returned in UTC.
    """
    cursor = next_opening(created_at.astimezone(WARSAW).replace(tzinfo=None))
    remaining = target
    while True:
        closing = datetime.combine(cursor.date(), CLOSING)
        available = closing - cursor
        if remaining <= available:  # the tie rule: ending exactly at closing is due at 16:00 today
            due_local = cursor + remaining
            break
        remaining -= available
        cursor = next_opening(closing)
    return to_utc(due_local.replace(tzinfo=WARSAW))


def sla_due(priority: str, created_at: datetime) -> tuple[datetime, datetime]:
    ack_target, resolve_target = SLA_TARGETS[priority]
    if uses_business_clock(priority):
        return business_due(created_at, ack_target), business_due(created_at, resolve_target)
    return created_at + ack_target, created_at + resolve_target


# --- persistence --------------------------------------------------------------------------------

class Store:
    """Tickets as JSON documents in a SQLite file (SVCDESK_DB, default /data/svcdesk.db)."""

    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, doc TEXT NOT NULL)"
        )
        self._conn.commit()

    def get(self, ticket_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT doc FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, ticket: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO tickets (id, doc) VALUES (?, ?)",
                (ticket["id"], json.dumps(ticket)),
            )
            self._conn.commit()

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT doc FROM tickets").fetchall()
        return [json.loads(row[0]) for row in rows]


store = Store(os.environ.get("SVCDESK_DB", "/data/svcdesk.db"))


# --- request models -----------------------------------------------------------------------------

class ReporterIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=100)
    email: str | None = None
    vip: bool = False


class TicketIn(BaseModel):
    # extra="ignore": server-owned fields (id, priority, state, timestamps, sla) and unknown fields
    # are silently dropped, never rejected (API.md section 2).
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    reporter: ReporterIn
    impact: StrictInt = Field(ge=1, le=3)
    urgency: StrictInt = Field(ge=1, le=3)
    related_to: str | None = None


# --- app and error shape ------------------------------------------------------------------------

app = FastAPI(title="svcdesk", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(dora_router)  # Lab 2: POST /dora/metrics

STATUS_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 409: "conflict"}


def error_response(status: int, code: str, message: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, **extra}})


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ()) if part != "body"]
        details.append({"field": ".".join(loc), "message": err.get("msg", "invalid")})
    message = "; ".join(f"{d['field']}: {d['message']}" if d["field"] else d["message"] for d in details)
    return error_response(422, "validation", message or "invalid request", details=details)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        return error_response(exc.status_code, str(detail["code"]), str(detail.get("message", "")))
    return error_response(exc.status_code, STATUS_CODES.get(exc.status_code, "error"), str(detail))


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return error_response(500, "internal", f"{type(exc).__name__}: {exc}")


def request_now(x_test_clock: str | None) -> datetime:
    """The per-request clock (API.md section 8): the header when the test clock is enabled, else real UTC."""
    if x_test_clock is not None and test_clock_enabled():
        try:
            return parse_instant(x_test_clock)
        except ValueError:
            raise api_error(400, "bad_clock", "X-Test-Clock must be an RFC 3339 instant with an offset")
    return datetime.now(timezone.utc)


def load_ticket(ticket_id: str) -> dict[str, Any]:
    ticket = store.get(ticket_id)
    if ticket is None:
        raise api_error(404, "not_found", f"ticket {ticket_id} not found")
    return ticket


def stored_instant(ticket: dict[str, Any], key: str) -> datetime | None:
    value = ticket.get(key)
    return parse_instant(value) if value else None


# --- endpoints ----------------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "svcdesk"}


@app.post("/tickets", status_code=201)
def create_ticket(body: TicketIn, x_test_clock: str | None = Header(default=None)) -> dict[str, Any]:
    now = request_now(x_test_clock)
    priority = compute_priority(body.impact, body.urgency, body.reporter.vip)
    ack_due, resolve_due = sla_due(priority, now)
    ticket = {
        "id": str(uuid.uuid4()),
        "title": body.title,
        "description": body.description,
        "reporter": {"name": body.reporter.name, "email": body.reporter.email, "vip": body.reporter.vip},
        "impact": body.impact,
        "urgency": body.urgency,
        "priority": priority,
        "state": "new",
        "created_at": fmt(now),
        "acknowledged_at": None,
        "resolved_at": None,
        "closed_at": None,
        "related_to": body.related_to,
        "sla": {"ack_due_at": fmt(ack_due), "resolve_due_at": fmt(resolve_due)},
    }
    store.put(ticket)
    return ticket


@app.get("/tickets")
def list_tickets(state: str | None = None, priority: str | None = None) -> list[dict[str, Any]]:
    tickets = store.all()
    if state is not None:
        tickets = [t for t in tickets if t["state"] == state]
    if priority is not None:
        tickets = [t for t in tickets if t["priority"] == priority]
    return tickets


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict[str, Any]:
    return load_ticket(ticket_id)


@app.get("/tickets/{ticket_id}/sla")
def get_sla(ticket_id: str, x_test_clock: str | None = Header(default=None)) -> dict[str, Any]:
    now = request_now(x_test_clock)
    ticket = load_ticket(ticket_id)
    ack_due = parse_instant(ticket["sla"]["ack_due_at"])
    resolve_due = parse_instant(ticket["sla"]["resolve_due_at"])
    acknowledged_at = stored_instant(ticket, "acknowledged_at")
    resolved_at = stored_instant(ticket, "resolved_at")
    open_ticket = ticket["state"] not in ("resolved", "closed")

    # Equality is never a breach (API.md section 5).
    ack_breached = (acknowledged_at > ack_due) if acknowledged_at else (now > ack_due)
    resolve_breached = (resolved_at > resolve_due) if resolved_at else (now > resolve_due)
    paused = (
        open_ticket
        and uses_business_clock(ticket["priority"])
        and not is_business_moment(now.astimezone(WARSAW))
    )
    return {
        "priority": ticket["priority"],
        "ack_due_at": ticket["sla"]["ack_due_at"],
        "resolve_due_at": ticket["sla"]["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused,
    }


def transition(ticket_id: str, action: str, now: datetime) -> dict[str, Any]:
    ticket = load_ticket(ticket_id)
    from_state, to_state = TRANSITIONS[action]
    if ticket["state"] != from_state:
        raise api_error(
            409, "invalid_transition", f"cannot {action} a ticket in state {ticket['state']}"
        )
    ticket["state"] = to_state
    if action == "ack":
        ticket["acknowledged_at"] = fmt(now)
    elif action == "resolve":
        ticket["resolved_at"] = fmt(now)
    elif action == "close":
        ticket["closed_at"] = fmt(now)
    store.put(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/ack")
def ack_ticket(ticket_id: str, x_test_clock: str | None = Header(default=None)) -> dict[str, Any]:
    return transition(ticket_id, "ack", request_now(x_test_clock))


@app.post("/tickets/{ticket_id}/start")
def start_ticket(ticket_id: str, x_test_clock: str | None = Header(default=None)) -> dict[str, Any]:
    return transition(ticket_id, "start", request_now(x_test_clock))


@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, x_test_clock: str | None = Header(default=None)) -> dict[str, Any]:
    return transition(ticket_id, "resolve", request_now(x_test_clock))


@app.post("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, x_test_clock: str | None = Header(default=None)) -> dict[str, Any]:
    return transition(ticket_id, "close", request_now(x_test_clock))


@app.post("/tickets/{ticket_id}/reopen")
def reopen_ticket(ticket_id: str, x_test_clock: str | None = Header(default=None)) -> dict[str, Any]:
    now = request_now(x_test_clock)
    ticket = load_ticket(ticket_id)
    state = ticket["state"]
    if state == "closed":
        if DECISIONS["C2"] == "immutable":
            raise api_error(
                409, "ticket_closed", "a closed ticket is immutable; open a new ticket with related_to"
            )
        anchor = stored_instant(ticket, "closed_at")
    elif state == "resolved":
        anchor = stored_instant(ticket, "resolved_at")
    else:
        raise api_error(409, "invalid_transition", f"cannot reopen a ticket in state {state}")
    # The window is judged on this request's clock only; a clock earlier than the anchor is fine.
    if anchor is not None and now > anchor + REOPEN_WINDOW:
        raise api_error(409, "reopen_window_expired", "reopen is allowed within 7 days only")
    ticket["state"] = "in_progress"
    ticket["resolved_at"] = None
    ticket["closed_at"] = None  # resolve_due_at is never changed by a reopen
    store.put(ticket)
    return ticket
