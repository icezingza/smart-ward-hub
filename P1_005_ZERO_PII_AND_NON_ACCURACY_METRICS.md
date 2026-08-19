# P1-005 — Zero-PII Boundary and Non-Accuracy Metrics

**Status:** Software contract strengthened; clinical and privacy governance approval pending

## Zero-PII token boundary

The shadow-mode record accepts an opaque `patient_token` only. The current validator requires a bounded token composed of safe identifier characters and rejects direct `HN`, `AN`, `MRN` or `NATIONAL_ID` markers. It also rejects those identity markers in `alert_id`, `device_id`, `bed_no` and free-text `context`, and limits context to 512 characters to reduce accidental data capture.

This is a software input boundary, not a claim that all upstream, operator, host, backup or external integration channels are free of personal data. Before real clinical validation, the hospital must verify token issuance, mapping custody, logs, exports, backups, screenshots, crash dumps, network traces and retention controls.

## Shadow record minimum fields

| Field | Allowed role | Boundary |
|---|---|---|
| `patient_token` | Pseudonymous join key | Must not be raw HN/AN/MRN/National ID; mapping remains outside Edge |
| `device_id` | Device context | Must not carry patient identity; must be inventory-controlled |
| `bed_no` | Operational location context | Must be minimized to the approved ward scope |
| `event_time` / `received_at` | Timing and freshness | Used for latency/freshness review, not clinical efficacy claims |
| `signal_type` | Non-diagnostic signal label | Limited to suspected fall, vital anomaly signal, device/perimeter warning |
| `context` | Bounded operational context | No raw identity markers; maximum 512 characters |

## Non-accuracy metrics

These metrics describe workflow and data quality. They must not be presented as sensitivity, specificity, positive predictive value, negative predictive value, clinical accuracy or patient-outcome evidence.

| Metric | Definition | Required denominator / caveat |
|---|---|---|
| `signal_count` | Number of unique shadow alert IDs recorded | Only counts accepted software records |
| `reviewed_count` | Number of signals with a reviewer classification | Review completeness must be reported alongside it |
| `review_coverage` | `reviewed_count / signal_count` | Not a quality score; low coverage invalidates event-rate interpretation |
| `unreviewed_signal_count` | `signal_count - reviewed_count` | Must be surfaced rather than silently excluded |
| `true_positive_count` | Reviewer-labelled `TRUE_POSITIVE` count | Reviewer classification, not clinical ground truth |
| `false_positive_count` | Reviewer-labelled `FALSE_POSITIVE` count | Requires consistent review rubric |
| `missed_event_count` | Reviewer-labelled `MISSED_EVENT` count | Denominator depends on independent observation capture |
| `confirmed_event_rate_over_reviewed` | `true_positive_count / reviewed_count` | Not sensitivity, PPV or clinical accuracy |
| `false_positive_review_rate_over_reviewed` | `false_positive_count / reviewed_count` | Alarm-burden review signal only |
| `mean_data_freshness_seconds` | Mean `received_at - event_time` | Separates device/network delay from clinical response |
| `mean_acknowledge_seconds` | Mean acknowledgment time from receipt | Not clinical response time automatically |
| `mean_resolve_seconds` | Mean resolution time from receipt | Requires clear operator ownership and clock semantics |

## Review and stop rules

Every `TRUE_POSITIVE`, `FALSE_POSITIVE`, `MISSED_EVENT`, `INDETERMINATE` and `DEVICE_DATA_FAULT` classification requires an independent reviewer ID and a written reason. Duplicate reviews are rejected. Reviews before signal receipt are rejected. Critical privacy leakage, identity mismatch, alert flood, serious missed event, recovery failure, premature purge or operator misinterpretation must stop the shadow run and create an incident record.

## Claim boundary

The current evidence supports **software verification of a shadow-mode governance contract and workflow/data-quality metrics**. It does not support clinical efficacy, diagnostic performance, patient safety effectiveness, alarm-fatigue conclusions, regulatory compliance or a decision to use the system with real patients.
