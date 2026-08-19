# Smart Ward Hub — Roaming Tablet Baseline Report

**สถานะ:** P0-hardened software baseline; pilot-ready foundation; clinical validation pending  
**ขอบเขต:** Fixed Hub plus authenticated Roaming Tablet synchronization for large wards  
**ผลการทดสอบ:** functional verification passed; software-only evidence

## 1. Executive summary

Smart Ward Hub now has a software baseline for a **Fixed Hub plus Roaming Tablet** model. The Fixed Hub remains the source of truth for bed, session, alert, telemetry and forensic state. A Roaming Tablet receives a minimum non-PII snapshot and submits authenticated, revision-aware commands; it cannot become an independent telemetry or clinical-state authority.

The implementation supports a deterministic snapshot cursor/revision, freshness and trust indicators, durable command idempotency, alert acknowledgement, admission-task acknowledgement and safe `RESET_REQUEST`. Destructive confirmation remains on the Fixed Hub in the initial pilot.

## 2. Implemented contract

| Capability | Endpoint/persistence | Evidence |
|---|---|---|
| Non-PII ward snapshot | `GET /api/v1/roaming/snapshot` | Cursor/revision and no-change response |
| Freshness/trust state | Snapshot session rows | `FRESH`, `STALE`, `NO_HEARTBEAT`, `DISABLED`, `OBSERVE`, `ENROLLED` |
| Revision conflict | `expected_revision` | Stale tablet mutation returns `409 STALE_REVISION` |
| Command idempotency | `RoamingCommand` and `7b8c9d0e1f22` | Duplicate command returns authoritative original result |
| Alert acknowledgement | `ACK_ALERT` | Durable acknowledgement actor/time without resolving incident automatically |
| Admission task acknowledgement | `ADMISSION_TASK_ACK` | Reads authoritative preparation state |
| Safe reset request | `RESET_REQUEST` | Enters `RESET_PENDING` only after Hub validation |
| Destructive reset | `RESET_CONFIRM` | Blocked from roaming path in the initial pilot |
| Zero-PII | Snapshot/command/audit redaction | No raw HN/AN/name in roaming response or audit evidence |

## 3. Safety behavior

An offline Tablet may display last-known state only with an explicit `OFFLINE — LAST KNOWN STATE` banner and freshness age. A stale revision cannot overwrite newer Fixed Hub state. Acknowledgement does not resolve an unresolved incident and does not bypass the incident-freeze gate. Reset confirmation, discharge, hot-swap, pairing changes, credential changes, incident freeze and purge remain live Fixed Hub actions.

> **Design rule:** mobile reach must not become mobile authority.

## 4. Test evidence

The focused `test_roaming.py` regression passed the following controls:

| Control | Result |
|---|---|
| Authenticated non-PII snapshot | Passed |
| Cursor/revision no-change response | Passed |
| Stale revision mutation rejection | Passed |
| Alert acknowledgement through Fixed Hub | Passed |
| Duplicate command replay/idempotency | Passed |
| Unresolved-alert reset gate | Passed |
| Safe reset request to `RESET_PENDING` | Passed |
| Roaming `RESET_CONFIRM` destructive block | Passed |
| Audit without raw patient token | Passed |

The master regression also passed Functional Levels 1–6, P0 hardening, residual controls, Device Trust enforce/observe, ward workflows, Outside-in admission, roaming synchronization, migration, reliability and 30-day software simulation checks.

Latest software-only reliability evidence was 30 simulated devices, 600 requests, all HTTP 200 in the ordered stream, p50 227.988 ms, p95 690.216 ms, p99 926.509 ms, maximum 1215.514 ms and mean 294.112 ms. The 30-day software simulation accepted 900 daily packets with concurrent ingestion measured at 175.730 ms. These values are not hardware, Wi-Fi, battery, HIS or clinical guarantees.

## 5. Open validation gates

Managed Android device identity, OIDC integration with the hospital IdP, encrypted BMAX cache, screenshot/clipboard policy, real ward Wi-Fi roaming, push notification delivery, multi-process command coordination, power-loss behavior and clinical human-factors validation remain open. The software command API enforces scope, revision and idempotency but does not itself prove hardware-backed Tablet identity.

## References

[1]: ./ROAMING_TABLET_ARCHITECTURE.md "Fixed Hub plus Roaming Tablet architecture"
[2]: ./test_roaming.py "Roaming synchronization regression"
[3]: ./alembic/versions/7b8c9d0e1f22_roaming_commands.py "Roaming command migration"
[4]: ./SECURITY_BASELINE.md "Security baseline and validation boundaries"
[5]: ./RISK_REGISTER.md "Risk register"
[6]: ./reliability_validation_result.json "Software reliability evidence"
[7]: ./pilot_simulation_result.json "30-day software simulation evidence"
