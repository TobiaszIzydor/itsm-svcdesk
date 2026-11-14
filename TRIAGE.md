---
lab5_triage:
  image: ghcr.io/tobiaszizydor/itsm-svcdesk@sha256:e310aa80bf2c2e11860a8c22755af198d356e007f11277a3fed4c3c52030464d
  sarif_receipt: 392
---
<!-- ai-generated: 80% - the decisions are mine; Claude Code read the SARIF, ran the queries and drafted the text -->
# Triage

What the gates and the reporting scanners found on my service, and what I did about each. One row per rule of one
tool; the Reason says which locations it covers.

The image gate was green on the first run, because the Dockerfile was already triaged before it: the base image
`python:3.13-slim` is pinned to the digest of 14 November 2026 (`sha256:e48f59cd...`), the Debian packages are
upgraded at build time, and pip is uninstalled after `pip install`, which removes its vendored msgpack, urllib3 and
`pkg_resources` with their fixed-but-unreleased CVEs. Trivy, Grype and OSV-Scanner then report nothing on my own
dependency files or image, so `.trivyignore` holds no entry.

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| gitleaks | generic-api-key | ignore | `k8s/evidence.json` line 5320 (Lab 3 evidence, raw `kubectl` output): the Helm pod annotation `checksum/secret`, a SHA-256 of the chart's rendered Secret, not a credential. The file must stay as captured, so it is ignored in `.gitleaksignore` with this reason; it made the `secrets` gate red on the first run of `main`. |
| semgrep | dockerfile.security.missing-user.missing-user | fix | `Dockerfile`, the `CMD` line (line 22 on the first run of `main`): the service ran as root. Fixed in the Dockerfile: a system user `svcdesk` (uid 10001) owns `/data`, where SQLite writes, and `USER svcdesk` runs uvicorn; `build-test` (the tests through compose) stays green. |
| semgrep | python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected | false-positive | `src/svcdesk/kb.py:29` builds the URL from `KB_INDEX_URL`, operator configuration and never request data, with the user's `q` only URL-encoded into the query string; `tools/lab2_artifacts.py:86` is a course-lab script whose base URL is a command-line argument; `semgrep/rules.py` lines 13-31 are the test cases of my own Semgrep rules (Stretch 3). No scheme or host is ever taken from a request. |

## Bake-off

My canary set has 9 labelled defects: 3 hard-coded credentials, 2 vulnerable pins (cryptography, Jinja2) and 4 code
defects (weak crypto twice, unsafe deserialization, SQL injection). From the receipted SARIF (issue 392):

| tool | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|
| semgrep | 5 | 3 | 4 | 0.625 | 0.556 | 0.588 |
| gitleaks | 3 | 0 | 6 | 1.0 | 0.333 | 0.5 |
| trivy | 3 | 0 | 6 | 1.0 | 0.333 | 0.5 |
| grype | 2 | 0 | 7 | 1.0 | 0.222 | 0.364 |
| osv-scanner | 2 | 0 | 7 | 1.0 | 0.222 | 0.364 |

Read per detector, the low recalls are mostly scope, not failure: gitleaks found all three credentials and nothing
else, Grype and OSV-Scanner found both pins and nothing else - inside its own class each of these three has precision
1.0 and recall 1.0. Trivy found both pins and one of the three credentials (its secret scanner missed `backup.sh` and
`search.py`), again with no false positive. Semgrep is the only one that looks at code, and it is both
the best and the noisiest: it found three of the four code defects and two credentials, but all three of its false
positives are the set's decoys - SHA-1 in `etag.py`, which the docstring calls "a content fingerprint, not a security
control", and two rules on `ticket_counts.py` line 8, a `%d` format whose argument is already `int(team_id)`. The
rule cannot see the cast or the purpose; only the key can.

**What I would gate on.** gitleaks and Trivy, exactly as this pipeline does: on this set they never raised a false
alarm, so a red build always means something real, and a gate that is wrong one time in three (Semgrep's 3 of 8
distinct findings) teaches people to ignore red. Grype and OSV-Scanner add nothing over Trivy here (the same two
pins), so they stay as second opinions in the Security tab. Semgrep stays report-only, triaged by a person, as in
`TRIAGE.md`; with project rules of my own (Stretch 3) its precision on my code would be higher than with
`p/default`.

**What none of the five found.** `app/reset_tokens.py` line 10 builds password-reset tokens with `random.choice`, a
predictable generator where `secrets` is required (weak-crypto, CWE-338). It is a security bug that reads like
ordinary code: no scanner rule fired on it, so all five together found 8 of 9 defects. And every recall above is an
upper bound: these are seeded defects, written to be findable, and real defects are found several times less often.
