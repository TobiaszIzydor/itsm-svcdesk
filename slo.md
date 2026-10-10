---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 28d
  slis:
    availability:
      objective: 0.99
      good: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code!~"5.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 403.2}
    latency:
      objective: 0.99
      threshold_seconds: 0.35
      good: 'sum(rate(http_server_request_duration_seconds_bucket{job="svcdesk", http_route="/kb/search", le="0.35"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 403.2}
  alerts:
    - {alert: KbSearchErrorsBurnFast, sli: availability, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchErrorsBurnSlow, sli: availability, burn_rate: 6, long_window: 6h, short_window: 30m}
---
<!-- ai-generated: 70% - the objectives, threshold and alert design are my decisions from my load 3 numbers; Claude Code drafted the prose and the arithmetic -->

# SLO for `GET /kb/search`

All numbers below come from my own `load 3` runs on 10 October 2026 (my own login's profile, 60 s open-loop at
40 requests/s, three runs): q, the p99 of `/kb/search`, was 0.256 s, 0.259 s and 0.264 s; p50 37 ms, p95 76 ms,
p99.9 282 ms, p99.99 294 ms; one 502 out of 2,399 responses in the run I used for the verdicts.

## Availability

**SLI:** the share of valid `/kb/search` requests (every request that reached the route, refusals included) that
were not answered with a 5xx status. **Objective: 99 %** over a rolling 28-day window. **Error budget:** 1 % of
the requests, i.e. 0.01 x 40,320 minutes = **403.2 minutes** of complete unavailability per 28 days.

Why 99 % and not 99.9 %: every request makes exactly one call to kb-index, with no retry and no cache (that is the
contract), so every kb-index failure becomes a 502 of mine, and I cannot fix kb-index. In my runs kb-index failed
about 0.04 % of the searches (1 in 2,399), which would already use 40 % of a 99.9 % budget before my own service
or the network has done anything wrong, and one bad day of the dependency would exhaust it. At 99 % the
dependency's normal failure rate costs about 4 % of the budget, so the budget is left for real incidents. The
objective is also one my service meets today with a wide margin, which matters because Lab 6 uses it as a
canary gate: an objective I do not meet would roll back honest releases.

## Latency

**SLI:** the share of valid `/kb/search` requests answered within **0.35 s** (the bucket `le="0.35"` of my ladder,
so the SLI counts requests instead of interpolating them). **Objective: 99 %** over 28 days. **Error budget:** 1 %
of the requests, 403.2 minutes' worth.

Why 0.35 s: the distribution has two modes. About 96.5 % of the requests finish in 13-100 ms; the other 3.5 % sit
in a narrow slow mode between 0.21 and 0.30 s, which is kb-index's own behaviour and which contains my p99. A
threshold below the slow mode (for example 0.1 s) would declare 3.5 % of the requests bad by design, more than a
99 % objective allows, so the SLO would be permanently violated without anything being broken. A threshold inside
the slow mode (0.25 s) would put the SLI on a knife edge: q moved between 0.256 and 0.264 s across my own three
runs, and the grader's machine differs again. 0.35 s is above the whole slow mode (p99.99 was 294 ms) with about
20 % headroom, so a request slower than 0.35 s means something is actually wrong (a degraded index, a saturated
threadpool), not the normal slow mode. It is also well under Lab 6's limit of 1 s.

Why 99 %: practically every request I measured is within 0.35 s, so the objective is met with a large margin and
the budget is spent only when the slow mode moves or widens. A stricter objective (99.9 %) would leave a budget of
about 40 minutes, and a single slow minute of kb-index would page for something the users barely notice.

## Alerts

| alert | SLI | burn rate | long / short window | budget spent when it fires | severity: page or chat |
|---|---|---|---|---|---|
| KbSearchErrorsBurnFast | availability | 14.4 | 1h / 5m | 14.4 x 1h / 672h = 2.1 % | P1, page |
| KbSearchErrorsBurnSlow | availability | 6 | 6h / 30m | 6 x 6h / 672h = 5.4 % | P2, chat |

Both alerts are multiwindow: the long window says the burn is sustained, the short window says it is still
happening, so an alert stops within minutes after the problem ends instead of firing for another half hour.
Both have `for: 2m`, so a single bad scrape does not fire them.

**The fast burn pages (P1).** At 14.4 x the budgeted rate, 14.4 % of the searches fail and the whole 28-day budget
is gone in 672 / 14.4 = about 47 hours. If it starts in the evening and nobody looks until the morning, about a
sixth of the month's budget (8h x 14.4 / 672h = 17 %) is spent overnight and every seventh user search fails for hours; the knowledge base
is the first thing people check before they open a ticket, so failures turn into extra tickets for the service
desk. Waking a person costs one disturbed night; this burn rate is rare enough that a page at it is almost always
real, and it is the only thing that justifies a page.

**The slow burn goes to chat (P2).** At 6 x, 6 % of the searches fail and the budget lasts 672 / 6 = about 112
hours, almost five days. Waiting until the morning costs about 5-10 % of the budget, and users see one failed
search in about seventeen, which is annoying but survivable with a retry. That is worth fixing during working
hours, not worth waking someone. I do not alert on the latency SLI yet: its budget is barely touched by the
distribution I measured, and a latency incident here is in practice a kb-index incident that also produces 502s
(timeouts), which the availability alerts already catch.

## Buckets

My ladder has 29 boundaries: 0.005, 0.01, 0.025, 0.035, 0.05, 0.06, 0.075, 0.1, 0.15, then every 0.01 s from
0.2 to 0.32, then 0.35, 0.4, 0.5, 0.75, 1.0, 2.5 and 5.0.

The p99 of the run I used for the verdicts, 0.2591 s, falls in (0.25, 0.26]: 0.01 s wide, 3.9 % of the p99, far
below the 20 % that is needed. The same 0.01 s steps cover the whole slow mode: every q from about 0.19 s to 0.40 s
falls in a bucket at most 20 % as wide as itself, which is about -25 % / +55 % around my q. I resolved a band
much wider than the required ±10 % because the p99 sits inside a mode that is itself only 0.1 s wide, my own three
runs already moved q by 3 %, and the grader measures on another machine; with 0.01 s steps the exact position of
its q does not matter. Above the band, 0.35 s is the latency threshold, and 0.4 to 5.0 s cover a degraded index up
to my 5 s upstream timeout. Below it I spent nine boundaries on the fast mode (13-100 ms), so that the p50 and
p95 on the dashboard are not one coarse bucket (the p50 of 37 ms falls in (0.035, 0.05]). One boundary of the
30 is left free.
