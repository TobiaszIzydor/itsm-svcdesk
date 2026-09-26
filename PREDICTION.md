---
feature: "POST /dora/metrics - five DORA metrics with the six edge-case rules"
predicted_minutes: 75
predicted_at: "2026-09-26T15:40:00+02:00"
feature_path: "src/svcdesk/dora/"
---

The handout budgets 55 minutes for this feature, but I added roughly 20 minutes of buffer because the six
edge-case rules (clock skew, revert chains, off-main hotfixes, deployments without commits, open failures and
overlapping incidents) usually take longer to get right and verify than the happy-path metrics themselves.
I plan to use AI assistance for scaffolding the endpoint and generating test cases, but I expect to spend most
of the time reading the spec and verifying the edge-case behaviour manually.
