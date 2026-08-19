# Smart Ward Hub — Fixed Hub plus Roaming Tablet Architecture

**Status:** Roaming synchronization and command software baseline  
**Use case:** large wards, multi-room wards and nurse walk-rounds  
**Clinical status:** clinical validation pending

## 1. Design decision

สำหรับวอร์ดขนาดใหญ่ควรใช้สถาปัตยกรรม **Fixed Edge Hub + Roaming Tablet** แทนการให้ทุก Tablet เป็น source of truth แยกกัน โดย Fixed Hub ประจำวอร์ดเป็นเจ้าของ state และ evidence ส่วน Roaming Tablet เป็น authenticated operational client ที่พยาบาลถือเดินตรวจได้

```text
                    Hospital HIS/FHIR boundary
                              │
                    ┌─────────┴─────────┐
                    │ Fixed Ward Hub    │
                    │ source of truth   │
                    │ SQLite/WAL        │
                    │ Device Trust      │
                    │ triage/evidence   │
                    └───────┬───────────┘
                 ward VLAN / controlled Wi-Fi
              ┌─────────────┼─────────────┐
              │             │             │
        Roaming Tablet A  Tablet B   Nurse-station kiosk
        walk-round UI     backup UI   optional fixed display
```

The Fixed Hub owns pairing, session state, alert state, forensic evidence, sequence/replay acceptance and destructive workflow transitions. A Roaming Tablet may cache a minimum non-PII view and submit authenticated commands, but it must not become an independent authority for patient-device state.

## 2. Role boundary

| Capability | Fixed Ward Hub | Roaming Tablet |
|---|---|---|
| Source of truth | Yes | No; uses synchronized cache |
| SQLite/WAL evidence store | Yes | Optional encrypted UI cache only |
| Device Trust credential authority | Enroll/revoke under scope | Present tablet identity; cannot self-enroll devices |
| BLE telemetry ingestion | Yes, directly or through proxy | No by default; do not make a walk-round tablet the telemetry owner |
| Triage and alert state | Authoritative evaluation | Read/cache and human acknowledgement command |
| Pairing/session transition | Authoritative state machine | Submit authenticated request; receive accepted/rejected result |
| NFC pointer | Resolve/submit pointer action | Scan/resolve pointer through Hub API |
| Routine close/incident freeze | Commit and persist | Request through Hub; no local destructive commit while disconnected |
| HIS/FHIR sync | Yes | No direct HIS synchronization |
| Offline capability | Local monitoring continues | Read last cache; queue safe non-destructive actions |
| Audit/evidence | Full structured audit and anchor | Local device audit of UI/command queue, then sync to Hub |

## 3. Roaming Tablet trust model

The Roaming Tablet should authenticate as both a **user-facing client** and a managed device. The user identity comes from OIDC or an approved hospital identity provider. The tablet identity comes from device enrollment, managed-device certificate or equivalent protected credential. Production use must not rely on a shared bearer token embedded in the app.

The tablet must not receive raw HN/AN or patient names. It receives only the minimum data needed for care workflow: bed number, opaque session/device references, alert severity and time, telemetry freshness, battery/trust state, acknowledgement state and reconciliation flags. Any additional identity display must be governed by a separate hospital-approved data boundary and is outside the Zero-PII Edge baseline.

## 4. Synchronization contract

Synchronization uses pull plus authenticated command push:

```text
Tablet connects
    ↓
GET ward snapshot with cursor/revision
    ↓
Display non-PII bed/alert/session state
    ↓
POST command with idempotency_key and expected_revision
    ↓
Fixed Hub validates scope + state + revision
    ↓
Hub commits or rejects through state machine
    ↓
Tablet receives authoritative result and advances cursor
```

The Hub is authoritative. The software baseline exposes `GET /api/v1/roaming/snapshot` with a deterministic revision/cursor and `POST /api/v1/roaming/commands` with durable command idempotency and authoritative outcomes. Last-write-wins must not be used for session, alert or forensic state. Every roaming command carries:

| Field | Purpose |
|---|---|
| `command_id` | Unique command identity for audit and retry |
| `idempotency_key` | Prevent duplicate reset, discharge or acknowledgement |
| `actor_id` | Authenticated nurse/operator identity or pseudonymous subject |
| `tablet_id` | Managed roaming device identity |
| `expected_revision` | Detect stale screen state before mutation |
| `session_id` | Opaque session target |
| `requested_at` | Audit and clock-skew evaluation |
| `command_type` | ACK, NOTE, RESET_REQUEST, RESET_CONFIRM, HOT_SWAP or DISCHARGE |

A stale revision returns a conflict response and the Tablet must refresh rather than overwrite the Fixed Hub state. Alert acknowledgement, admission-task acknowledgement and safe `RESET_REQUEST` are supported in the current software baseline. `RESET_CONFIRM`, discharge, hot-swap, pairing changes, credential changes, incident freeze and purge remain Fixed Hub/live-connection actions in the initial pilot. The existing handover idempotency and safe purge rules remain authoritative.

## 5. Offline roaming policy

A roaming Tablet may continue to display its last synchronized state while disconnected, but must show a prominent `OFFLINE — LAST KNOWN STATE` banner and a freshness age. It may queue low-risk, non-destructive actions such as an acknowledgement or operator note if hospital policy permits. The command is not considered committed until the Fixed Hub acknowledges it.

The following actions should require a live connection to the Fixed Hub in the first pilot: RESET confirmation, discharge, hot-swap, device credential changes, pairing changes, incident freeze and any action that clears or purges data. If the ward requires offline reset, that must be a separate clinical-safety design with a lease, local evidence and reconciliation protocol; it should not be assumed by the initial implementation.

When the connection returns, queued commands are replayed by idempotency key. The Hub validates session revision and current state. A rejected command is displayed as `REQUIRES RECONCILIATION`, not silently retried forever.

## 6. Walk-round UI

The roaming screen should optimize for one-hand use and short interactions:

1. show ward/zone and connection/freshness state;
2. show the next bed or allow a bed-number search;
3. tap NFC to resolve a device pointer when permitted;
4. display bed, device trust, signal age, battery and active alert severity;
5. acknowledge or escalate through an authenticated command;
6. show explicit result: `COMMITTED`, `QUEUED OFFLINE`, `CONFLICT — REFRESH`, or `REQUIRES RECONCILIATION`.

The Tablet should not present raw data that is unnecessary for walk-round operation. It should not use color alone for alerts, and it should not allow an accidental NFC tap to confirm reset or discharge.

## 7. Network and deployment patterns

| Ward condition | Recommended deployment |
|---|---|
| Small ward | One Fixed Hub plus optional nurse-station display |
| Large ward | One Fixed Hub per ward/zone plus managed Roaming Tablets on segmented Wi-Fi |
| Multiple floors or buildings | Separate Fixed Hub per operational ward/zone; central HIS/FHIR integration above them |
| Wi-Fi dead zones | Tablet displays stale state and queues safe commands; install approved AP/roaming coverage before destructive offline workflows |
| WAN/HIS outage | Fixed Hub continues local monitoring; Tablets use local ward network if available |
| Fixed Hub outage | Manual clinical fallback first; Tablet must not silently become an unvalidated telemetry authority |

Roaming Tablets should not connect directly to wearable BLE streams in the initial architecture. This avoids duplicate telemetry ingestion, split sequence ownership and inconsistent forensic evidence.

## 8. Acceptance gates

| Gate | Pass condition |
|---|---|
| Authentication | OIDC/user identity and managed tablet identity are both validated |
| Zero-PII | No raw HN/AN/name in Tablet cache, logs, screenshots or command payloads |
| Snapshot freshness | Stale/last-known banners are visible and tested |
| Revision conflict | Stale Tablet cannot overwrite a newer Hub state |
| Idempotency | Retries cannot duplicate reset, discharge, handover or purge |
| Offline queue | Safe commands queue and reconcile; destructive actions are blocked by default |
| Network transition | Walk-round reconnect does not duplicate commands or lose authoritative results |
| Tablet loss | Revoked/expired Tablet credential cannot read new ward state |
| Fixed Hub loss | Manual clinical fallback is visible and documented |
| Human factors | Walk-round UI works with gloves, one hand and realistic ward interruptions |

## 9. Implementation evidence and boundaries

The current software evidence includes `test_roaming.py`, durable `RoamingCommand` persistence, migration `7b8c9d0e1f22`, non-PII snapshot responses, stale revision `409` conflicts, acknowledgement idempotency, unresolved-incident reset gating and role-based authentication checks. It does not yet prove managed Android device identity, OIDC integration with a hospital IdP, real ward Wi-Fi roaming, encrypted Android cache, push notifications or multi-process distributed command coordination.

## 10. Product value

This design extends the product from a stationary console to a **Sovereign Ward Operating Layer**: the Fixed Hub preserves local truth and evidence, while managed Roaming Tablets give nurses mobility without copying the patient identity store or splitting clinical state across devices. This supports large-ward deployment while preserving the core claims of Sovereign Edge, Offline-first, Zero-PII, Patient Safety Intelligence and Tamper-Evident Evidence.

## References

[1]: ./WARD_WORKFLOW_CONTRACT.md "Ward workflow contract"
[2]: ./TABLET_ONLY_KIOSK_SPEC.md "Tablet-only kiosk specification"
[3]: ./edge_controls.py "Idempotency and audit controls"
[4]: ./main.py "Hub endpoints and state machine implementation"
