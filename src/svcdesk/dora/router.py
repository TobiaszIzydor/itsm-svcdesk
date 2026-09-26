# ai-generated: 85% - Claude Code wrote the code from my design (module layout, algorithms, rounding and validation rules given in the prompt)
"""HTTP layer for /dora/* - the only module of the package that imports FastAPI."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from svcdesk.dora.metrics import evaluate
from svcdesk.dora.ticket_events import ticket_events
from svcdesk.dora.validation import DoraError

router = APIRouter()


def error_response(exc: DoraError) -> JSONResponse:
    error = {"code": exc.code, "message": exc.message}
    if exc.event_id is not None:
        error["event_id"] = exc.event_id
    return JSONResponse(status_code=exc.status, content={"error": error})


@router.post("/dora/metrics")
async def dora_metrics(request: Request) -> JSONResponse:
    # Read the body by hand so FastAPI's own validation never answers first (METRIC-SPEC.md section 6).
    try:
        body = await request.json()
    except Exception:  # invalid JSON, invalid UTF-8, nesting too deep
        return error_response(DoraError(400, "bad_request", "the body is not valid JSON"))
    try:
        return JSONResponse(evaluate(body))
    except DoraError as exc:
        return error_response(exc)


@router.get("/dora/ticket-events")
def dora_ticket_events() -> JSONResponse:
    # Imported here, not at the top: svcdesk.main imports this module while it is still being loaded.
    from svcdesk.main import store

    return JSONResponse(ticket_events(store.all()))
