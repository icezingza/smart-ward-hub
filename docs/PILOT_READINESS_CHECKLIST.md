# Smart Ward Hub — Pilot Readiness Checklist

**Rule:** Any `BLOCKED` item prevents pilot start. Any `UNVERIFIED` item requires an owner, evidence date and explicit risk acceptance; it must not be silently treated as passed.

| Gate | Required evidence | Owner | Status |
|---|---|---|---|
| Product boundary | Approved `PRODUCT_BOUNDARY.md`, intended use and exclusions | Product + clinical | BLOCKED |
| Site and buyer | Design-partner agreement, named site/buyer/clinical owner | Commercial | BLOCKED |
| User workflow | Current-state map, training plan, usability walkthrough | Clinical/product | BLOCKED |
| Identity | OIDC test tenant, scope matrix, credential rotation/revocation test | Security/IT | BLOCKED |
| Transport | TLS/mTLS topology, certificate lifecycle and network segmentation plan | Security/IT | BLOCKED |
| Data protection | Data-flow/PII map, retention, access, backup encryption and restore result | Security/quality | BLOCKED |
| Risk management | Hazard analysis, risk controls traced to requirements/tests, stop conditions | Quality/clinical | BLOCKED |
| Software release | Versioned artifact, CI pass, dependency/SBOM report, migration/rollback result | Engineering | BLOCKED |
| Hardware | Approved device/firmware list, fixture, serial/BLE/Wi-Fi bench results | Edge engineering | BLOCKED |
| HIS sandbox | Admission/FHIR contract, retry/idempotency/reconciliation evidence | Integration | BLOCKED |
| Operations | Runbook, monitoring, incident escalation, on-call and support contact | Operations | BLOCKED |
| Clinical governance | Protocol, training, alert review, adverse-event and stop procedure | Clinical owner | BLOCKED |
| Privacy/legal | Data controller, processing basis, agreements and local review | Legal/privacy | BLOCKED |
| Evidence boundary | Software, bench, pilot and clinical evidence separated | Quality | BLOCKED |

## Pilot acceptance metrics

Define numerical thresholds before collecting results. At minimum track telemetry acceptance/error rate, offline duration and recovery time, duplicate/replay rejection, alert acknowledgement latency, operator workload, unresolved incident count, backup restore time, HIS reconciliation success and privacy/security incidents.

Do not change a threshold after seeing results without recording a versioned rationale, risk review and approval. A simulation result is not a substitute for a pilot result.

## Start decision

The pilot owner may start only when every blocking gate has evidence or a formally approved exception with expiry, containment and stop authority. The decision record must include release commit, environment configuration fingerprint without secrets, hardware/firmware versions, test window, named operators and rollback procedure.

## Stop and rollback triggers

Stop immediately for raw patient identifier leakage, authentication bypass, audit-integrity failure, unsafe destructive action, unreconciled data loss, unknown device identity, repeated alert failure, untrained operator use, or any event that cannot be contained and reviewed by the clinical owner.
