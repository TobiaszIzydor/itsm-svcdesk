<!-- ai-generated: 100% - drafted with ChatGPT from the course requirements and reviewed by the student -->

# svcdesk specification

## Purpose

The svcdesk service provides an HTTP API for managing service-desk tickets.
The service runs on port 8080 and communicates using JSON.

## Ticket creation

The service allows clients to create tickets containing a title, optional
description, reporter information, impact and urgency.

The service assigns every ticket a unique identifier and computes its
priority. Clients cannot choose the identifier, state, priority or service
timestamps.

Impact and urgency use values 1, 2 and 3. Priority starts from the matrix
defined by requirements R-04 and the API contract.

Invalid ticket input must return HTTP 400 or 422 with a JSON error object.
Unknown request fields and server-owned fields supplied by the client are
ignored.

## Ticket retrieval

The service provides endpoints to retrieve one ticket and to list tickets.
Ticket lists may be filtered by exact state and priority.

An unknown ticket identifier returns HTTP 404 with a JSON error object.

## State machine

Tickets follow this normal sequence:

new -> acknowledged -> in_progress -> resolved -> closed

The corresponding actions are acknowledge, start, resolve and close.
Invalid transitions return HTTP 409.

A resolved ticket may be reopened within seven days and returns to
in_progress. Behaviour for reopening an already closed ticket is decision C2
and must match DECISIONS.md.

## Priority decision

The impact and urgency matrix is the base priority calculation.

The effect of reporter.vip is decision C3. The implementation must use one of
the admissible behaviours defined by API.md and the selected behaviour must
match DECISIONS.md.

## SLA

Each priority has acknowledgement and resolution targets.

P2, P3 and P4 use business hours: Monday to Friday from 08:00 to 16:00 in
Europe/Warsaw.

The clock used by P1 is decision C1. It may use wall-clock time or
business-hours time as defined by API.md. The running service and DECISIONS.md
must use the same choice.

GET /tickets/{id}/sla reports the priority, acknowledgement due time,
resolution due time, breach state and paused state.

## Test clock

When SVCDESK_TEST_CLOCK is enabled, X-Test-Clock provides the current time for
that request. A malformed test-clock value returns HTTP 400 or 422.

## Deployment

The service is delivered through Docker Compose as a service named svcdesk.
It is built from this repository, listens on port 8080 and must not use
host-path bind mounts.

GET /health returns HTTP 200 with:

{"status": "ok", "service": "svcdesk"}

The service must become healthy within 120 seconds.

## Decision points

Three contradictions in the requirements are intentionally left for an
explicit implementation decision:

- C1: R-13 versus R-14, concerning the SLA clock for P1.
- C2: R-09 versus R-10, concerning reopening closed tickets.
- C3: R-05 versus R-06, concerning VIP reporters and priority.

The chosen values will be documented in DECISIONS.md before implementation,
and the implementation must exhibit exactly those behaviours.