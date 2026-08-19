# Smart Ward Hub — Product Requirements Document

**Document role:** AI-readable product contract and decision boundary  
**Product status:** Controlled production prototype; P0-hardened software baseline; pilot-ready foundation; clinical validation pending

## 1. Product definition

Smart Ward Hub is a **Sovereign Edge-first Patient Monitoring Platform** for ward-local telemetry ingestion, safety-oriented decision support, device/session workflow, evidence preservation and HIS/EMR interoperability. The Fixed Edge Hub remains useful during WAN/HIS interruption while maintaining a narrow, Zero-PII data boundary.

The product is not an autonomous diagnostic system, not a replacement for clinical judgment, and not proof of regulatory compliance. Every clinical-facing capability must remain human-reviewed and subject to clinical validation.

## 2. Product differentiators

The product must preserve these differentiators in every future change:

| Differentiator | Required product behavior |
|---|---|
| Sovereign Edge / Offline-first | Keep local operational truth and safety evaluation at the ward edge; tolerate WAN/HIS interruption with visible freshness and sync state |
| Zero-PII by design | Accept only opaque `patient_token`/`encounter_token` at Hub Core; never store raw HN, name or identity mapping on Edge |
| Patient Safety Intelligence | Provide explainable, human-reviewed triage/fall signals and safe alert lifecycle; never diagnose or silently suppress alerts |
| Tamper-Evident Evidence | Preserve hash-linked forensic packages, freeze unresolved incidents and verify local integrity; external anchoring remains a validation gate |
| HIS/EMR Interoperability | Use an explicit Admission Gateway and FHIR/acknowledgement contract with idempotency and safe retention/purge |
| Device Trust & Secure Provisioning | Verify registered device identity, canonical signed telemetry, sequence/replay protection and credential lifecycle |
| Outside-in Ward Workflow | Allow controlled admission preparation from outside the ward while keeping Edge authority and Zero-PII |
| Sovereign Ward Operating Layer | Support managed roaming clients as thin authenticated views/command clients, never as another source of truth |

## 3. Functional requirements

### FR-001: Edge ingestion

The Hub shall accept the locked `TelemetryPacket v1` contract, reject malformed or legacy identity fields, enforce per-device monotonic sequence and persist or buffer data according to configured durability rules.

### FR-002: Authentication and authorization

The Hub shall fail closed when authentication is not configured, enforce scope-based authorization and support a migration path from development static tokens to production OIDC/JWT and mTLS configuration.

### FR-003: Device Trust

The Hub shall support public-key enrollment, canonical signed telemetry verification, credential states (`ACTIVE`, `SUSPENDED`, `REVOKED`, expired), observe/enforce modes and audit evidence without storing private keys.

### FR-004: Patient safety workflow

The Hub shall preserve alert acknowledgement, incident freeze, `RESET_PENDING`, hot-swap, discharge and handover safety gates. A roaming client shall not execute destructive `RESET_CONFIRM` in the initial pilot.

### FR-005: Outside-in admission

The system shall expose non-PII bed availability and idempotent admission preparation. Raw HN/AN must be tokenized before crossing into Hub Core.

### FR-006: Evidence and interoperability

The system shall generate handover/FHIR bundles, retain local aggregates on failed sync, permit purge only after verified acknowledgement, and maintain tamper-evident forensic linkage.

### FR-007: Operations

The system shall expose health, audit, backup, recovery and configuration evidence while separating software simulation results from real hardware, hospital integration and clinical validation evidence.

## 4. Non-functional requirements

| Area | Requirement |
|---|---|
| Privacy | Zero-PII Edge boundary; redact audit/evidence output |
| Availability | Local operation during connectivity interruption; visible stale/offline state |
| Integrity | Hash chain, sequence/replay checks, idempotent commands and migration discipline |
| Performance | Bounded memory and concurrency behavior; benchmark values must be labelled software simulation unless hardware-tested |
| Recovery | WAL-aware backup, atomic checkpoint and documented power-loss/storage recovery |
| Security | Fail-closed auth, least privilege, rate limiting, Device Trust and explicit approval for side effects |
| Operability | Fixed Hub source of truth, optional thin roaming client, reproducible runbooks and evidence |

## 5. Safety and claim boundaries

The approved language is **functional verification passed**, **controlled production prototype**, **pilot-ready foundation**, **clinical validation pending** and **pilot deployment configuration pending**. Do not claim `clinical-ready`, `production-ready`, `tamper-proof`, `100% HIPAA compliant` or `100% PDPA compliant` from software tests alone.

## 6. Current acceptance state

Functional software regression for Phases 1–6, Device Trust, ward workflow, Outside-in Admission and roaming synchronization has passed according to the project test runner. Real OIDC/mTLS, Acer hardware, power-loss, network, HIS, key custody, external WORM anchoring and clinical validation remain open gates.

## 7. Source documents

Use `EDGE_HUB_ARCHITECTURE.md`, `SECURITY_BASELINE.md`, `WARD_WORKFLOW_CONTRACT.md`, `OUTSIDE_IN_WARD_WORKFLOW.md`, `ROAMING_TABLET_ARCHITECTURE.md`, `PRODUCT_DIFFERENTIATORS.md`, `RISK_REGISTER.md` and `NEXT_PHASE_PRIORITY_MATRIX.md` for detailed contracts and evidence.
