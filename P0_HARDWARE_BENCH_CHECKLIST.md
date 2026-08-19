# Smart Ward Hub — Acer Fixed Hub P0 Hardware Bench Checklist

**Target:** Acer Spin N17H2 as Fixed Edge Hub candidate  
**Status:** Checklist prepared; physical execution pending

## Safety and scope

Run this checklist only on an isolated non-clinical test ward or lab network with synthetic opaque tokens and non-production devices. Do not connect a real patient, live HIS, production credential or real clinical alert stream during bench validation.

## Pre-conditions

| Check | Expected evidence | Status |
|---|---|---|
| Device model/serial recorded | Redacted asset ID and operator | Pending |
| OS version and patch level | Host inventory | Pending |
| Disk encryption state | Host evidence, no recovery secret | Pending |
| Non-root/service account | Account and permission check | Pending |
| Firewall and listening ports | Allowlist and scan result | Pending |
| Trusted time source | Clock offset and source | Pending |
| Power/charger/battery health | Battery report and charger test | Pending |
| Network topology | Edge, device, roaming and HIS segments | Pending |
| Test certificates/tokens | Test-only identifiers and fingerprints | Pending |
| Backup destination | Encrypted destination and manifest policy | Pending |

## Functional and recovery sequence

1. Start from a known-good software version and record commit/change ID.
2. Apply migrations on a clean synthetic database and verify Alembic head.
3. Start the service with authentication configured and documentation disabled.
4. Verify `/health`, database readiness, disk capacity, checkpoint path permission and audit path permission.
5. Ingest synthetic TelemetryPacket v1 traffic and verify sequence/replay, Device Trust mode, bounded buffer and audit redaction.
6. Exercise pairing, `RESET_PENDING`, hot-swap, discharge, Outside-in admission and roaming stale-revision behavior with synthetic opaque tokens.
7. Interrupt network connectivity and verify visible stale/offline state, local retention and no unsafe purge.
8. Reboot normally and verify service supervisor ordering, database recovery, checkpoint restoration, alert/session state and reconciliation indicators.
9. Remove power at controlled points: idle, telemetry ingestion, SQLite commit, checkpoint write and audit write. Record the exact interruption point.
10. Restore power and verify boot, filesystem/database integrity, last accepted sequence, alert/session consistency, forensic linkage and audit continuity.
11. Simulate low disk capacity in an isolated fixture and verify bounded failure, operator alert and no silent data loss claim.
12. Restore from a known-good backup on a separate target and compare schema, counts, hash-chain verification, active session state and pending sync state.
13. Repeat with a network interruption and certificate expiry/revocation fixture.

## Acceptance evidence

The bench result must include UTC timestamps, operator, asset ID, software commit, OS version, power/network condition, command/test reference, expected result, observed result, status label, incident ID if applicable, redacted logs and artifact checksums. Separate software simulation results from physical Acer evidence.

## Stop conditions

Stop the test and switch to manual safe operation if there is identity mismatch, raw HN/AN entering Hub Core, authentication bypass, unexplained alert loss, forensic hash mismatch, database corruption, repeated missed telemetry, unsafe automatic reset, certificate/key exposure, uncontrolled purge or a host/network condition that cannot be explained.

## Evidence boundary

This checklist does not authorize clinical use. Passing it would support **hardware bench verification** for the tested configuration only; it would not establish clinical readiness, production readiness, regulatory compliance, or full hospital integration.
