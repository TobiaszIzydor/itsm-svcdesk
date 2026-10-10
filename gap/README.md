<!-- ai-generated: 70% - Claude Code ran the measurement and drafted the text; the toxic and the reading of the numbers are my decisions -->
# The client-server latency gap

**Setup.** Toxiproxy 2.12.0 in front of `svcdesk` (`listen 0.0.0.0:8666`, `upstream svcdesk:8080`) with one
latency toxic on the downstream stream: 100 ms, jitter 10 ms, toxicity 1. Measured with
`itsmlab load 3 --base-url http://host.docker.internal:8666` (the M-08 load, 60 s open-loop at 40 requests/s),
10 October 2026, with my own login's kb-index profile.

| | p99 |
|---|---|
| client (oha, through the proxy) | 0.3836 s |
| server (`histogram_quantile(0.99)` over my `/kb/search` histogram, same run) | 0.2687 s |
| gap | 0.1149 s |

**Why the gap exists.** My histogram is started by the middleware when the request reaches the application and
stopped when the application has handed the last byte of the response to the server. Everything outside that
interval is invisible to it: the toxic sits between svcdesk and the client and holds every response for 100 ms
(plus or minus 10 ms) after the server has already finished and recorded its duration. So the server still sees
its usual distribution (fast mode of tens of milliseconds, slow mode of kb-index around 0.21-0.30 s, p99 about
0.27 s, the same as without the proxy), while the client sees every request shifted by the toxic: its p10 moved
from about 25 ms to 140 ms. The measured gap, 115 ms, is the toxic's 100 ms plus about 10-15 ms of extra cost on
the client's path that the server cannot see either: the jitter's upper half at the tail, the additional hop
through Docker Desktop's port forwarding to `host.docker.internal`, and the proxy's own copy of each response.

**What it means.** A server-side histogram answers "how long did my code take", not "how long did the user wait".
An SLO on the server histogram alone would report 0.27 s while users wait 0.38 s at the p99, and it would stay
green if the network, a load balancer or a proxy in front of the service degraded. That is why the latency SLO
needs either a black-box measurement from the client side (a prober, or the load balancer's own histogram) next
to the white-box one, or a threshold with enough headroom for the path the server does not see.
