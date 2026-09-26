# ai-generated: 85% - Claude Code wrote the code from my design (module layout, algorithms, rounding and validation rules given in the prompt)
"""Change identity: R-06 (reverts inherit their change, transitively) and R-07 (first commit instant)."""

from datetime import datetime


class RevertCycleError(ValueError):
    def __init__(self, sha: str) -> None:
        super().__init__(f"reverts chain starting at {sha} is a cycle")
        self.sha = sha


def resolve_change(log, sha: str, memo: dict[str, str] | None = None) -> str:
    """Follow reverts from sha to the commit that carries a change_id (iterative, memoized in memo)."""
    memo = {} if memo is None else memo
    path: list[str] = []
    on_path: set[str] = set()
    current = sha
    while True:
        if current in memo:
            change = memo[current]
            break
        commit = log.commits_by_sha[current]
        if commit["change_id"] is not None:
            change = commit["change_id"]
            break
        if current in on_path:
            raise RevertCycleError(sha)
        on_path.add(current)
        path.append(current)
        current = commit["reverts"]
    for s in path:
        memo[s] = change
    memo[current] = change
    return change


def first_commit_instants(log, memo: dict[str, str] | None = None) -> dict[str, datetime]:
    """change_id -> earliest at over every commit resolving to it, anywhere in the log."""
    memo = {} if memo is None else memo
    first: dict[str, datetime] = {}
    for sha, commit in log.commits_by_sha.items():
        change = resolve_change(log, sha, memo)
        if change not in first or commit["at"] < first[change]:
            first[change] = commit["at"]
    return first
