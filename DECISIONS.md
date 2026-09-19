---
svcdesk_decisions:
  C1: wallclock      # wallclock | business
  C2: immutable      # reopen | immutable
  C3: vip            # matrix | vip
---
<!-- ai-generated: 80% - Claude Code drafted the prose from the chosen values; the student chose the three resolutions -->

# Decisions

## C1 - SLA clock for P1

**Decision:** Both P1 targets (acknowledge within 15 minutes, resolve within 4 hours) run on the wall clock,
around the clock, exactly as R-14 asks. P2, P3 and P4 keep the business-hours clock of R-13 (Monday to Friday,
08:00 to 16:00 Europe/Warsaw), so a P3 raised on Friday afternoon is due on the following business days. The
running service reproduces the "wall-clock" columns of the T1..T8 vectors for P1 and the "business" columns for
every other priority.

**Rejected alternative:** `business`: every priority, P1 included, pauses outside business hours, so a P1 raised
on Friday at 17:00 is not late until Monday at 08:15. We rejected it because it silently turns "the whole
organisation has stopped working" into a Monday-morning problem, which is the one outcome R-14 was written to
prevent.

**Reason:** R-13 and R-14 cannot both hold for P1, and R-14 is the more specific rule: it names P1 explicitly and
gives the Friday-evening example, while R-13 states the general default. A P1 can only come from impact 1 and urgency 1
(the VIP floor never produces one), so it always means the organisation has stopped; a target that pauses
for the weekend would make the Monday report say "on time" about an outage nobody looked at for 60 hours. The cost
is that an on-call arrangement must exist for P1 alone; that is a smaller and more honest cost than reporting a
weekend outage as within target.

**Service owner:** The Service Desk manager (the owner of the SLA catalogue and of the on-call rota) signs this
off, because the decision commits the desk to a 24/7 acknowledgement duty for P1 and only that role can promise
the staffing that makes the target real rather than a number in a report.

**Customer outcome:** A reporter whose whole organisation has stopped gets a desk that is measurably late within
15 minutes, at any hour, so the outage is escalated on Friday night instead of being discovered on Monday; teams
and individuals with lower priorities are measured only against the hours in which the desk actually works.

## C2 - Closed tickets and reopening

**Decision:** A closed ticket is immutable (R-09): `POST /tickets/{id}/reopen` on a closed ticket answers 409
regardless of its age, and further work on the same issue needs a new ticket that references the closed one via
`related_to`. Reopening remains possible from `resolved` within 7 days of `resolved_at` (R-10 and R-11), returns
the ticket to `in_progress`, clears `resolved_at` and `closed_at`, and never changes `resolve_due_at`.

**Rejected alternative:** `reopen`: a closed ticket can also be reopened within 7 days of `closed_at`. We rejected
it because closure is, by R-07, the moment the reporter confirmed the fix; letting the same record flip back
afterwards makes the closed-ticket count and the resolution history of the desk unstable and unreportable.

**Reason:** R-09 and R-10 contradict each other only for the closed state, and the `resolved` state already gives
the reporter the 7-day window R-10 asks for: a fix that did not work is noticed while the ticket is resolved and
waiting for confirmation, and reopen is allowed then. Once the reporter has confirmed and the ticket is closed,
a new problem is a new ticket; `related_to` keeps the link, so nothing is lost for the agent, and the monthly
report can rely on closed meaning closed. Immutability also removes a whole class of audit questions about a
ticket whose closure timestamp was later erased.

**Service owner:** The Service Desk process owner (the role accountable for the incident lifecycle and the
desk's reporting) signs this off, because the decision defines when an incident record is final and how
recurrences are linked, which is a process rule rather than a technical one.

**Customer outcome:** A reporter who confirmed the fix too early still gets help: they raise a new ticket that
points at the old one, the agent sees the history at once, and the organisation keeps reports in which a closed
ticket stays closed and the count of reopened work is honest.

## C3 - VIP reporters and the priority matrix

**Decision:** The matrix of R-04 is computed first; then a ticket whose reporter has `vip: true` and lands at P3
or P4 is raised to P2 (R-06). P1 and P2 are unchanged, so a VIP ticket at impact 1, urgency 1 stays P1. A
`priority` field in the request body is ignored under every circumstance (R-05 still holds for clients: nobody
can request a priority; only the stored VIP flag of the reporter changes it).

**Rejected alternative:** `matrix`: `reporter.vip` is stored but never affects priority, so a VIP cosmetic issue
is a P4 like everyone else's. We rejected it because R-06 states an explicit business rule with a stated purpose
(executive issues are visible immediately), and dropping it would make the flag decorative while the desk would
still be asked, informally, to jump on those tickets.

**Reason:** R-05 says priority comes from impact and urgency "and from nothing else" and forbids requesting a
priority; R-06 asks for a VIP floor. The floor is not a request: neither the reporter nor the agent can choose a
priority, and the VIP flag is a property of the reporter that the desk controls. Capping the floor at P2 keeps P1
reserved for real organisation-wide outages, so the incident manager's escalation path is not flooded by
executive convenience, while P2 (one hour to acknowledge, eight business hours to resolve) makes the ticket
visible on the same day.

**Service owner:** The Service Desk manager, together with the Service Level manager who owns the SLA
catalogue, signs this off: the decision spends desk capacity on a small group of reporters and changes the
reported P2 volume, which is a service-level trade-off that only the owner of the SLA agreement can make.

**Customer outcome:** An executive reporter gets a desk response within one business hour even for a small
problem, and the rest of the organisation keeps P1 meaning "everyone has stopped", so a real outage is never
queued behind a VIP's cosmetic issue.
