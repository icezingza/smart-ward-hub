# Smart Ward Hub — P1-005 Clinical Shadow-Mode Contract

**Status:** Software safety/governance contract implemented; clinical governance approval pending

## Purpose and boundary

P1-005 defines how Smart Ward Hub can be evaluated in a non-interventional shadow mode. The system may compute and record **suspected fall**, **vital anomaly signal** and **device/perimeter warning**, but it must not diagnose, prescribe treatment, replace hospital vital-sign measurement or issue a treatment order.

The software contract is a governance gate, not a clinical protocol. A qualified clinical owner and the hospital's approved safety process must determine whether, where and how any real-world shadow evaluation may occur.

## Activation gates

Shadow mode cannot activate until the policy records a clinical owner, technical owner, privacy/security reviewer, ward manager, incident contact, backup/restore evidence, device inventory, training note, data-retention decision, rollback plan and governance approval ID. Notifications are disabled by default. Enabling a workflow-changing notification requires a separate approved change and is rejected by the current baseline.

## Review model

Each signal is stored with pseudonymous patient token, device, bed context, event time, received time and non-diagnostic context. Review classifications are `TRUE_POSITIVE`, `FALSE_POSITIVE`, `MISSED_EVENT`, `INDETERMINATE` and `DEVICE_DATA_FAULT`. Review reasons and reviewer IDs are required. The metrics report review coverage, event counts, data freshness, acknowledgement time and resolve time, but labels itself `SHADOW_REVIEW_METRICS_NOT_CLINICAL_ACCURACY`.

## Stop and resume

A stop event requires an incident ID and reason and changes the controller to `STOPPED`. New signal intake is blocked until a separate resume approval ID is supplied. Stop conditions include privacy leakage, identity mismatch, duplicate pairing, sequence corruption, persistent recovery failure, alert flood, serious missed event, premature FHIR purge or operator misinterpretation of a signal as a treatment instruction.

## Evidence

`clinical_shadow_mode.py` and `test_clinical_shadow_mode.py` provide deterministic software verification for policy completeness, safe labels, Zero-PII token boundaries, review classification, non-accuracy metrics and stop/resume behavior. They do not measure sensitivity, specificity, clinical effectiveness, alarm fatigue, human factors or patient outcomes.

## Gate status

P1-005 remains **Pending clinical governance approval**. Before any limited pilot, the project needs an approved clinical protocol, named accountable owners, staff walkthrough/training, data-retention decision, incident/escalation path, manual fallback, independent review of false positives and missed events, and signed change/rollback controls.
