# Smart Ward Hub — Pilot Readiness Report

**Assessment date:** 19 August 2026  
**Assessment scope:** Smart Ward Hub software and Edge runtime in the sandbox environment  
**Decision:** **Pilot-ready foundation with conditions; not clinical production-ready**

> This is an engineering readiness assessment, not a medical diagnosis or clinical opinion. Qualified clinical, security, privacy and governance owners must approve consequential decisions.

## Executive decision

Smart Ward Hub has passed the functional regression suite for the existing Levels 1–6 flows and the new Edge hardening checks. The implementation now has a Zero-PII direction, a locked TelemetryPacket v1 contract, thread-safe bounded buffering, sequence protection, atomic checkpoint recovery, process-local rate limiting, request IDs, structured audit events with redaction, handover idempotency, security headers, TrustedHost protection, fail-closed authentication, FHIR acknowledgment rules, local forensic anchoring, and pilot documentation.

The system should be classified as a **controlled production prototype** and may proceed to a laboratory or shadow-mode pilot only after the stated owners approve the remaining conditions. The evidence does not establish clinical performance, hardware durability, battery life, radio reliability, regulatory compliance, or legal admissibility of forensic records. **Clinical validation pending** remains the correct status.

## Evidence summary

| Evidence | Result | Classification |
|---|---|---|
| Level 1 pairing and SQLite/WAL tests | Passed | Implemented functional evidence |
| Level 2 telemetry and aggregation tests | Passed | Implemented functional evidence |
| Level 3 triage tests | Passed | Prototype algorithm evidence; clinical performance unverified |
| Level 4 forensic tests | Passed | Local tamper-evident evidence |
| Level 5 FHIR/handover tests | Passed | Contract and acknowledgment simulation |
| Security baseline and fail-closed tests | Passed | Baseline API security evidence |
| Edge runtime tests | Passed | PII guard, overflow, ordering, recovery evidence |
| Residual-control regression | Passed | Rate limit, replay, audit redaction, anchor and single-purge idempotency evidence |
| Device Trust enforce/observe regression | Passed | Ed25519 enrollment, signed v1 telemetry, mutation rejection, replay, revocation and observe continuity |
| Device Trust Alembic migration | Passed | Clean-database upgrade reaches migration head |
| Ward workflow regression | Passed | Opaque admission boundary, NFC pointer, RESET_PENDING, hot-swap, discharge and incident freeze |
| Outside-in admission regression | Passed | Non-PII bed availability, reservation, expiry, idempotent handoff, pairing commit and release |
| Roaming Tablet synchronization regression | Passed | Non-PII snapshot cursor, stale revision conflict, acknowledgement idempotency, reset safety gate and audit |
| Roaming command Alembic migration | Passed | Clean-database upgrade reaches `7b8c9d0e1f22` head |
| Outside-in Alembic migration | Passed | Clean-database upgrade reaches `6a7b8c9d0e11` head |
| Ward workflow Alembic migration | Passed | Clean-database upgrade reaches `4f1a2c7d8e90` head |
| 30-device / 600-request reliability harness | Passed | Software-only validation |
| Hardware validation | Not performed | Open gate |
| Clinical validation | Not performed | Open gate |
| Real HIS/EMR integration | Not performed | Open gate |

## Measured reliability result

The reliability harness used 30 simulated devices, 20 ordered packets per device, and 600 total API requests. All requests returned HTTP 200 during the ordered-stream test. Observed per-request latency was p50 **227.988 ms**, p95 **690.216 ms**, p99 **926.509 ms**, maximum **1,215.514 ms**, and mean **294.112 ms**. The complete concurrent stream took **6,435.372 ms** wall-clock time in this environment.

The harness also passed duplicate sequence rejection, unpaired-device rejection, untrusted Host rejection, and checkpoint recovery. These values are measurements of the sandbox software harness only. They are not a throughput or latency guarantee for wearable hardware, hospital Wi-Fi, battery behavior, or clinical response time.

## Acceptance gates

| Gate | Status | Required condition before real pilot |
|---|---|---|
| G1 Contract and Zero-PII | **Passed for software baseline** | Run static/log/checkpoint scan on the pilot image and downstream exports |
| G2 Authentication and host boundary | **Passed for baseline** | Deploy OAuth2/OIDC, secret rotation, TLS/mTLS and network firewall controls |
| G3 Edge reliability | **Passed in software harness** | Execute power-loss, disk-full, clock-drift, Wi-Fi-loss and hardware load tests |
| G4 Clinical safety | **Open** | Clinical governance approval and shadow-mode review protocol |
| G5 HIS/EMR integration | **Open** | Test tenant, FHIR profile validation, real acknowledgment and retry/idempotency tests |
| G6 Operations | **Partially ready** | Assign owners, escalation contacts, backup/restore drill and rollback rehearsal |
| G7 Evidence preservation | **Baseline passed** | External anchor, protected key custody and trusted timestamp before evidence claims |
| G8 Residual controls | **Passed for software baseline** | Calibrate rate limits and verify coordinated limits/audit delivery if deployment uses multiple processes or nodes |

## Required conditions

The pilot must begin in a test or shadow environment, not as an autonomous clinical decision system. Every alert must be presented as a decision-support signal. The ward must retain an independent clinical workflow, and a designated reviewer must classify signals as true positive, false positive, missed event, indeterminate, or device/data fault.

The HIS/EMR integration must not purge local data until the remote system returns a validated acknowledgment matching the Bundle ID and idempotency key. Failed delivery must retain data and enter retry or dead-letter handling.

The pilot operator must use the runbook and record daily data freshness, buffer pressure, dropped samples, unresolved alerts, sync failures, security failures, backup status and incidents. Expansion beyond the first limited ward requires a signed review of these records.

## Residual risks

The highest residual risks are clinical false negatives/false positives, static-token deployment if OAuth2/OIDC is not completed, lack of real mTLS and key custody, local-only forensic anchoring, process-local state topology, incomplete power-loss testing, and unknown behavior of actual wearable hardware and hospital networks. Rate limiting and audit controls are implemented for the single-process Edge owner model but still need deployment-topology calibration and, if required, coordinated enforcement.

These risks are documented in `RISK_REGISTER.md`. They are not eliminated by a passing software regression suite.

## Recommended next decision

Approve a **laboratory and shadow-mode pilot only**, with a limited device count and explicit stop conditions. Do not approve autonomous clinical use, production HIS write-back, or marketing claims of clinical accuracy until the open gates are closed by the relevant technical, security, privacy, clinical and governance owners.

## Delivered artifacts

| Artifact | Purpose |
|---|---|
| `PILOT_READINESS_PACK.md` | Frozen architecture and acceptance framework |
| `EDGE_HUB_ARCHITECTURE.md` | Edge code structure and trust boundaries |
| `CLINICAL_SAFETY_SHADOW_MODE.md` | Clinical review and shadow-mode protocol |
| `HIS_FHIR_INTEGRATION_CONTRACT.md` | HIS/EMR integration and purge contract |
| `OPERATIONS_RUNBOOK.md` | Startup, daily operations, incident, backup and rollback guidance |
| `SECURITY_BASELINE.md` | Security controls and validation boundaries |
| `RISK_REGISTER.md` | Severity, control status and residual risk |
| `RESIDUAL_HARDENING_REPORT.md` | Residual-control implementation and evidence boundaries |
| `DEVICE_TRUST_BASELINE_REPORT.md` | Device Trust implementation and validation boundaries |
| `WARD_WORKFLOW_CONTRACT.md` | Admission, NFC, session, reset, hot-swap and forensic workflow contract |
| `HUB_REFERENCE_DESIGN.md` | Physical Hub, UI, Edge, network, power and prototype reference design |
| `TABLET_ONLY_KIOSK_SPEC.md` | Auto-boot, local state restore, kiosk, watchdog and safe recovery contract |
| `TABLET_HARDWARE_DECISION.md` | Acer Spin N17H2 versus BMAX i11_s hardware-role decision |
| `ROAMING_TABLET_ARCHITECTURE.md` | Fixed Hub plus Roaming Tablet sync, offline and security contract |
| `ROAMING_TABLET_BASELINE_REPORT.md` | Roaming snapshot, command safety, evidence and validation gates |
| `OUTSIDE_IN_WARD_WORKFLOW.md` | Outside-facing admission console, tokenized handoff and ward zoning contract |
| `test_outside_admission.py` | Bed availability, reservation and admission handoff regression |
| `alembic/versions/6a7b8c9d0e11_outside_admission.py` | Bed availability and admission preparation migration |
| `test_roaming.py` | Roaming snapshot, command, revision and safety regression |
| `alembic/versions/7b8c9d0e1f22_roaming_commands.py` | Roaming command and alert acknowledgement migration |
| `hardware_research_notes_2026-08-19.md` | Source-bounded hardware research notes and verification boundaries |
| `test_session_workflows.py` | Session workflow regression tests |
| `test_residual_controls.py` | Residual-control regression tests |
| `device_trust.py` | Canonical Ed25519 signed-telemetry verification |
| `test_device_trust.py` | Enforce-mode Device Trust regression tests |
| `test_device_trust_observe.py` | Observe-mode continuity regression test |
| `reliability_validation_result.json` | Measured software reliability evidence |
| `pilot_simulation_result.json` | Software-only 30-day simulation evidence |
| `run_all_tests.py` | Master regression runner |


## Strategic product differentiator

Smart Ward Hub's strategic differentiator is the combination of **Sovereign Edge / Offline-first**, **Zero-PII by design**, **Patient Safety Intelligence**, **Tamper-Evident Evidence**, **HIS/EMR Interoperability**, and the **Device Trust & Secure Provisioning Layer**. Its current software baseline verifies canonical signed telemetry and device credential lifecycle events; the wider device-to-evidence trust chain still includes manufacturer-authenticated identity, hardware-backed keys and external append-only anchoring as validation gates.

This is recorded as a **product direction with an implemented signed-telemetry/lifecycle software baseline**, not as a completed production security claim. Current software evidence supports Ed25519 public-key enrollment, canonical signed telemetry verification in enforce mode, sequence/replay protection, basic credential lifecycle controls, Zero-PII processing, durable forensic packages, local hash verification and pilot workflows. Asymmetric manufacturer CA provisioning, secure-element/HSM key custody, geofence trust degradation and external WORM anchoring remain planned or externally validated gates.

Stakeholder wording must preserve patient safety: a device or geofence trust anomaly should result in alert, audit and controlled degraded-trust/quarantine handling, not automatic device bricking that could create a monitoring blind spot. See `PRODUCT_DIFFERENTIATORS.md` for the approved claim language and roadmap.
