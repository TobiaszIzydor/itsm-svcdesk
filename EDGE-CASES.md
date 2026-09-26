---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 20% - Claude checked every cited event id against the fixture and edited the wording; the analysis and the gaming strategy are mine -->

# Edge cases in the practice event log

## E1 - clock skew produces a negative lead time

- What the log contains: three pairs where the commit is stamped after the deployment that shipped it: sha-0040 in DEP-0012 (13m54s late), sha-0094 in DEP-0024 (51s late) and sha-0123 in DEP-0031 (13m late).
- What a default definition would have done: dropping the pairs would remove three real deliveries and nudge the median upward, while keeping raw negatives would let a single broken clock push the median toward nonsense; either way the dashboard reader never learns that two machines disagree about the time.
- Why the rule is defensible: the change was genuinely delivered, so the pair must stay; clamping to zero bounds the error to the size of the skew (minutes here), and counting the clamped pairs turns a silent distortion into a visible signal that someone needs to fix NTP.

## E2 - a revert of a revert

- What the log contains: sha-0070 reverts sha-0069 and sha-0071 reverts sha-0070, so two of the three commits have a non-null reverts and all three resolve transitively to CHG-0033.
- What a default definition would have done: counting three commits as three changes would report two units of work that do not exist, so a team that thrashes back and forth on one change would look more productive than a team that got it right the first time.
- Why the rule is defensible: a change is a unit of intended work, and a revert has no intent of its own; inheriting the change_id transitively means churn is attributed to the change that caused it instead of inflating throughput.

## E3 - a hotfix that never touched `main`

- What the log contains: four shas from hotfix branches reached production in the window: sha-0019 (DEP-0006), sha-0077 (DEP-0019), sha-0108 (DEP-0028) and sha-0127 (DEP-0033).
- What a default definition would have done: filtering on branch == "main" would silently delete these commits from lead time, and hotfixes are typically the fastest and most urgent changes, so the dashboard would show slower delivery and hide exactly the work that happened under pressure.
- Why the rule is defensible: lead time measures code reaching users, and users do not care which branch it came from; counting commits_never_on_main separately keeps the process shortcut visible without falsifying the delivery numbers.

## E4 - a deployment with zero linked commits

- What the log contains: four production deployments in the window carry no commits: DEP-0026 and DEP-0032 succeeded, while DEP-0043 and DEP-0044 failed and each opened its own incident.
- What a default definition would have done: dropping them would erase two real production failures from the change fail rate, so the reader would see a healthier service than the one users experienced, and dividing by an empty commit list could crash the computation outright.
- Why the rule is defensible: a config push or a redeploy is still a release that can break production, so it belongs in frequency, fail rate and rework denominators; it simply has no commit to measure lead time from, so it contributes no pair.

## E5 - a deployment that failed and never recovered

- What the log contains: DEP-0015 failed on 2026-09-07 at 06:12:35Z; its only covering incident, INC-0004, opened at 06:35:41Z and has no resolved event anywhere in the log.
- What a default definition would have done: closing it at the window's end would invent a recovery time of about fifteen days that changes whenever someone moves the window, and dropping it entirely would also remove it from the change fail rate, so the worst failure of the period would be the one the dashboard forgets.
- Why the rule is defensible: a recovery that has not happened has no duration, so it cannot enter the median without fabrication; but the failure did happen, so it stays in change_fail_rate and in open_failures, where the reader can see it is still outstanding.

## E6 - overlapping incidents

- What the log contains: eleven intersecting incident pairs: INC-0004, still open and therefore running to the window's end, intersects seven later incidents; INC-0005, INC-0010 and INC-0011 overlap each other on 2026-09-07; and INC-0007 overlaps INC-0008 on 2026-09-19.
- What a default definition would have done: merging overlapping incidents would give several independent failures one shared recovery and hide how many things broke, while summing wall-clock would count the same outage hours two or three times and make the morning of 7 September look like a far longer outage than users saw.
- Why the rule is defensible: the metric asks how long it took to recover from each failed deployment, so it is computed per failed deployment from its own covering incident; the overlap count tells the reader when incidents were concurrent without letting that concurrency distort the durations.

## Gaming demonstration

I improved change_lead_time_seconds_p50 by exploiting R-08, which takes the median over (deployment, commit) pairs rather than over changes. In after.jsonl I added a large number of trivial one-commit changes, each deployed a few minutes after it was committed, so short pairs outnumber the real ones and the median collapses. At the same time I moved every base deployment two days later, so the real work reached users more slowly: in the base-only log, the true change lead time rose by well over the 25 % the harm gate requires. In a real team this is what a lead-time OKR or a push to reach DORA's "elite" band would produce: engineers split work into micro-PRs that are merged and shipped immediately, while substantial changes wait for a slower release train. The engineers producing the micro-PRs and the manager reporting an elite lead time would be rewarded, while the customers waiting for the actual features would pay for it.
