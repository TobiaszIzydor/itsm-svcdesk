# svcdesk - house rules for AI agents working in this repository

This is the ITSM 2026/27 course repository: the `svcdesk` ticketing service (Lab 1), extended in later labs.
Read `docs/lab1/REQUIREMENTS.md`, `docs/lab1/API.md` and `docs/lab1/CHECKS.md` before touching code.
`API.md` is the contract the checker enforces and wins wherever the documents differ.

## What never changes without the owner

- **`specs/` is frozen.** It is receipted; the grader checks that every `src/` commit descends from that
  receipt. Never edit, move or delete anything under `specs/` (a converge report is the one allowed addition).
- **`DECISIONS.md` and the service must agree.** The front matter (`C1`, `C2`, `C3`) must equal the
  `DECISIONS` dict at the top of `src/svcdesk/main.py` and what the running service does. Change both or neither.
  Current values: C1=wallclock, C2=immutable, C3=vip.
- **Tags never move.** Attempts are `lab1/v1`, `lab1/v2`, `lab1/v3`; a moved tag voids the attempt. Agents do
  not tag, push or open submission issues; the student does.
- **No personal data**: no hostnames, usernames, e-mail addresses or `doctor` output in any committed file.

## Build and verify

- Stack: Python 3.13 + FastAPI in `src/svcdesk/main.py`; `Dockerfile` from `python:3.13-slim`; dependencies
  pinned in `requirements.txt` and installed at build time (the grader has no network after the build).
- `docker-compose.yml` is a contract: service `svcdesk`, port 8080, `SVCDESK_TEST_CLOCK: "1"`, a named
  volume, **no bind mounts on any service**, `tests` under `profiles: ["tests"]`.
- The one command: `.\itsmlab.ps1 verify 1` on Windows, `./itsmlab.sh verify 1` elsewhere. Core must be green
  and the observation line must read `C1=wallclock C2=immutable C3=vip` before anything is committed as done.
- Own tests: `tests/run_tests.py`, standard library only, reads `SVCDESK_URL`, last line
  `ITSMLAB-TESTS: passed=<n> failed=0`. Run: `docker compose --profile tests run --rm --build tests`.
- SLA changes: rerun the T1..T8 vector check (all sixteen values on both clocks) before claiming anything works.

## Code conventions

- Every file under `src/` and `specs/` with a code or `.md` extension, plus `DECISIONS.md`, carries an
  `ai-generated: <0-100>% - <how>` comment in its first ten lines. Keep the estimate honest.
- Every error body is `{"error": {"code": ..., "message": ...}}`, validation errors and 404s included.
- `X-Test-Clock` is per request only: never compare one request's clock with another, never reject an action
  because its clock precedes a stored timestamp.
- Server-owned and unknown request fields are ignored, never rejected.
- LF line endings everywhere (`.gitattributes`); do not add CRLF files.
- Do not commit `report.json`, `*.db`, `data/` or virtual environments.

## Sub-agents

`.claude/agents/` holds the agents that may run here; `AGENT-POLICY.md` justifies every tool they are denied,
as a blast-radius decision. A new agent gets a denylist and a policy line for each entry before it is used.
