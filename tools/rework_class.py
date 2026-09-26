# ai-generated: 85% - Claude Code wrote the script; the data source and the rework rule are mine
"""L2-STRETCH-2: deployment rework rate over the class submissions repository -> rework-class.json.

Standard library only. Runs from the repository root (e.g. inside python:3.13-slim with the repo at /repo):

    python tools/rework_class.py

Rule: every issue carrying both "receipted" and "kind:submission" (pull requests skipped) is a deployment.
Deployments are grouped by (user.login lowercased, lab number from the "lab:<n>" label) and ordered by
(created_at, issue number); the first of each group is planned, every later one is a rework deployment.
The capture file is only read, never modified.
"""

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext

SOURCE = ('gh api --paginate "repos/swasik/itsm-2026-submissions/issues?state=all&labels=receipted,'
          'kind:submission&per_page=100" --jq ".[]"')
CAPTURE_PATH = "rework/submissions.jsonl"
OUTPUT_PATH = "rework-class.json"
REQUIRED_LABELS = {"receipted", "kind:submission"}
LAB_LABEL = re.compile(r"lab:([0-9]+)")


def label_names(issue):
    """GitHub returns labels as objects with a name; plain strings are accepted too."""
    names = set()
    for label in issue.get("labels") or []:
        name = label.get("name") if isinstance(label, dict) else label
        if isinstance(name, str):
            names.add(name)
    return names


def parse_instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def classify(issues):
    """(deployments grouped by (login, lab), skip reasons) for the issues of the capture."""
    groups = defaultdict(list)
    skipped = Counter()
    for issue in issues:
        if not isinstance(issue, dict):
            skipped["not an object"] += 1
            continue
        if "pull_request" in issue:
            skipped["pull request"] += 1
            continue
        names = label_names(issue)
        if not REQUIRED_LABELS <= names:
            skipped["missing receipted or kind:submission"] += 1
            continue
        labs = {int(m.group(1)) for m in (LAB_LABEL.fullmatch(n) for n in names) if m}
        if len(labs) != 1:
            skipped["no lab label" if not labs else "several lab labels"] += 1
            continue
        login = (issue.get("user") or {}).get("login")
        if not isinstance(login, str) or not login:
            skipped["no user.login"] += 1
            continue
        groups[(login.lower(), labs.pop())].append(issue)
    for group in groups.values():
        group.sort(key=lambda i: (parse_instant(i["created_at"]), i["number"]))
    return groups, skipped


def rate(rework, deployments):
    if deployments == 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 50
        return float((Decimal(rework) / Decimal(deployments)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def main():
    with open(CAPTURE_PATH, "rb") as f:
        raw = f.read()
    captured_at = datetime.fromtimestamp(os.stat(CAPTURE_PATH).st_mtime, timezone.utc)
    lines = [line for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    issues = [json.loads(line) for line in lines]

    groups, skipped = classify(issues)
    deployments_per_lab = Counter()
    rework_per_lab = Counter()
    for (_, lab), group in groups.items():
        deployments_per_lab[lab] += len(group)
        rework_per_lab[lab] += len(group) - 1  # everything after the first submission is a resubmission
    deployments = sum(deployments_per_lab.values())
    rework = sum(rework_per_lab.values())

    result = {
        "source": SOURCE,
        "captured_at": captured_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capture_path": CAPTURE_PATH,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "deployments": deployments,
        "rework_deployments": rework,
        "deployment_rework_rate": rate(rework, deployments),
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(result, indent=2) + "\n")

    print(f"read {len(issues)} issues from {CAPTURE_PATH}; skipped {sum(skipped.values())}"
          + "".join(f"\n  skipped ({reason}): {n}" for reason, n in sorted(skipped.items())))
    print(f"{len(groups)} (student, lab) groups")
    for lab in sorted(deployments_per_lab):
        print(f"  lab {lab}: deployments {deployments_per_lab[lab]}, rework {rework_per_lab[lab]}, "
              f"rate {rate(rework_per_lab[lab], deployments_per_lab[lab])}")
    print(f"total: deployments {deployments}, rework {rework}, rate {result['deployment_rework_rate']}")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
