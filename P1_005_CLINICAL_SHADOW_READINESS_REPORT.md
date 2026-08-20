# P1-005 Clinical Shadow-Mode Readiness Report

**Decision:** `SHADOW_MODE_SOFTWARE_PREPARATION_READY`
**Shadow execution:** `NOT_STARTED`
**Clinical governance:** `PENDING`
**Clinical validation:** `PENDING`
**Real-world authorization:** `false`
**Product status:** `NOT_PRODUCTION_READY`

## Scope and safety boundary

P1-005 hardens a non-interventional software shadow-mode contract. The system may record approved non-diagnostic labels such as **suspected fall**, **vital anomaly signal** and **device/perimeter warning**. It must not diagnose, prescribe treatment, replace hospital vital-sign measurement or issue a treatment order.

The software contract is not a clinical protocol and does not authorize real-world evaluation. Clinical governance, named accountable owners, staff training, manual fallback, incident escalation and data-retention decisions remain external prerequisites.

## Software-preparation tracks

| Track | Software control | External evidence still required |
|---|---|---|
| SM-001 | Activation requires named owners, operational prerequisites and governance approval reference | Clinical owner appointment, governance sign-off and accountable escalation |
| SM-002 | Approved non-diagnostic vocabulary; diagnostic/treatment labels rejected | Clinical wording and human-factors review |
| SM-003 | Bounded opaque token, raw-marker/context/secret filtering and explicit limited privacy claim | Upstream tokenization, logs, backups, exports, crash dumps, traces and retention review |
| SM-004 | Reviewer, classification, reason and event/received/review timestamp ordering | Independent adjudication and approved review protocol |
| SM-005 | Review coverage, unreviewed count and denominator-labelled workflow/data-quality metrics | Approved analysis plan and complete reviewed dataset |
| SM-006 | Incident stop blocks new intake until separate resume approval | Clinical escalation and manual-fallback drill |
| SM-007 | Workflow-changing notifications remain disabled; change/threshold/rollback boundary remains explicit | Signed change-control and rollback record |

## Hardening changes

The runtime contract now rejects non-string and unsafe owner/reference fields, raw identity/contact/secret markers, non-boolean governance flags, naive timestamps, invalid signal/reviewer fields, duplicate activation, invalid lifecycle transitions, unapproved stop/resume references and metrics calls with naive timestamps. Metrics continue to expose `unreviewed_signal_count` and `*_over_reviewed` rates and remain labelled `SHADOW_REVIEW_METRICS_NOT_CLINICAL_ACCURACY`.

The readiness manifest and strict schema keep `shadow_execution=NOT_STARTED`, `clinical_governance=PENDING`, `clinical_validation=PENDING`, `real_world_authorization=false`, `notification_mode=DISABLED`, `software_evidence_only=true` and the authorization boundary locked.

## Verification

The phase-end gate runs the existing contract regression, existing negative regression and the new adversarial suite. The adversarial suite covers readiness field mutations, policy type/reference/activation errors, raw PII and secret markers, naive timestamps, duplicate signals, review identity/time errors, zero-denominator metric semantics, stop/resume misuse and no-accuracy claim preservation. It also performs template/schema validation, private-key marker scanning and `git diff --check`.

All results are **software verification**. The Zero-PII statement is limited to the tested input marker boundary and is not system-wide privacy proof. The metrics are workflow/data-quality metrics and must not be described as sensitivity, specificity, PPV, NPV, clinical accuracy, clinical effectiveness or patient-outcome evidence.

## External gate boundary

P1-005 remains pending clinical governance approval. Before any real-world shadow evaluation or limited pilot, the project still needs an approved protocol, named clinical and operational owners, consent/waiver decision where applicable, staff walkthrough, human-factors and alarm-fatigue review, manual fallback, independent event review, retention/deletion decision, signed change/rollback control and external authorization.
