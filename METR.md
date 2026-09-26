---
actual_minutes: 37
predicted_minutes: 75
ratio: 0.49
---

# METR n=1 replication
 
Feature: "POST /dora/metrics - five DORA metrics with the six edge-case rules" (feature_path `src/svcdesk/dora/`).
Prediction receipt: <URL issue z predykcją>
 
Predicted: 75 minutes. Actual: 37 minutes, measured from 15:40 (start of work after the prediction receipt) to
16:17 (a working endpoint that passed every metrics check of the local checker). Ratio actual/predicted: **0.49**.
 
## What went into the 37 minutes
 
I gave Claude Code one prompt containing my design: the module layout, the algorithm for each metric with its
rule number, the rounding policy and the validation rules. It wrote eight files in `src/svcdesk/dora/` and
registered the router in `main.py`. Because there is no Python on my machine, it verified the pure computation
inside a throwaway `python:3.13-slim` container and showed me a field-by-field comparison with
`fixtures/metrics-practice.json`. Every field matched on the first attempt, and `./itsmlab.ps1 verify 2` left only
the checks that belonged to later steps. Reading its report, I noticed that it validated every event before
deduplication, so a malformed later duplicate would have been rejected, while R-05 says later duplicates are
ignored and are not an error. One follow-up prompt fixed that, and the re-run confirmed nothing else changed.
Most of the 37 minutes was therefore spent reading and checking the assistant's output, not writing code.
 
## What the 37 minutes does not contain
 
My prediction assumed that reading METRIC-SPEC.md, finding the six edge cases in the practice log and designing
the solution would happen inside the measured window. In practice I did all of that before the receipt, while
preparing for the lab, so it is not in the 37 minutes. <Opcjonalnie: That preparation took roughly P minutes;
counting it, the ratio would be about X.XX.>
 
## What I take from it
 
The ratio of 0.49 looks like a twofold speed-up from AI, but that reading would be misleading. The assistant was
fast and correct because the hard part - turning the specification into precise decisions about pairs, changes,
covering incidents and rounding - was already done and handed to it. What AI removed was the typing; what it did
not remove was understanding the rules and verifying the result, and the one real defect was found by reading
its report against the specification, not by the checker. Next time I would predict the preparation and the
implementation as two separate numbers, so that time moving from one to the other shows up in the measurement
instead of hiding outside it.