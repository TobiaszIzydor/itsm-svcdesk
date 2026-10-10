---
lab3_first_draft:
  source: ai                    # ai | instructor  (instructor = the no-AI path: the flawed ladder is your draft)
  tool: "Claude Opus 5.5 in claude.ai, new chat, 10 October 2026"
  ladder: [0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.5, 5.0, 10.0]
  verdict: refuted
  evidence: {p99_seconds: 0.2591, bucket: [0.2, 0.3], relative_width: 0.386}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.2591, bucket: [0.04, 0.5], relative_width: 1.775}
---
<!-- ai-generated: 70% - the Answer is the assistant's verbatim; the prompt and the decisions are mine, Claude Code drafted the arithmetic and verdict prose -->

# The assistant's first draft, and two verdicts

## Prompt

I'm instrumenting a Python FastAPI service with Prometheus. It has an endpoint GET /kb/search that calls an upstream search index on every request. Please suggest histogram bucket boundaries, in seconds, for the request-latency histogram http_server_request_duration_seconds, and a Prometheus alerting rule for this endpoint. Give me the list of buckets and the alert rule as YAML.

## Answer

The upstream search call sets the latency floor, so most requests will probably land between about 20 ms and 1 s. These buckets give fine resolution in that range, coarser resolution for slow outliers and timeouts, and an exact boundary at 0.5 s for the alert threshold.

yaml
# http_server_request_duration_seconds buckets (seconds)
buckets:
  - 0.01
  - 0.025
  - 0.05
  - 0.075
  - 0.1
  - 0.15
  - 0.2
  - 0.3
  - 0.5    # SLO threshold, kept as an exact boundary
  - 0.75
  - 1.0
  - 1.5
  - 2.5
  - 5.0
  - 10.0   # cover your upstream/client timeout; +Inf is added automatically
yaml
groups:
  - name: kb-search-latency
    rules:
      - alert: KbSearchHighLatencyP95
        expr: |
          histogram_quantile(
            0.95,
            sum by (le) (
              rate(http_server_request_duration_seconds_bucket{method="GET", handler="/kb/search"}[5m])
            )
          ) > 0.5
          and
          sum(rate(http_server_request_duration_seconds_count{method="GET", handler="/kb/search"}[5m])) > 0.1
        for: 10m
        labels:
          severity: warning
          service: kb-api
        annotations:
          summary: "GET /kb/search p95 latency above 500ms"
          description: >-
            p95 latency for GET /kb/search has been {{ $value | humanizeDuration }}
            for 10 minutes. Check the upstream search index first.

A few notes:

Threshold: The 0.5 s threshold and the 0.1 req/s traffic guard are placeholders. The guard stops a handful of requests from firing the alert overnight. After a week of real data, set the threshold just above your observed p95.
Alert on a boundary: Keep the alert threshold equal to a bucket boundary. histogram_quantile interpolates linearly inside a bucket, so a threshold that falls mid-bucket gives a fuzzy result.
Label names: These depend on your instrumentation. prometheus-fastapi-instrumentator uses handler and method, while OpenTelemetry-based setups often use http_route and http_request_method. Adjust the matchers to fit.
Setting buckets in code: With prometheus_client, pass buckets=(0.01, 0.025, ..., 10.0) to the Histogram. With prometheus-fastapi-instrumentator, use metrics.latency(buckets=...).
Upstream metric: It's worth adding a separate histogram for the upstream search call itself. When this alert fires, you'll be able to tell whether the slowness comes from the index or your service.

## Verdict on the draft ladder

My `load 3` run (my own login's profile, 60 s open-loop at 40 requests/s, 10 October 2026) measured a p99 of
0.2591 s. The distribution has two modes: about 96.5 % of the requests finish in 13-100 ms (p50 37 ms, p95 76 ms),
and the remaining 3.5 % sit in a narrow slow mode between 0.21 and 0.30 s. The p99 is inside that slow mode.

The draft ladder puts 0.2591 s in the bucket (0.2, 0.3]. Its width is 0.1 s, and 0.1 / 0.2591 = 0.386, i.e.
38.6 % of the p99, almost twice the 20 % that M-11 allows. Inside that bucket `histogram_quantile` interpolates
linearly: about 96.5 % of the requests are at or below 0.2, so the 99th percentile is placed
(0.99 - 0.965) / 0.035 = 71 % of the way through the bucket, at about 0.271 s. That is what my own histogram
reported over the run (271.1 ms against oha's 259.1 ms): 12 ms too high, and any p99 between 0.2 and 0.3 s
would have produced a number somewhere in the same bucket without a warning. The ladder spends its finest
steps (0.01 to 0.1) on the fast mode, where nothing needs to be decided, and jumps over the slow mode in two
coarse steps. Verdict: **refuted**, the draft ladder does not resolve my p99.

## The draft alert rule

The assistant proposed one rule: p95 latency of `/kb/search` above 0.5 s for 10 minutes, guarded by a traffic
floor of 0.1 requests/s. For my service it would never fire. First, its matchers use `handler` and `method`,
while my histogram carries `http_route` and `http_request_method`, so the selector matches no series at all.
Second, even with the labels fixed, my p95 is 76 ms: the slow mode holds only 3.5 % of the requests, so it lies
above the p95 and a p95 rule cannot see it, let alone at 0.5 s, which is above every request I measured. Third,
it does not look at errors, and kb-index's failures (502 from svcdesk) are the part of my SLO that can actually
burn budget. Fourth, a single 5-minute window with a 10-minute `for` either pages on short blips or reacts late,
and it does not reset quickly after the problem ends.

What I kept: the advice to put the latency threshold on a bucket boundary (my latency SLI counts the requests
at or below `le="0.35"`, a boundary of my ladder), and the idea of a traffic guard, which in my rules is replaced
by ratios of rates (no traffic means no ratio, so no alert). The rule itself was replaced by multiwindow,
multi-burn-rate alerts on the availability SLI, as in the SRE Workbook (see `slo.md` and
`prometheus/alerts.yml`).

## Verdict on the instructor's flawed ladder

The same p99, 0.2591 s, falls in the flawed ladder's bucket (0.04, 0.5]. Its width is 0.46 s, and
0.46 / 0.2591 = 1.775, i.e. 177.5 % of the p99. The ladder spends ten of its fourteen boundaries below 0.03 s,
in the fast mode where the median lives, and then jumps from 0.04 straight to 0.5, over the whole slow mode.
About 61 % of my requests finish within 0.04 s, so the remaining 39 % share one bucket, and
`histogram_quantile` places the 99th percentile (0.99 - 0.61) / 0.39 = 97 % of the way through it, at about
0.49 s: nearly twice the true p99, and nowhere near any request I actually measured. Any p99 between 40 ms and
0.5 s would look the same. Verdict: **refuted**.
