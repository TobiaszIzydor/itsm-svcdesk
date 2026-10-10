# ai-generated: 70% - Claude Code wrote the code from my instructions (endpoint contract and upstream policy are mine)
"""GET /kb/search - one call to kb-index per request, no cache, no retry (MONITORING-SPEC.md M-02)."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

KB_INDEX_URL = os.environ.get("KB_INDEX_URL", "http://kb-index:8080").rstrip("/")
UPSTREAM_TIMEOUT_SECONDS = 5.0

router = APIRouter()


def upstream_unavailable(message: str) -> JSONResponse:
    return JSONResponse(status_code=502, content={"error": {"code": "upstream_unavailable", "message": message}})


@router.get("/kb/search")
def kb_search(q: str = Query(min_length=1, max_length=200)) -> Any:
    # A plain def: FastAPI runs it in its threadpool, so the blocking urllib call does not stall the event loop.
    url = f"{KB_INDEX_URL}/search?{urllib.parse.urlencode({'q': q})}"
    try:
        with urllib.request.urlopen(url, timeout=UPSTREAM_TIMEOUT_SECONDS) as upstream:
            body = json.loads(upstream.read())
        hits = body["hits"]
    except urllib.error.HTTPError as exc:
        return upstream_unavailable(f"kb-index answered {exc.code}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return upstream_unavailable(f"kb-index unreachable or invalid: {type(exc).__name__}")
    return {"query": q, "hits": hits}
