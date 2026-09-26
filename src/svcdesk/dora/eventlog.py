# ai-generated: 85% - Claude Code wrote the code from my design (module layout, algorithms, rounding and validation rules given in the prompt)
"""Deduplication (R-05), indexes, and the well-formedness rules of METRIC-SPEC.md section 1."""

from dataclasses import dataclass
from typing import Any

from svcdesk.dora.changes import RevertCycleError, resolve_change
from svcdesk.dora.validation import DoraError


def dedupe(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """First occurrence of each event_id wins; later ones are dropped silently."""
    seen: set[str] = set()
    kept = []
    for ev in raw_events:
        if ev["event_id"] not in seen:
            seen.add(ev["event_id"])
            kept.append(ev)
    return kept


def _malformed(message: str, event_id: str | None = None) -> DoraError:
    return DoraError(422, "malformed_log", message, event_id)


@dataclass
class EventLog:
    commits_by_sha: dict[str, dict[str, Any]]
    deployments: list[dict[str, Any]]
    # incident_id -> {"opened": datetime | None, "resolved": datetime | None, "deployments": ids from opened}
    incidents: dict[str, dict[str, Any]]

    @classmethod
    def build(cls, events: list[dict[str, Any]]) -> "EventLog":
        """Index deduplicated, shape-checked events; DoraError when the log is not well formed."""
        commits: dict[str, dict[str, Any]] = {}
        deployments: list[dict[str, Any]] = []
        incidents: dict[str, dict[str, Any]] = {}
        incident_events: list[dict[str, Any]] = []
        for ev in events:
            if ev["type"] == "commit":
                if ev["sha"] in commits:
                    raise _malformed(f"sha {ev['sha']} appears on more than one commit", ev["event_id"])
                commits[ev["sha"]] = ev
            elif ev["type"] == "deployment":
                deployments.append(ev)
            else:
                incident_events.append(ev)
                entry = incidents.setdefault(ev["incident_id"], {"opened": None, "resolved": None, "deployments": []})
                if entry[ev["phase"]] is not None:
                    raise _malformed(
                        f"incident {ev['incident_id']} has more than one {ev['phase']} event", ev["event_id"]
                    )
                entry[ev["phase"]] = ev["at"]
                if ev["phase"] == "opened":
                    entry["deployments"] = ev["deployments"]

        deployment_ids = {d["deployment_id"] for d in deployments}
        for sha, commit in commits.items():
            if commit["reverts"] is not None and commit["reverts"] not in commits:
                raise _malformed(f"commit {sha} reverts unknown sha {commit['reverts']}", commit["event_id"])
        for d in deployments:
            for sha in d["commits"]:
                if sha not in commits:
                    raise _malformed(f"deployment {d['deployment_id']} carries unknown sha {sha}", d["event_id"])
            if d["caused_by"] is not None and d["caused_by"] not in incidents:
                raise _malformed(
                    f"deployment {d['deployment_id']} caused_by unknown incident {d['caused_by']}", d["event_id"]
                )
        for ev in incident_events:
            for dep in ev["deployments"]:
                if dep not in deployment_ids:
                    raise _malformed(f"incident {ev['incident_id']} names unknown deployment {dep}", ev["event_id"])
        for incident_id, entry in incidents.items():
            if entry["opened"] is None:
                raise _malformed(f"incident {incident_id} resolved but was never opened")

        log = cls(commits_by_sha=commits, deployments=deployments, incidents=incidents)
        memo: dict[str, str] = {}
        for sha in commits:
            try:
                resolve_change(log, sha, memo)
            except RevertCycleError as exc:
                raise _malformed(str(exc), commits[exc.sha]["event_id"]) from None
        return log
