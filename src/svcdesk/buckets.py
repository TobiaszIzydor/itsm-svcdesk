# ai-generated: 70% - Claude Code proposed the ladder from my load 3 measurement; the band, the threshold and the budget of 30 are my decisions
"""The one ladder of http_server_request_duration_seconds, in seconds (MONITORING-SPEC.md M-06, M-11, M-13).

Measured (load 3, 10 October 2026): a fast mode of 13-100 ms (p50 37 ms, p95 76 ms) and a slow mode of
0.21-0.30 s that holds about 3.5 % of the requests, and with it the p99 (q = 0.259 s). 0.01 s steps from 0.20 to
0.32 s resolve any q from 0.19 to 0.40 s (every bucket at most 20 % of the q it holds); the rest of the 29
boundaries go to the fast mode and to the timeouts. 0.35 is the latency SLI's threshold (slo.md).
"""

BUCKETS = [
    0.005, 0.01, 0.025, 0.035, 0.05, 0.06, 0.075, 0.1, 0.15,
    0.2, 0.21, 0.22, 0.23, 0.24, 0.25, 0.26, 0.27, 0.28, 0.29, 0.3, 0.31, 0.32,
    0.35, 0.4, 0.5, 0.75, 1.0, 2.5, 5.0,
]
