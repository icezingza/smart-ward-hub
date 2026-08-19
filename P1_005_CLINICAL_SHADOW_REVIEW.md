# P1-005 — Clinical Shadow-Mode Detailed Review

**Review scope:** `clinical_shadow_mode.py`, `test_clinical_shadow_mode.py`, `test_clinical_shadow_mode_negative.py`, `CLINICAL_SAFETY_SHADOW_MODE.md`
**Review classification:** software/governance contract review; not clinical validation

## Code-path review

| Code area | Current control | Result |
|---|---|---|
| `ShadowModePolicy.validate()` | Named owners, backup/restore evidence, device inventory, training, retention, rollback and approval ID | Implemented in software contract |
| `ShadowModeController.activate()` | Rejects incomplete policy and workflow-changing notifications | Implemented; external approval still required |
| `ShadowSignal.validate()` | Opaque token, raw identity marker rejection, context length bound, safe signal label and event/received ordering | Implemented and covered by positive/negative tests |
| `ShadowReview.validate()` | Allowed classifications, reviewer/reason requirement and timestamp ordering | Implemented; controller adds signal-receipt ordering and duplicate-review rejection |
| `ShadowModeController.stop/resume()` | Incident ID/reason required; intake stops until explicit resume approval | Implemented in software contract |
| `metrics()` | Review coverage, unreviewed count, event labels, freshness, acknowledgement and resolution timing | Implemented as non-accuracy workflow/data-quality metrics |

## Additional test results

| Test group | Coverage | Result |
|---|---|---|
| Existing baseline | Activation, safe labels, raw HN rejection, classifications, metrics, stop/resume | Passed |
| Negative matrix | Notification gate, raw HN in context, oversized context, invalid time, diagnostic label, duplicate signal/review | Passed |
| Metric semantics | Explicit `*_over_reviewed` names, unreviewed count and zero-denominator behavior | Passed |
| P1-006 preflight | Missing-gate block, complete external-review readiness, self-asserted clinical evidence rejection | Passed |

## Zero-PII boundary assessment

The current validator protects the shadow-record entry point by requiring a bounded opaque token and rejecting common raw identity markers in the token and operational fields. This is necessary but not sufficient. Before real validation, the hospital must also review upstream tokenization, mapping custody, database backups, audit logs, exports, screenshots, crash dumps, network traces, telemetry payloads, support bundles and data-retention deletion behavior.

A software regex is not a proof of privacy compliance. The correct claim is **software input boundary verified for the tested markers**, not zero risk of personal-data exposure across the whole deployment.

## Non-accuracy metrics assessment

Metrics are explicitly labelled `SHADOW_REVIEW_METRICS_NOT_CLINICAL_ACCURACY`. `confirmed_event_rate_over_reviewed` and `false_positive_review_rate_over_reviewed` are proportions of reviewer-labelled records only. They are not sensitivity, specificity, PPV, NPV, clinical accuracy or patient-outcome evidence. `review_coverage` and `unreviewed_signal_count` must be reported beside any rate so incomplete review cannot appear authoritative.

Freshness, acknowledgement and resolve time describe data/workflow timing. They must not be described as clinical response time or clinical effectiveness without a separate approved study design.

## Residual risks

Clinical owner, governance approval, consent or waiver, human-factors review, alarm-fatigue review, independent event adjudication, inclusion/exclusion criteria, real device qualification, HIS/IdP/transport validation and real-world incident handling remain open. P1-005 therefore remains **In Progress** and **clinical validation pending**.
