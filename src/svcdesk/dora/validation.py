# ai-generated: 85% - Claude Code wrote the code from my design (module layout, algorithms, rounding and validation rules given in the prompt)
"""Request and event-shape validation (METRIC-SPEC.md sections 1 and 6): 400 for a non-object body, 422 otherwise."""

from datetime import datetime
from typing import Any

from svcdesk.dora.timeparse import parse_instant

EVENT_TYPES = ("commit", "deployment", "incident")
OUTCOMES = ("success", "failure")
PHASES = ("opened", "resolved")


class DoraError(Exception):
    def __init__(self, status: int, code: str, message: str, event_id: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.event_id = event_id


def _invalid(message: str, event_id: str | None = None) -> DoraError:
    return DoraError(422, "validation", message, event_id)


def _instant(value: Any, field: str, event_id: str | None = None) -> datetime:
    try:
        return parse_instant(value)
    except ValueError:
        raise _invalid(f"{field} must be an RFC 3339 instant with an offset", event_id) from None


def parse_request(body: Any) -> tuple[datetime, datetime, list[Any]]:
    """(from, to, raw events) from the request body, or DoraError."""
    if not isinstance(body, dict):
        raise DoraError(400, "bad_request", "the body must be a JSON object")
    window = body.get("window")
    if not isinstance(window, dict):
        raise _invalid("window is missing or not an object")
    frm = _instant(window.get("from"), "window.from")
    to = _instant(window.get("to"), "window.to")
    if to <= frm:
        raise _invalid("window.to must be after window.from")
    events = body.get("events")
    if not isinstance(events, list):
        raise _invalid("events is missing or not an array")
    return frm, to, events


def _is_str(x: Any) -> bool:
    return isinstance(x, str)


def _is_str_or_null(x: Any) -> bool:
    return x is None or isinstance(x, str)


def _is_str_list(x: Any) -> bool:
    return isinstance(x, list) and all(isinstance(s, str) for s in x)


def check_event_id(ev: Any, index: int) -> str:
    """The pre-dedupe check (R-05): an object with an event_id of 1..64 characters, or DoraError."""
    if not isinstance(ev, dict):
        raise _invalid(f"events[{index}] is not an object")
    event_id = ev.get("event_id")
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
        raise _invalid(f"events[{index}].event_id must be a string of 1..64 characters")
    return event_id


def check_event_shape(ev: dict[str, Any]) -> dict[str, Any]:
    """A normalized copy of one kept event (known fields only, at parsed to UTC), or DoraError.

    Runs after dedupe, so the event already passed check_event_id; a dropped duplicate is never shape-checked.
    """
    event_id = ev["event_id"]
    where = f"event {event_id}"
    kind = ev.get("type")
    if not isinstance(kind, str) or kind not in EVENT_TYPES:
        raise _invalid(f"{where}.type must be one of {', '.join(EVENT_TYPES)}", event_id)
    out: dict[str, Any] = {"event_id": event_id, "type": kind, "at": _instant(ev.get("at"), f"{where}.at", event_id)}

    def need(field: str, ok: bool, what: str) -> None:
        if not ok:
            raise _invalid(f"{where}.{field} must be {what}", event_id)
        out[field] = ev.get(field)

    if kind == "commit":
        need("sha", _is_str(ev.get("sha")), "a string")
        need("branch", _is_str(ev.get("branch")), "a string")
        need("change_id", _is_str_or_null(ev.get("change_id")), "a string or null")
        need("reverts", _is_str_or_null(ev.get("reverts")), "a string or null")
        if (out["change_id"] is None) == (out["reverts"] is None):
            raise _invalid(f"{where}: exactly one of change_id and reverts must be non-null", event_id)
    elif kind == "deployment":
        need("deployment_id", _is_str(ev.get("deployment_id")), "a string")
        need("environment", _is_str(ev.get("environment")), "a string")
        outcome = ev.get("outcome")
        need("outcome", isinstance(outcome, str) and outcome in OUTCOMES, "success or failure")
        need("commits", _is_str_list(ev.get("commits")), "an array of strings")
        need("unplanned", isinstance(ev.get("unplanned"), bool), "a boolean")
        need("caused_by", _is_str_or_null(ev.get("caused_by")), "a string or null")
    else:
        need("incident_id", _is_str(ev.get("incident_id")), "a string")
        phase = ev.get("phase")
        need("phase", isinstance(phase, str) and phase in PHASES, "opened or resolved")
        need("deployments", _is_str_list(ev.get("deployments")), "an array of strings")
    return out
