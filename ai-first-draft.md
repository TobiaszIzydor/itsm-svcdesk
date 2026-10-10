---
lab3_first_draft:
  source: ai                    # ai | instructor  (instructor = the no-AI path: the flawed ladder is your draft)
  tool: "Claude Opus 5.5 in claude.ai, new chat, 10 October 2026"
  ladder: [0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.5, 5.0, 10.0]
  verdict: TODO                 # confirmed (it resolves your p99, M-11) | refuted (it does not)
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
lab3_flawed_ladder:
  verdict: refuted              # the only admissible verdict (M-27); the evidence is yours to compute
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
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

The arithmetic: the p99 you measured, the bucket of the draft ladder that holds it, its width relative to the p99,
and what `histogram_quantile` could report from that bucket. Then the verdict in one sentence.

## The draft alert rule

What the assistant's alert rule would have done for your SLO, and what you kept of it in `prometheus/alerts.yml`.

## Verdict on the instructor's flawed ladder

The same arithmetic for `buckets-flawed.example.yml`: where its resolution is spent, and where your p99 is.
