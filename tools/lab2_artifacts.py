# ai-generated: 85% - Claude Code wrote the script; the gaming strategy and its parameters are mine
"""Lab 2 artifacts: metrics.json, gaming/after.jsonl, gaming.json, plus a self-check of METRIC-SPEC.md section 8.

Standard library only. Runs from the repository root (e.g. inside python:3.13-slim with the repo at /repo):

    python tools/lab2_artifacts.py [--base-url http://host.docker.internal:8080]
"""

import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}
BASE_LOG = "fixtures/events-practice.jsonl"
AFTER_LOG = "gaming/after.jsonl"
METRICS_JSON = "metrics.json"
GAMING_JSON = "gaming.json"

METRIC = "change_lead_time_seconds_p50"
RULE = "R-08"
DEPLOYMENT_SHIFT = timedelta(days=2)
GAMING_PAIRS = 130
GAMING_START = datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc)
GAMING_STEP = timedelta(minutes=190)
GAMING_DEPLOY_DELAY = timedelta(minutes=5)

EDGE_CASES = (
    ("E1", "anomalies", "negative_lead_time_pairs"),
    ("E2", "anomalies", "revert_chains_collapsed"),
    ("E3", "anomalies", "commits_never_on_main"),
    ("E4", "anomalies", "deployments_without_commits"),
    ("E5", "counts", "open_failures"),
    ("E6", "anomalies", "overlapping_incident_pairs"),
)


# --- files ---------------------------------------------------------------------------------------

def read_jsonl(path):
    """UTF-8 (a BOM is accepted), blank lines skipped."""
    with open(path, encoding="utf-8-sig") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_text(path, text):
    """UTF-8 without BOM, LF line endings."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_json(path, obj):
    write_text(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def write_jsonl(path, events):
    write_text(path, "".join(json.dumps(ev, separators=(",", ":"), ensure_ascii=False) + "\n" for ev in events))


# --- time ----------------------------------------------------------------------------------------

def parse_instant(value):
    return datetime.fromisoformat(value.replace("z", "Z").replace("Z", "+00:00")).astimezone(timezone.utc)


def format_instant(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- service -------------------------------------------------------------------------------------

def post_metrics(base_url, events, label):
    body = json.dumps({"window": WINDOW, "events": events}).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/dora/metrics", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        sys.exit(f"POST /dora/metrics ({label}) answered {exc.code}: {exc.read().decode('utf-8', 'replace')}")
    except urllib.error.URLError as exc:
        sys.exit(f"POST /dora/metrics ({label}) failed: {exc.reason} (is the service up at {base_url}?)")


# --- gaming log ----------------------------------------------------------------------------------

def build_after(base):
    """Every base event in order, deployments 2 days later; then 130 one-commit, five-minute changes."""
    after = []
    for ev in base:
        ev = copy.deepcopy(ev)
        if ev.get("type") == "deployment":
            ev["at"] = format_instant(parse_instant(ev["at"]) + DEPLOYMENT_SHIFT)
        after.append(ev)
    for i in range(1, GAMING_PAIRS + 1):
        n = f"{i:04d}"
        committed = GAMING_START + i * GAMING_STEP
        after.append({"event_id": f"g-c-{n}", "type": "commit", "at": format_instant(committed),
                      "sha": f"g-sha-{n}", "branch": "main", "change_id": f"G-CHG-{n}", "reverts": None})
        after.append({"event_id": f"g-d-{n}", "type": "deployment",
                      "at": format_instant(committed + GAMING_DEPLOY_DELAY), "deployment_id": f"G-DEP-{n}",
                      "environment": "production", "outcome": "success", "commits": [f"g-sha-{n}"],
                      "unplanned": False, "caused_by": None})
    return after


def build_after_base_only(after, base):
    """R-21's view: commits not in the base log removed, every deployment's commits filtered to base shas."""
    base_shas = {ev["sha"] for ev in base if ev.get("type") == "commit"}
    kept = []
    for ev in after:
        if ev.get("type") == "commit" and ev.get("sha") not in base_shas:
            continue
        if ev.get("type") == "deployment":
            ev = dict(ev, commits=[sha for sha in ev.get("commits", []) if sha in base_shas])
        kept.append(ev)
    return kept


# --- self-check ----------------------------------------------------------------------------------

def first_by_event_id(events):
    first = {}
    for ev in events:
        first.setdefault(ev.get("event_id"), ev)
    return first


def check_conservation(base, after):
    """R-19: base commits keep at/sha/branch/change_id/reverts, incidents are unchanged, deployments keep
    deployment_id/outcome/environment and never move earlier. Returns a list of violations."""
    after_by_id = first_by_event_id(after)
    problems = []
    for event_id, ev in first_by_event_id(base).items():
        other = after_by_id.get(event_id)
        kind = ev.get("type")
        if other is None or other.get("type") != kind:
            problems.append(f"{event_id}: missing from {AFTER_LOG}")
        elif kind == "commit":
            for field in ("sha", "branch", "change_id", "reverts"):
                if other.get(field) != ev.get(field):
                    problems.append(f"{event_id}: {field} changed")
            if parse_instant(other["at"]) != parse_instant(ev["at"]):
                problems.append(f"{event_id}: commit re-timed")
        elif kind == "incident":
            if other != ev:
                problems.append(f"{event_id}: incident changed")
        elif kind == "deployment":
            for field in ("deployment_id", "outcome", "environment"):
                if other.get(field) != ev.get(field):
                    problems.append(f"{event_id}: {field} changed")
            if parse_instant(other["at"]) < parse_instant(ev["at"]):
                problems.append(f"{event_id}: deployment moved earlier")
    return problems


def verdict(ok):
    return "PASS" if ok else "FAIL"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://host.docker.internal:8080")
    args = parser.parse_args()

    base = read_jsonl(BASE_LOG)
    before = post_metrics(args.base_url, base, "base")
    write_json(METRICS_JSON, before)
    print(f"wrote {METRICS_JSON} ({len(base)} base events)")

    after_events = build_after(base)
    write_jsonl(AFTER_LOG, after_events)
    after_events = read_jsonl(AFTER_LOG)  # score exactly what the checker will read
    after = post_metrics(args.base_url, after_events, "after")
    write_json(GAMING_JSON, {"metric": METRIC, "rule": RULE, "before": before, "after": after})
    print(f"wrote {AFTER_LOG} ({len(after_events)} events) and {GAMING_JSON}")

    print("\nSelf-check (METRIC-SPEC.md section 8)")
    results = []

    problems = check_conservation(base, after_events)
    results.append(not problems)
    print(f"  R-19 conservation: {verdict(not problems)} ({len(problems)} violations)")
    for problem in problems[:10]:
        print(f"      {problem}")

    b, a = before[METRIC], after[METRIC]
    eligible = b is not None and b != 0
    improved = eligible and a is not None and a <= 0.75 * b
    results.append(improved)
    detail = f"before {b}, after {a}, limit {0.75 * b:g}" if eligible else f"before {b} is ineligible"
    print(f"  R-20 improvement ({METRIC} -25 %): {verdict(improved)} ({detail})")

    harmed = post_metrics(args.base_url, build_after_base_only(after_events, base), "after_base_only")
    bt, ht = before["ground_truth"]["true_change_lead_time_seconds_p50"], harmed["ground_truth"]["true_change_lead_time_seconds_p50"]
    bd, hd = before["ground_truth"]["changes_delivered"], harmed["ground_truth"]["changes_delivered"]
    slower = bt is not None and ht is not None and ht >= 1.25 * bt
    fewer = hd <= 0.9 * bd
    results.append(slower or fewer)
    print(f"  R-21 harm: {verdict(slower or fewer)}")
    print(f"      true_change_lead_time_seconds_p50: base {bt}, after_base_only {ht}, "
          f"needs >= {1.25 * bt:g} -> {verdict(slower)}" if bt is not None else
          f"      true_change_lead_time_seconds_p50: base is null -> FAIL")
    print(f"      changes_delivered: base {bd}, after_base_only {hd}, needs <= {0.9 * bd:g} -> {verdict(fewer)}")

    print("\nEDGE-CASES.md counts (practice fixture)")
    for case, section, field in EDGE_CASES:
        print(f"  {case}: {before[section][field]}  ({section}.{field})")

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
