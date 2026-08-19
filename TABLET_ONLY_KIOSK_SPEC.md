# Smart Ward Hub — Tablet-only Kiosk Specification

**Status:** Tablet-only reference baseline  
**Purpose:** automatic boot, kiosk launch, local-state restore and safe ward recovery  
**Clinical status:** clinical validation pending

## 1. Design decision

Smart Ward Hub may be built as a **single Tablet-only Edge Appliance** rather than a tablet terminal paired with a separate Mini-PC. The tablet must therefore run the local Edge runtime, persistent SQLite/WAL state, Device Trust verification, telemetry buffer, triage, audit and forensic workflows on the same device.

This is not the same as using an ordinary consumer tablet as a remote dashboard. The selected tablet must support a controlled operating system, local service supervision, encrypted persistent storage, kiosk mode, stable networking, NFC/BLE access and a reliable power/charging path.

> The tablet should auto-start the Hub, restore the latest known operational state, and make the ward screen available without bed-by-bed manual reconfiguration. Restore must never silently assert that a patient or device is still safe; it must show freshness, trust and recovery state explicitly.

## 2. Recommended tablet platform

| Platform | Recommendation | Reason |
|---|---|---|
| Linux-capable x86/ARM rugged tablet | Preferred for the current FastAPI/Python baseline | Can run the existing local service model with systemd/supervisor and a Chromium/Qt kiosk shell |
| Windows IoT/Enterprise tablet | Viable controlled prototype | Supports Assigned Access/Shell Launcher, but service hardening and update policy require validation |
| Android dedicated device | Possible future port | Requires a native service, container strategy or validated embedded runtime; do not assume the current Python backend is production-safe on ordinary Android |
| Consumer tablet without device-owner/kiosk control | Not recommended | User apps, sleep policy, storage behavior, updates and physical handling are not sufficiently controlled |

The first prototype should choose a tablet with at least wired Ethernet through a validated dock or USB adapter, Wi-Fi supported by the ward VLAN, NFC or a supported reader, BLE capability or a validated proxy interface, encrypted storage, a replaceable/managed power path and a device-owner/kiosk policy.

## 3. Automatic boot contract

The boot sequence must be deterministic:

```text
Power on / reboot
      ↓
OS boot + verified storage
      ↓
Hub service supervisor starts local Edge runtime
      ↓
SQLite migration/readiness check
      ↓
Checkpoint and session-state recovery
      ↓
Device Trust / clock / storage / network health evaluation
      ↓
Kiosk UI launches automatically
      ↓
Latest known ward state shown with freshness and trust banners
```

The tablet must not require a keyboard, shell command or per-bed setup after an ordinary restart. A service supervisor/watchdog must restart the local runtime if it exits, while the UI must show `EDGE_SERVICE_DEGRADED` if the service cannot be recovered.

For a Linux-capable tablet, the reference pattern is a dedicated service account, `systemd` service for the Edge API, a separate kiosk compositor/browser process, restart limits, read-only OS partitions where practical and a controlled maintenance escape path. For Windows, use a dedicated service plus Assigned Access/Shell Launcher and disable ordinary user shell access. Android requires a separate platform-specific implementation and must not be treated as equivalent without validation.

## 4. State restore contract

State restore is divided into **durable truth**, **recoverable runtime state** and **stale display state**:

| State | Source | Restore behavior |
|---|---|---|
| Device registry and credentials | SQLite/Alembic | Restore before accepting telemetry |
| Pairing/session state | SQLite `Pairing`/`WardSession` | Restore with status and last transition |
| Telemetry checkpoint | EdgeTelemetryStore checkpoint | Recover bounded samples and last sequence where valid |
| Alerts and forensic packages | SQLite | Restore as durable human-review state |
| Audit and anchor paths | JSONL/local anchor storage | Check readability and write test before marking healthy |
| HIS sync attempts | SQLite | Resume according to idempotency state; never replay destructively |
| UI selected bed | local UI preference only | Restore as a convenience, never as authorization |

The restored screen must show at least:

- `LAST_STATE_RESTORED_AT`;
- `LAST_TELEMETRY_AT` per active device;
- current session status;
- Device Trust status (`VERIFIED`, `UNVERIFIED`, `STALE`, `REVOKED` or `DEGRADED`);
- checkpoint recovery result;
- offline/sync state;
- unresolved alert count; and
- whether operator confirmation is required.

If state is stale, the UI must not show a normal green state merely because the database contains a previous pairing. It should show `STALE_STATE_REQUIRES_RECONCILIATION` and ask the operator to verify the physical device/bed relationship. This is a safety distinction between **last known state** and **current clinical reality**.

## 5. Restore safety rules

The tablet may restore a session as `ACTIVE` in the database, but the UI should present it as `ACTIVE — RECONCILIATION REQUIRED` until a fresh telemetry heartbeat and current Device Trust check are observed. A restored `RESET_PENDING`, `INCIDENT_FROZEN`, `REVOKED` or `SESSION_CLOSED` state must not be auto-promoted to active.

If the device clock is outside the configured skew, the credential is expired/revoked, the checkpoint is corrupt, the audit path is unwritable or the database migration is incomplete, the tablet must fail closed for the affected operation and show a clear maintenance state. It must not delete the last valid evidence to make the UI appear healthy.

The restore flow must never automatically:

- assign a patient token to a different device;
- clear an unresolved incident;
- confirm `RESET`;
- purge an aggregate twice;
- downgrade a revoked credential; or
- claim that a stale device is currently transmitting.

## 6. Tablet-only local runtime layout

```text
[Tablet OS kiosk session]
        │ auto-launch
        ▼
[Hub UI shell]
        │ localhost/Unix socket only
        ▼
[Local Edge service]
  FastAPI + auth boundary
  Device Trust verifier
  EdgeTelemetryStore
  triage / alerts
  session workflow
  SQLite WAL / audit / anchor
        │
        ├── tablet BLE/NFC interfaces
        ├── Wi-Fi or wired dock network
        └── authenticated HIS/FHIR egress
```

The UI and local API should communicate over a restricted local interface. The tablet should not expose the administrative API directly to the ward Wi-Fi. If external operators need access, use a separate authenticated maintenance path with OIDC/mTLS and explicit scopes.

## 7. Power, sleep and connectivity behavior

The tablet must operate in dedicated-device mode: screen sleep disabled during active ward operation, controlled brightness, thermal monitoring, managed charging and a visible power-degraded state. The internal battery is a continuity aid, not proof of power-loss safety. A dock or UPS-supervised power path remains required for pilot testing.

When Wi-Fi/WAN is unavailable, local telemetry, triage, session state and audit should continue if the tablet is healthy. The UI should display `OFFLINE — LOCAL MONITORING ACTIVE` rather than an ambiguous disconnected icon. When the network returns, synchronization must use the existing idempotency and acknowledgment gates.

## 8. Acceptance tests for Tablet-only prototype

| Test | Pass condition |
|---|---|
| Cold boot | Hub service and kiosk UI appear automatically without keyboard interaction |
| Normal restart | Pairing/session state restores with freshness banners |
| Checkpoint recovery | Bounded buffer and sequence state recover without duplicate acceptance |
| Stale state | Old telemetry becomes visibly stale and requires reconciliation |
| Revoked/expired credential | Telemetry operation fails closed and state is visible |
| Incident state | `INCIDENT_FROZEN` is not cleared by reboot or NFC tap |
| Reset state | `RESET_PENDING` survives reboot and still requires explicit confirmation |
| Power interruption | Recovery does not create duplicate pairing, purge or handover |
| Offline operation | Local monitoring continues without HIS/WAN |
| Service crash | Watchdog restarts service or exposes `EDGE_SERVICE_DEGRADED` |
| Kiosk escape | Ordinary operator cannot access shell, settings or other apps |
| Storage failure | System exposes maintenance state without deleting evidence |

These are software/device integration acceptance gates. They do not establish clinical readiness, regulatory compliance, battery life, RF performance or medical-device certification.

## References

[1]: ./HUB_REFERENCE_DESIGN.md "Hub physical and software reference design"
[2]: ./WARD_WORKFLOW_CONTRACT.md "Ward workflow and session contract"
[3]: ./edge_runtime.py "Checkpoint recovery and bounded buffer implementation"
[4]: ./main.py "FastAPI startup and workflow integration"


## 9. Device-specific prototype decision

For the current Python/FastAPI Edge baseline, the **Acer Spin N17H2 is the primary one-tablet prototype candidate** if the actual unit runs a full supported Windows edition or Linux. Its x86 desktop software path is more compatible with the current local service, SQLite/WAL and kiosk templates.

The **BMAX i11_s is the preferred lightweight touch-display candidate**, but its Android platform must pass device-owner/kiosk, local service, NFC/BLE, storage endurance and auto-start tests before it can become the sovereign Edge source of truth. If those tests are not passed, use BMAX as a temporary UI terminal and Acer as the Edge source of truth during bench validation.

This is a provisional hardware decision based on representative family specifications. The physical units must be checked before deployment; neither device has yet established NFC, wired Ethernet, secure boot/TPM, 24/7 power behavior or clinical hardware suitability.
