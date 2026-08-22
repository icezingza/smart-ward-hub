# P2-005 Worker Control Consistency Readiness Report

**Date:** 22 August 2026
**Status:** `VERIFIED — SOFTWARE-ONLY / FIXTURE-ONLY`
**Decision:** `P2_005_WORKER_CONTROL_CONSISTENCY_VERIFIED`
**Scope:** In-process worker control plane, SQLite software-fixture replay, recovery transcript, operator approval/read-back and cross-package evidence binding

## 1. Executive summary

The P2-005 consistency gate verifies that the worker-control evidence chain has compatible semantics across its main software layers. It exercises an allowlisted in-process job path, idempotent replay, stale-lease blocking and explicit reconciliation; it then checks the durable SQLite fixture for lease recovery, retry/dead-letter classification and isolated backup/restore. The gate also verifies the redacted operator transcript, separated approval/read-back and the existing cross-package binding result.

The gate passed as a **local software consistency control**. It does not start a scheduler, distributed worker, network client, external queue, clinical job or production resume. It records `read_only=true`, `runtime_mutation_performed=false`, `external_transmission_performed=false` and `authorization_promoted=false` in the exported evidence.

## 2. Evidence summary

| Control | Result | Evidence |
|---|---|---|
| In-process allowlisted job and idempotency | Passed | QUEUED submission, identical fingerprint on idempotent replay and SUCCEEDED completion |
| Stale-lease recovery | Passed | Stale job is blocked, explicitly reconciled to QUEUED and recovered to SUCCEEDED |
| In-process audit integrity | Passed | Hash-chain verification true in normal and recovery paths |
| Durable SQLite fixture | Passed | `mode=SOFTWARE_FIXTURE`, WAL, synchronous value `2` and integrity check `ok` |
| Retry/dead-letter semantics | Passed | `LEASE_EXPIRED_REQUIRES_RECONCILIATION`, `RETRY_LIMIT_EXCEEDED_DEAD_LETTER` and explicit replay confirmation |
| Backup/restore binding | Passed | `SOFTWARE_RESTORE_VERIFIED`, binding verified and restored classification preserved |
| Recovery transcript | Passed | Five events, transcript integrity true, raw worker identifiers not exported |
| Approval/read-back | Passed | Validation valid, transcript binding valid and requester/approver/read-back roles separated |
| Cross-package binding | Passed | Existing binding decision `BOUND` with all checks true |
| Authorization boundary | Locked | External authority NONE, runtime authority NONE, production/clinical authorization false |

## 3. Cross-layer contract

The in-process layer treats allowlisted `BACKUP_REPORT` and `EVIDENCE_REPORT` jobs as non-clinical work. It enforces bounded attempts, role separation, idempotency fingerprints, leases, stale-lease reconciliation and append-only audit verification. The durable layer preserves the same safety semantics in a SQLite `software_fixture` with WAL and `synchronous=FULL`; it is not a production durable queue or distributed scheduler.

The recovery transcript converts lease/dead-letter/backup events into five redacted events. The approval/read-back contract binds the transcript hash and queue-binding hash while requiring distinct roles and a software-rehearsal confirmation. The cross-package binding then verifies transcript, approval, durable replay evidence and freeze-listed artifact hashes. P2-005 consistency is therefore an umbrella semantic check, not a replacement for the lower-level unit and phase-end suites.

## 4. Hardening and adversarial coverage

The focused suite contains six cases: full-stack consistency, durable runtime replay mutation, transcript integrity mutation, approval/binding mutation, authorization mutation and raw identity marker mutation. Every mutation path must return `P2_005_WORKER_CONTROL_CONSISTENCY_BLOCKED` with a remediation code and must not self-promote authority.

The phase-end gate verifies the focused suite, rejects network/provider/transport/scheduler imports in the new control and exporter, checks all consistency checks and boundary locks, round-trips the exporter, scans for raw identity/secret markers and private-key material, and runs `git diff --check`.

## 5. Claim boundary and residual risk

This evidence supports the claim that the worker software controls are internally consistent in deterministic fixtures. It does not verify distributed locking, production scheduler supervision, Windows service recovery, encrypted backup destination, retention/RPO/RTO, external dead-letter delivery, hardware storage durability, human operator sign-off, clinical state mutation or independent external approval.

External Gates remain `7 BLOCKED / 3 OPEN / 0 PASSED`. The authorization boundary remains `external_authority=NONE`, `runtime_authority=NONE`, `production_authorized=false`, `clinical_validation_authorized=false` and `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`. Product status remains `CONTROLLED_PRODUCTION_PROTOTYPE` with `production_ready=false`.

> The correct claim is **software-verified worker-control consistency in a controlled production prototype**. This is not production-ready, clinical-ready, tamper-proof or a 100% HIPAA/PDPA compliance determination.

## 6. Files and verification

| Item | Path / value |
|---|---|
| Evaluator | `p2_005_worker_control_consistency.py` |
| Exporter | `export_p2_005_worker_control_consistency.py` |
| Focused tests | `test_p2_005_worker_control_consistency.py` — 6 passed |
| Phase-end gate | `test_p2_005_worker_control_consistency_phase_end_hardening.py` — passed |
| Master integration | `run_all_tests.py` |
| Evidence snapshot | `evals/micro_rag/evidence/p2-005-worker-control-consistency-local.json` |
| Feature commit | `e3d4373a8adc08b0a8a54450357313f6957d4f3b` |
| Feature freeze source | `e3d4373a8adc08b0a8a54450357313f6957d4f3b` |

The evidence snapshot was generated against a passing freeze and committed separately. The release-freeze must be refreshed after this report and traceability update, followed by master regression, runtime-artifact cleanup and final alignment verification.
