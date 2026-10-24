---
lab4_comms:
  awareness: 2026-10-12T07:12:00Z
  detection: 2026-10-12T07:09:19Z
  classification: 2026-10-12T08:00:00Z
  nis2:
    early_warning_due: 2026-10-13T07:12:00Z
    notification_due: 2026-10-15T07:12:00Z
    notification_sent: 2026-10-13T09:00:00Z
    final_report_due: 2026-11-13T09:00:00Z
  ksc:
    early_warning_due: 2026-10-13T07:09:19Z
    notification_due: 2026-10-15T07:09:19Z
    notification_sent: 2026-10-13T09:00:00Z
    final_report_due: 2026-11-13T09:00:00Z
  dora:
    initial_due: 2026-10-12T12:00:00Z
    initial_sent: 2026-10-12T11:00:00Z
    intermediate_due: 2026-10-15T11:00:00Z
    intermediate_sent: 2026-10-14T10:00:00Z
    final_due: 2026-11-14T10:00:00Z
  log:
    - {at: 2026-10-12T11:00:00Z, to: the financial supervisor, what: DORA initial notification}
    - {at: 2026-10-12T12:00:00Z, to: the CSIRT, what: NIS2 and KSC early warning}
    - {at: 2026-10-13T09:00:00Z, to: the CSIRT, what: NIS2 and KSC incident notification}
    - {at: 2026-10-14T10:00:00Z, to: the financial supervisor, what: DORA intermediate report}
---
<!-- ai-generated: 70% - the three instants and the sending times are my decisions; Claude Code did the deadline arithmetic and drafted the prose -->

# Communications log: the regulators' clocks

The shop is assumed to fall under NIS2, the Polish KSC act and DORA at once, with this incident significant under the
first two and major under the third. Every instant is UTC; the incident is the one of `postmortem.md`, on Monday
12 October 2026.

## The three instants you defend

**Detection (KSC), 07:09:19Z.** KSC counts "od momentu jego wykrycia", from the moment of detection, and the incident
was detected when ShopCheckoutErrors fired and paged the on-call at 07:09:19Z (MTTD 214 s after the onset). That is
the first moment anyone in the organisation had a signal; it does not wait for a human to understand it, so it is
the earliest and most conservative of the three clocks: the KSC early warning is due at 07:09:19Z on Tuesday.

**Awareness (NIS2), 07:12:00Z.** NIS2 starts its clock when the entity "becomes aware" of a *significant* incident,
which needs more than a page: someone must know that users are affected. At 07:10:07Z the on-call acknowledged the
ticket; by about 07:11 the AI-assisted investigation had shown that the checkout errors came from the product
catalog (H2, 0.096 failed GetProduct calls per second), that orders were being lost and that product pages failed
too. At 07:12:00Z, with that impact on paying customers clear, the on-call judged the incident significant. Claiming
a later instant would only be safe if it could be defended, and here it could not: nothing more was learned after
07:12 that changed the judgement.

**Classification (DORA), 08:00:00Z.** Classifying a major ICT-related incident applies the criteria of the DORA
technical standard (clients affected, duration, reputational and economic impact, critical services), which is a
deliberate decision of the incident manager, not of the on-call alone. With the incident over at 07:12:19Z and the
postmortem numbers at hand (about 2 of 64 orders failed, 4 % of front-end requests), the classification meeting at
08:00:00Z is less than an hour after awareness, a realistic and defensible delay.

## The log

| when (UTC) | to | what | which clock |
|---|---|---|---|
| Mon 2026-10-12 11:00 | the financial supervisor | DORA initial notification | due 12:00: classification + 4 h, earlier than awareness + 24 h (Tue 07:12) |
| Mon 2026-10-12 12:00 | the CSIRT | NIS2 and KSC early warning | due Tue 07:09:19 (KSC, detection + 24 h) and Tue 07:12 (NIS2, awareness + 24 h) |
| Tue 2026-10-13 09:00 | the CSIRT | NIS2 and KSC incident notification | due Thu 07:09:19 (KSC) and Thu 07:12 (NIS2), + 72 h; final reports due one month later, 2026-11-13 09:00 |
| Wed 2026-10-14 10:00 | the financial supervisor | DORA intermediate report | due Thu 11:00, initial + 72 h; the final report is due 2026-11-14 10:00 |

The DORA initial notification goes first, an hour before its deadline, because DORA's 4-hour clock is the shortest
one. The early warning to the CSIRT goes out the same day, well inside both 24-hour clocks, so that neither depends
on the other: KSC's runs from detection and is three minutes earlier than NIS2's. The full notification follows the
next working morning, when the postmortem's numbers are checked, still two days before its 72-hour deadline.
