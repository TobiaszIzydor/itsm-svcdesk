<!-- ai-generated: 90% - Claude Code compared specs/001-svcdesk/spec.md with the built service and wrote this report; the student reviewed the divergences -->
# Converge report - specs/001-svcdesk/spec.md against the built service

This compares the receipted specification (`specs/001-svcdesk/spec.md`) with what this repository actually
contains after Lab 1: `src/svcdesk/main.py` (FastAPI, SQLite in a named volume), `docker-compose.yml`,
`tests/run_tests.py` and `DECISIONS.md`. The checker (`itsmlab verify 1`) is green on Core with the
observations C1=wallclock, C2=immutable, C3=vip, which is what `DECISIONS.md` declares.

## What converged

- **Ticket creation and validation (R-03, R-20).** `POST /tickets` takes title, optional description, reporter
  (name, optional e-mail, optional `vip`), impact and urgency; every field the service owns (id, priority,
  state, timestamps, `sla`) and every unknown field is dropped from the request, never rejected. Invalid
  input answers 422 with a top-level `error` object, exactly as the spec's "Ticket creation" section asks.
- **Priority (R-04, R-05, R-06).** The matrix is the base; the VIP floor raises P3 and P4 to P2 and leaves
  P1 and P2 alone. A `priority` in the body is ignored. This is the `vip` branch the spec left to C3.
- **State machine (R-07, R-08).** `new -> acknowledged -> in_progress -> resolved -> closed`, one endpoint
  per action, 409 with an `error` body for every other transition, 404 for an unknown id.
- **Reopen (R-10, R-11).** From `resolved` within 7 days of `resolved_at` the ticket returns to
  `in_progress`; a closed ticket answers 409 regardless of age (C2 = `immutable`, R-09 wins).
- **SLA (R-12, R-13, R-14, R-15).** P2 to P4 run on Monday-Friday 08:00-16:00 Europe/Warsaw; P1 is
  wall-clock (C1 = `wallclock`). `GET /tickets/{id}/sla` reports priority, both due instants, both breach
  flags and `paused`. All eight vectors T1..T8 of API.md are reproduced on both clocks (a scratch check of
  the sixteen values ran before the checker did, and `tests/run_tests.py` asserts them again).
- **Health, listing, test clock, deployment (R-02, R-19, R-21, R-22, R-24).** `GET /health` returns the
  exact body; `GET /tickets` filters on `state` and `priority` with no pagination; `X-Test-Clock` is honoured
  per request and a malformed value is a 400; compose builds `svcdesk` from the repository on 8080 with a
  named volume and no bind mounts, and the service is healthy within seconds.

## What diverged and was fixed during implementation

- **Error shape.** The spec asks for "a JSON error object" (R-20, R-25) but FastAPI's default validation and
  404 bodies use a top-level `detail`. Exception handlers for `RequestValidationError` and `HTTPException`
  now rewrite every error, including the framework's own 404 on an unknown path, into `{"error": {...}}`.
- **Integer strictness.** The spec says impact and urgency "use values 1, 2 and 3"; the first model accepted
  the string `"2"` through Pydantic's lax coercion. `StrictInt` was introduced so that a string such as
  `"high"` or `"2"` is a validation error, as R-20 requires.
- **Naive test clock.** The spec only says a malformed value is rejected. API.md section 8 is stricter: an
  instant without an offset is malformed too. The parser now requires an offset, and `tests/run_tests.py`
  checks a naive timestamp against a 400.
- **Tie at closing.** The spec's SLA section names the business window but not the tie rule; T4 in API.md
  does. The consumption loop uses `remaining <= available`, so a target ending exactly at 16:00 is due at
  16:00 that day rather than 08:00 the next.
- **Reopen side effects.** The spec says only "returns to in_progress". Following R-11 and API.md section 6,
  a reopen now clears `resolved_at` and `closed_at` and leaves `resolve_due_at` untouched; the own tests
  assert both.

## What the specification left open

- **Timestamp format (R-17).** The spec never says how instants are rendered. The service emits UTC with a
  `Z` suffix and whole seconds when the input had whole seconds.
- **Identifier scheme (R-18).** "Unique identifier" became a UUID4 string.
- **Persistence (R-23).** The spec describes no storage. Tickets are JSON documents in a SQLite file under
  `/data`, a named volume, so they survive a container restart.
- **Pause semantics (R-16).** The spec lists a "paused state" without defining it; the service follows
  API.md section 5: open ticket, business-hours resolution target, `now` outside a business window, and
  therefore never paused for a wall-clock P1.
- **Reporter e-mail and `related_to` (R-03).** Neither is validated beyond type; the spec did not ask for
  it and API.md says `related_to` is not validated in Lab 1.
- **Order of decisions.** The spec says the three values "will be documented in DECISIONS.md before
  implementation". The front-matter values were fixed before the code; the five-label prose of
  `DECISIONS.md` was written alongside the implementation and checked against the running service by
  the checker's consistency spec.
