# ai-generated: 70% - Claude Code wrote the code from my instructions (metric design, labels and ladder source are mine)
"""RED histogram of every request and GET /metrics (MONITORING-SPEC.md M-03 to M-07).

One pure ASGI middleware observes each request exactly once, after routing, so that http_route is the matched
route template (never a raw path or a query string); a request that matches no route gets ROUTE_UNMATCHED.
"""

import time

from fastapi import APIRouter, Response
from prometheus_client import Histogram, disable_created_metrics, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_PLAIN_0_0_4

from svcdesk.buckets import BUCKETS

METRICS_PATH = "/metrics"
ROUTE_UNMATCHED = "unmatched"

# No per-label-set _created gauges: fewer series, and the histogram is exactly _bucket, _sum and _count.
disable_created_metrics()

REQUEST_DURATION = Histogram(
    "http_server_request_duration_seconds",
    "Duration of HTTP server requests, in seconds.",
    ["http_request_method", "http_route", "http_response_status_code"],
    buckets=BUCKETS,
)

router = APIRouter()


@router.get(METRICS_PATH, include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_PLAIN_0_0_4)


class RequestMetricsMiddleware:
    """Times the whole request with perf_counter and observes it once; an exception counts as 500 and is re-raised."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status = 500
        start = time.perf_counter()

        async def send_wrapper(message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status = 500
            raise
        finally:
            route = scope.get("route")
            template = getattr(route, "path", None) or ROUTE_UNMATCHED
            if template != METRICS_PATH:
                REQUEST_DURATION.labels(
                    http_request_method=scope["method"],
                    http_route=template,
                    http_response_status_code=str(status),
                ).observe(time.perf_counter() - start)
