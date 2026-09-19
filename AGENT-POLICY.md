# Agent policy - why each tool is denied

Every `disallowedTools` entry of an agent under `.claude/agents/` has one line here. Each denial is a
blast-radius decision: what breaks if the agent uses the tool wrongly, and whether that can be undone.
The agent this applies to is `conformance-reviewer`, a read-only reviewer; the denials are what make it read-only.

- Bash(rm *): a wrong path deletes receipted `specs/`, the `.git` directory or the volume data of a running check; a deleted untracked file (a fresh test, a report, a policy line) has no copy anywhere and cannot be recovered, so the reviewer may never remove anything.
- Bash(git push *): a push publishes to the public repository and to the Tier A workflow; a wrong push moves `main` under a tag, and a force push rewrites history that the specs receipt points at, which voids the receipt and cannot be undone by anyone on our side.
- Bash(git tag *): tags are attempts; `lab1/vN` pushed by mistake consumes one of three graded attempts, and a tag moved after its receipt voids the attempt while still counting, so tagging stays a human decision.
- Bash(docker *): compose commands can `down -v` a checker project mid-run, prune images the checker relies on, or start a service on port 8080 that the human's own run collides with; the checker is the source of truth here and a reviewer that restarts it produces confusing, non-reproducible results.
- WebFetch: the reviewer must judge the code against the published contract in this repository, not against whatever a web page says today; a fetched page can also carry instructions that redirect the review, and there is no way to audit what it read afterwards.
- Write: a reviewer that writes files can overwrite `DECISIONS.md`, `docker-compose.yml` or a source file with its own idea of the contract, silently breaking L1-CORE-4 consistency; findings belong in the conversation, and the human applies them under version control.
- Edit: the same blast radius as Write at a finer grain: a one-line edit to the SLA clock or the `DECISIONS` dict is enough to turn a green Core run red, and an edit to `specs/` would break the spec-first rule; both are recoverable only if the human notices before committing.
