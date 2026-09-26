# ai-generated: 85% - Claude Code wrote the code from my design (phase/state mapping and ordering given in the prompt)
"""GET /dora/ticket-events (METRIC-SPEC.md section 7): the lifecycle instants a ticket actually holds, as a stream."""

from typing import Any

from svcdesk.dora.timeparse import format_instant, parse_instant

# (stored timestamp, phase, state at that instant), in lifecycle order. No in_progress: Lab 1 stores no instant for it.
PHASES = (
    ("created_at", "created", "new"),
    ("acknowledged_at", "acknowledged", "acknowledged"),
    ("resolved_at", "resolved", "resolved"),
    ("closed_at", "closed", "closed"),
)


def ticket_events(tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One event per held timestamp, sorted by (instant, ticket_id); a null or absent timestamp emits nothing.

    A reopen clears resolved_at and closed_at, so a reopened ticket only emits the phases it still holds.
    """
    keyed = []
    for ticket in tickets:
        ticket_id = str(ticket["id"])
        for rank, (field, phase, state) in enumerate(PHASES):
            value = ticket.get(field)
            if not value:
                continue
            at = parse_instant(value)
            event = {
                "ticket_id": ticket_id,
                "at": format_instant(at),
                "phase": phase,
                "priority": ticket["priority"],
                "state": state,
            }
            keyed.append(((at, ticket_id, rank), event))  # rank keeps equal instants in lifecycle order
    keyed.sort(key=lambda item: item[0])
    return [event for _, event in keyed]
