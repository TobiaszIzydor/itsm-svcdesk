# ai-generated: 85% - Claude Code wrote the code from my design (module layout, algorithms, rounding and validation rules given in the prompt)
"""The five DORA metrics, counts, anomalies and ground truth (METRIC-SPEC.md sections 2-6), as a pure function."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from svcdesk.dora.changes import first_commit_instants, resolve_change
from svcdesk.dora.eventlog import EventLog, dedupe
from svcdesk.dora.numeric import clamp0, divide, median, round_ratio, round_seconds, seconds_between
from svcdesk.dora.timeparse import format_instant
from svcdesk.dora.validation import check_event_id, check_event_shape, parse_request

SPEC_VERSION = "1.0.0"
SECONDS_PER_DAY = 86400


def in_scope_deployments(log: EventLog, frm: datetime, to: datetime) -> list[dict[str, Any]]:
    """R-01, R-02: production deployments with from <= at < to, in a deterministic order."""
    scoped = [d for d in log.deployments if d["environment"] == "production" and frm <= d["at"] < to]
    return sorted(scoped, key=lambda d: (d["at"], d["deployment_id"], d["event_id"]))


def lead_time_pairs(log: EventLog, scoped: list[dict[str, Any]]) -> tuple[list[Decimal], int]:
    """R-08..R-10, E1: one pair per sha at its first successful deployment; (clamped values, negatives)."""
    seen: set[str] = set()
    pairs: list[Decimal] = []
    negatives = 0
    for d in scoped:
        if d["outcome"] != "success":
            continue
        for sha in d["commits"]:
            if sha in seen:
                continue
            seen.add(sha)
            lead = seconds_between(log.commits_by_sha[sha]["at"], d["at"])
            if lead < 0:
                negatives += 1
            pairs.append(clamp0(lead))
    return pairs, negatives


def covering_incident(log: EventLog, deployment_id: str) -> dict[str, Any] | None:
    """R-12: the opened incident naming the deployment with the earliest opened (ties: lowest id)."""
    candidates = [
        (entry["opened"], incident_id)
        for incident_id, entry in log.incidents.items()
        if entry["opened"] is not None and deployment_id in entry["deployments"]
    ]
    if not candidates:
        return None
    return log.incidents[min(candidates)[1]]


def recovery_times(log: EventLog, scoped: list[dict[str, Any]]) -> tuple[list[Decimal], int]:
    """R-12, R-13, E5: per failed deployment, never per incident; (recovery times, open failures)."""
    recoveries: list[Decimal] = []
    open_failures = 0
    for d in scoped:
        if d["outcome"] != "failure":
            continue
        covering = covering_incident(log, d["deployment_id"])
        if covering is None or covering["resolved"] is None:
            open_failures += 1
            continue
        recoveries.append(clamp0(seconds_between(d["at"], covering["resolved"])))
    return recoveries, open_failures


def overlapping_incident_pairs(log: EventLog, to: datetime) -> int:
    """R-13, E6: unordered pairs of incidents whose [opened, resolved or to) intervals intersect."""
    intervals = sorted(
        (entry["opened"], entry["resolved"] if entry["resolved"] is not None else to)
        for entry in log.incidents.values()
        if entry["opened"] is not None
    )
    count = 0
    for i, (a_open, a_end) in enumerate(intervals):
        for b_open, b_end in intervals[i + 1:]:
            if b_open >= a_end:  # sorted by opened: no later interval can start before a ends
                break
            if a_open < b_end:
                count += 1
    return count


def ground_truth(
    log: EventLog, scoped: list[dict[str, Any]], memo: dict[str, str], first_commit: dict[str, datetime]
) -> tuple[int, Decimal | None]:
    """R-16, R-17: changes first delivered by a successful in-window deployment, and their true lead time."""
    first_deploy: dict[str, datetime] = {}
    for d in scoped:
        if d["outcome"] != "success":
            continue
        for sha in d["commits"]:
            change = resolve_change(log, sha, memo)
            if change not in first_deploy:
                first_deploy[change] = d["at"]
    leads = [clamp0(seconds_between(first_commit[c], at)) for c, at in first_deploy.items()]
    return len(first_deploy), median(leads)


def compute(log: EventLog, frm: datetime, to: datetime) -> dict[str, Any]:
    """The whole POST /dora/metrics response for a well-formed log, key order as in METRIC-SPEC.md section 6."""
    scoped = in_scope_deployments(log, frm, to)
    total = len(scoped)
    memo: dict[str, str] = {}
    first_commit = first_commit_instants(log, memo)

    successful = sum(1 for d in scoped if d["outcome"] == "success")
    failed = total - successful
    rework = sum(1 for d in scoped if d["unplanned"] is True and d["caused_by"] is not None)
    pairs, negative_pairs = lead_time_pairs(log, scoped)
    recoveries, open_failures = recovery_times(log, scoped)
    delivered, true_lead = ground_truth(log, scoped, memo, first_commit)
    off_main = {
        sha for d in scoped for sha in d["commits"] if log.commits_by_sha[sha]["branch"] != "main"
    }

    return {
        "spec_version": SPEC_VERSION,
        "window": {"from": format_instant(frm), "to": format_instant(to)},
        "deployment_frequency_per_day": round_ratio(divide(total * SECONDS_PER_DAY, seconds_between(frm, to))),
        "change_lead_time_seconds_p50": round_seconds(median(pairs)),
        "failed_deployment_recovery_time_seconds_p50": round_seconds(median(recoveries)),
        "change_fail_rate": round_ratio(divide(failed, total)) if total else None,
        "deployment_rework_rate": round_ratio(divide(rework, total)) if total else None,
        "counts": {
            "deployments": total,
            "successful_deployments": successful,
            "failed_deployments": failed,
            "recovered_failures": len(recoveries),
            "open_failures": open_failures,
            "rework_deployments": rework,
            "lead_time_pairs": len(pairs),
            "changes": len(first_commit),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_pairs,
            "deployments_without_commits": sum(1 for d in scoped if not d["commits"]),
            "commits_never_on_main": len(off_main),
            "revert_chains_collapsed": sum(1 for c in log.commits_by_sha.values() if c["reverts"] is not None),
            "overlapping_incident_pairs": overlapping_incident_pairs(log, to),
        },
        "ground_truth": {
            "changes_delivered": delivered,
            "true_change_lead_time_seconds_p50": round_seconds(true_lead),
        },
    }


def evaluate(body: Any) -> dict[str, Any]:
    """Request body -> response dict, or DoraError.

    R-05: only object-ness and event_id are checked before dedupe; the full shape check and well-formedness
    run on the kept events alone, so a later duplicate is ignored even when it is malformed.
    """
    frm, to, raw_events = parse_request(body)
    for i, ev in enumerate(raw_events):
        check_event_id(ev, i)
    shaped = [check_event_shape(ev) for ev in dedupe(raw_events)]
    return compute(EventLog.build(shaped), frm, to)
