---
lab4_postmortem:
  ticket: "1224ad8d-06a8-4ae3-865a-da2015a4ddb5"
  detecting_alert: ShopCheckoutErrors
  onset: 2026-10-12T07:05:45Z
  detection: 2026-10-12T07:09:19Z
  acknowledgement: 2026-10-12T07:10:07Z
  recovery: 2026-10-12T07:12:19Z
  mttd_seconds: 214
  mtta_seconds: 48
  mttr_seconds: 394
  identified_flags: [productCatalogFailure, adManualGc, recommendationCacheFailure]
---
<!-- ai-generated: 70% - the flag identification and the conclusions are my decisions from the queries I ran; Claude Code ran the queries and drafted the text -->

# Postmortem: some orders and product pages failed, ads slowed to 0.8 s

## Date

The incident happened on Monday 12 October 2026 between 07:05:45 and 07:12:19 UTC; this postmortem was written on
24 October 2026 from the course recording lab4-rec-3.

## Authors

Written by the on-call engineer of the shop, working from the recorded Prometheus data, the ticket and the
recorded AI investigation (the recorded path of Laboratory 4: the alert, the page and the acknowledgement are part of
the recording).

## Status

Complete for the incident: service was restored at 07:12:19 UTC and the ticket is acknowledged. The problem record
stays open and the action items are in progress.

## Summary

For about six and a half minutes the shop failed a share of its product-page, recommendation and checkout requests,
because the product catalog returned errors for some products, while ads slowed from about 4 ms to about 0.8 s
because the ad service spent seconds of every minute in garbage collection.

## Impact

Measured on the recording with `sum(increase(traces_span_metrics_calls_total{...}[9m]))` at 07:14 UTC (07:05-07:14):

- **Orders:** about 2 of 64 `PlaceOrder` calls failed (3.5 %): `service_name="checkout", span_kind="SPAN_KIND_SERVER",
  span_name="oteldemo.CheckoutService/PlaceOrder", status_code="STATUS_CODE_ERROR"`. Those customers lost their order.
- **Catalog:** 42 of 1,007 `GetProduct` calls failed (4.2 %), `service_name="product-catalog"`.
- **Front end:** 84 of 2,102 requests failed (4.0 %), mostly `GET /api/products/[productId]/index` (0.17/s at 07:11)
  and `GET /api/recommendations` (0.10/s): product pages and recommendation boxes that did not load.
- **Ads:** p95 of `oteldemo.AdService/GetAds` rose from 3.9 ms to 780-880 ms and the median from 2 ms to 600 ms
  (`histogram_quantile(0.95, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="ad",
  span_kind="SPAN_KIND_SERVER"}[2m])))`), which pushed the frontend's p95 from 33 ms to 620 ms (`GET /api/data`
  1.2 s).
- Payment, shipping, email and cart were not affected: no failed spans, unchanged latency and traffic.

## Root Causes

Three feature flags failed at the onset, one per class of the injector's pool; identified from symptoms only:

- **productCatalogFailure** (errors, confident): product-catalog started failing `GetProduct` (0 before, 0.15/s
  after), and every failed checkout span is a failed `GetProduct` call of checkout (`span_kind="SPAN_KIND_CLIENT"`).
  Payment had 0.11 calls/s and no errors, so it is not `paymentFailure`; ad had no errors, so it is not `adFailure`.
- **adManualGc** (latency, confident): the ad service's GC time went from 0 to about 7 s per minute
  (`sum(rate(jvm_gc_duration_seconds_sum{service_name="ad"}[2m]))*60`), its JVM memory from 129 to 147 MB and its
  latency up by two orders of magnitude, all from 07:06:30 and all gone after the fault ended. Shipping latency,
  catalog latency and front-end traffic were unchanged, which rules out the three other flags of the class.
- **recommendationCacheFailure** (resources, not certain): the weakest signal of the three. Recommendation's memory
  rose slowly from the onset (container 85.4 to 86.5 MB, falling back after the fault ended) and its p95 from about
  5 to 7 ms at the end; the email service, the only other candidate of the class, stayed flat at 62 MB, which a 100x
  or 1000x leak at six confirmations a minute would not have done. Six minutes were too short for this fault to
  hurt users.

## Trigger

The three flags switched on together at the onset, 07:05:45 UTC; the first symptoms reached the metrics with the
next one-minute push (ad latency at 07:06:30, catalog errors at 07:07:30).

## Resolution

Service was restored by switching the failing flags off. The recording shows the catalog errors stopping first (the
2-minute error rate is 0 from 07:11:30, so `productCatalogFailure` went off around 07:11), which ended the failed
orders and resolved ShopCheckoutErrors at 07:12:19 UTC; the fault was fully over by 07:13:30, when the last flag was
off, and ad latency was back to normal at 07:14:30. Errors first was the right order: failing orders lose money and
customers, slow ads only annoy them.

## Detection

ShopCheckoutErrors (P1, `service="checkout"`) fired at 07:09:19 UTC, 214 s after the onset, on the symptom users
felt - checkout errors - and paged the on-call; ShopServiceErrors (P2, per service) went to chat for checkout,
frontend, frontend-proxy and product-catalog. The ad slowdown, which started first, paged no one: nothing alerted on
ad or front-end latency, and only customers would have noticed it.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Alert on the front end's p95 latency (P3 to chat) so that a slowdown like the ad service's is seen without a checkout failure | prevent | on-call team | ITSM-41 |
| Page on product-catalog's own GetProduct error ratio, the cause seen one hop earlier than checkout | mitigate | shop team | ITSM-42 |
| Add the feature-flag changes of the last hour to the incident ticket template, so that "what changed?" is answered first | process | on-call team | ITSM-43 |
| Watch memory growth per service (recommendation, email) with a slow-burn alert, so that a resource fault is visible before it degrades users | prevent | shop team | ITSM-44 |
| Give the AI investigator instructions to compare with the baseline before the onset and to read counters with rate() | other | on-call team | ITSM-45 |

## Lessons Learned

### What went well

The page went to the right person 3.5 minutes after the onset and was acknowledged 48 s later; the symptom alert was
on checkout, which is what users care about, and the four per-service P2 alerts went to chat, not to the pager, so
the person woken got one page (the pager counted one firing and one resolved notification).

### What went wrong

The ad service was slow for three minutes before the page and nothing told anyone; the AI investigator repeated the
alert (H1), blamed payment without checking it (H3) and read a cumulative counter as growing load (H4) - only H2,
the catalog, pointed beyond the alert.

### Where we got lucky

The catalog failed only one product in ten and the incident was short, so only about two orders were lost; the
resource fault (recommendation) had no time to grow, and with a longer incident it would have degraded the
recommendation box too.

## Timeline

All times UTC, 12 October 2026.

- **07:05:00** last quiet minute: no failed server spans, ad p95 3.9 ms, frontend p95 35 ms.
- **07:05:45** onset: the three flags switch on.
- 07:06:30 ad latency jumps (p95 880 ms) and the ad JVM starts spending seconds per minute in GC.
- 07:07:30 product-catalog `GetProduct` errors appear (0.15/s); front-end product pages start failing.
- **07:09:19** detection: ShopCheckoutErrors (P1) fires and pages the on-call; ShopServiceErrors (P2) goes to chat.
- 07:09:37 ticket `1224ad8d-06a8-4ae3-865a-da2015a4ddb5` is created (P1).
- **07:10:07** acknowledgement of the ticket by the on-call.
- 07:11 the AI investigator (ledger `ai-rca-eval.json`) proposes four hypotheses; acted on:
  - **H1** (correct): the errors are in checkout's `PlaceOrder` -
    `sum(rate(traces_span_metrics_calls_total{service_name="checkout", span_kind="SPAN_KIND_SERVER", span_name="oteldemo.CheckoutService/PlaceOrder", status_code="STATUS_CODE_ERROR"}[5m])) > 0`,
    0.007/s at 07:11:30, nothing at the baseline; it confirms the page, adds nothing.
  - **H2** (correct): they come from `ProductCatalogService/GetProduct` -
    `sum(rate(traces_span_metrics_calls_total{service_name="product-catalog", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[5m])) > 0.05`,
    0.096/s at 07:11:30, nothing at the baseline; the lead that pointed at the catalog.
  - H3 (payment) and H4 (load) were checked and contradicted by the data, not acted on.
- ~07:11 `productCatalogFailure` off: the catalog's error rate is 0 from 07:11:30.
- **07:12:19** recovery: ShopCheckoutErrors resolves.
- 07:13:30 the fault is fully over (all flags off); 07:14:30 ad latency back to normal.

## Supporting information

`itsmlab incident 4` printed onset 07:05:45Z, detection 07:09:19Z by ShopCheckoutErrors, acknowledgement 07:10:07Z,
recovery 07:12:19Z, MTTD 214 s, MTTA 48 s, MTTR 394 s (run fe6ecd21acce7a08). The data is the snapshot
`incident/tsdb-snapshot.tar.gz` of recording lab4-rec-3, served by Prometheus 3.15.0; the queries are the ones quoted
in Impact, Root Causes and Timeline; the ticket is `incident/ticket.json`; the AI investigation is
`ai-rca/transcript.md` and its ledger `ai-rca-eval.json`; the alert rules are `prometheus/demo-alerts.yml` and the
routing tree `alertmanager/alertmanager.yml`.

## Problem record

- Incident record: 1224ad8d-06a8-4ae3-865a-da2015a4ddb5 (P1, Shop checkout failing, paged by ShopCheckoutErrors)
- Root cause: the product catalog fails GetProduct for some products while productCatalogFailure is on, and the ad service runs manual full garbage collections while adManualGc is on; recommendationCacheFailure grows the recommendation cache.
- Known error: checkout, product pages and recommendations fail for about one product in ten while the catalog flag is on, and ads take about 0.8 s while the GC flag is on; the cause is known, the fix (alerts on the cause and on latency) is not yet in place.
- Workaround: switch the failing flag off in the injector (POST /flags/{key}/off), catalog first because it loses orders, then the ad and recommendation flags.
