# Smart Ward Hub — Ward Workflow Contract

**Status:** controlled production prototype workflow baseline  
**Deployment status:** pilot deployment configuration pending  
**Clinical status:** clinical validation pending

## 1. Contract objective

เอกสารนี้กำหนด boundary ระหว่าง Admission Gateway, Ward Edge Hub, NFC pointer, BLE/attested ingestion proxy และ operator workflow สำหรับการผูกอุปกรณ์, hot-swap, discharge, reset และ forensic evidence. Contract นี้ต้องรักษา **Zero-PII**, `TelemetryPacket v1`, Device Trust และ patient-safety continuity ของ Smart Ward Hub เดิม

> Hub Core รับเฉพาะ `patient_token` หรือ `encounter_token` ที่ถูกทำให้เป็น opaque token แล้วเท่านั้น Raw HN/AN, ชื่อผู้ป่วย และ QR ที่ถอดกลับเป็น identity ได้ ต้องถูก tokenized ก่อนเข้า Hub Core

## 2. Trust boundary

```text
Raw HN/AN or Admission Barcode
          │
          ▼
Admission Gateway / HIS-authorized tokenizer
          │  patient_token or encounter_token only
          ▼
Ward Edge Hub Core ─── NFC pointer ─── device_id/key_id lookup only
          │
          ▼
BLE / Attested Ingestion Proxy
          │  signed canonical TelemetryPacket v1
          ▼
Device Trust verification → sequence/replay guard → Edge buffer → triage/evidence
```

The NFC pointer is a **Fast Lookup Index**, not a cryptographic root of trust. A passive NFC UID may identify which device record to load, but it does not prove that a subsequent BLE packet came from that device. Telemetry admission still requires the configured Device Trust mode, signed envelope and monotonic sequence control.

For the current prototype, a BLE Gateway or attested ingestion proxy may attach `X-Device-Key-ID` and `X-Device-Signature` when the original C60 hardware cannot sign Ed25519 itself. This proxy is a distinct trust boundary and must have its own identity, audit trail, key custody and deployment validation. It must not be described as equivalent to a device secure element.

## 3. Admission contract

| Input | Allowed at Hub Core | Required behavior |
|---|---|---|
| Raw HN/AN barcode | No | Tokenize at Admission Gateway or HIS-authorized service |
| Opaque `patient_token` | Yes | Validate format and store as pseudonymous reference |
| Opaque `encounter_token` | Yes | Use as session-scoped pseudonymous reference where available |
| Patient name/address/phone | No | Reject and do not write to Edge logs or cache |
| Patient QR with embedded HN/AN | No | Decode and tokenize before forwarding |

The current pairing schema accepts an opaque `patient_token` and rejects common raw HN/AN prefixes. This prevents the Hub Core from becoming an identity-mapping store. A hospital-specific Admission Gateway remains responsible for mapping and authorization; that mapping is outside this Edge package.

## 4. NFC pointer contract

The NFC endpoints are:

| Endpoint | Purpose | Trust meaning |
|---|---|---|
| `POST /api/v1/nfc/pointers` | Enroll `nfc_uid → device_id/key_id` metadata | Operator-authorized lookup registration only |
| `POST /api/v1/nfc/resolve` | Resolve a scanned pointer | Returns device lookup data; does not authenticate telemetry |

NFC records contain no patient identity. A pointer may be revoked independently. The resolved `key_id` is used to select the expected Device Trust credential, while the signed telemetry itself remains the cryptographic proof.

## 5. Session state machine

```text
UNENROLLED
    ↓ device enrollment
ENROLLED / READY
    ↓ authenticated pairing
ACTIVE
    ├─ trust or incident anomaly → INCIDENT_FROZEN
    ├─ tap output / reset request → RESET_PENDING
    ├─ hot-swap → SESSION_CLOSED + new ACTIVE session
    └─ discharge → SESSION_CLOSED → READY_FOR_CHARGE
RESET_PENDING
    └─ visual confirmation RESET → SESSION_CLOSED → READY_FOR_CHARGE
INCIDENT_FROZEN
    └─ forensic review + reset request → RESET_PENDING
REVOKED
```

The state machine is **state-aware and fail-safe**. A tap on an active device must not silently destroy monitoring data. It enters `RESET_PENDING`, emits a short UI/audio signal and requires an explicit `RESET` confirmation. If an unresolved incident has no forensic package, reset and discharge are blocked until incident freeze occurs.

## 6. Hot-swap contract

Hot-swap applies only when the patient/encounter remains the same and a new device is assigned. The old session is closed with a routine digest, the new device receives a new `session_id`, and both sessions are linked through the supplied opaque `handover_id`. Raw telemetry sequences are never continued across devices; each device keeps its own monotonic sequence boundary.

The endpoint is:

```text
POST /api/v1/sessions/{old_session_id}/hot-swap
{
  "new_device_id": "...",
  "new_key_id": "...",
  "handover_id": "handover-..."
}
```

In `SW_DEVICE_TRUST_MODE=enforce`, the new device must have an active matching credential before hot-swap succeeds. The old buffer is cleared only after the routine close digest and new-session transaction are committed.

## 7. Discharge and output reset

Discharge means the patient/encounter ends. It closes the session, deactivates the pairing, records a routine close digest, clears the volatile application buffer and returns the device to `READY_FOR_CHARGE`. It does not delete forensic evidence or imply physical memory zeroization.

The output flow is therefore:

```text
NFC tap → resolve device pointer → inspect session state
        → RESET_PENDING + short signal
        → visual confirmation RESET
        → routine digest / incident gate
        → session close → READY_FOR_CHARGE
```

The implementation uses the phrase **“clear volatile application buffer”** rather than “wipe memory”. SQLite, checkpoint, audit and forensic retention policies remain separate controls.

## 8. Forensic evidence contract

Two evidence levels are required:

| Level | Trigger | Contents | Retention meaning |
|---|---|---|---|
| Routine Session Close | Confirmed reset, hot-swap or discharge | Summary fields, sequence range, sample count, timestamps and chained digest | Low-volume operational evidence; not a full telemetry archive |
| Incident-Triggered Freeze | Unresolved RED incident or explicit incident-freeze action | Frozen forensic package with the recent Edge window, currently up to 10 minutes where available | Tamper-evident incident evidence; external anchor and clinical governance pending |

Routine close uses `SessionCloseDigest` with a chained SHA-256 digest. Incident freeze links `ForensicPackage` to `session_id` and preserves the recent buffer window. Existing alert-triggered forensic freezing remains active; the workflow endpoint prevents reset from bypassing an unresolved incident.

The evidence language remains **tamper-evident**, not tamper-proof. External WORM anchoring, trusted timestamps, key custody and independent verification remain external validation gates.

## 9. API and audit requirements

Every workflow mutation requires bearer authentication and an appropriate scope. The system records `request_id`, actor, opaque session/device identifiers, transition, reason and outcome. Raw HN/AN and patient names must never appear in request payloads forwarded to Hub Core, cache, checkpoints or audit logs.

| Operation | Scope | Required audit event |
|---|---|---|
| NFC pointer enrollment | `device-trust:manage` | `nfc.pointer.enroll` |
| NFC pointer resolution | `pairing:write` | `nfc.pointer.resolve` |
| Reset request/confirmation | `pairing:write` | `session.reset_request`, `session.reset_confirm` |
| Hot-swap | `pairing:write` | `session.hot_swap` |
| Discharge | `pairing:write` | `session.discharge` |
| Routine digest | internal workflow | `session.close_digest` |
| Incident freeze | `forensics:write` | `session.incident_freeze` |

## 10. Open validation gates

The contract is implemented as a software workflow baseline, not as proof of real hospital integration. Remaining gates include Admission Gateway/HIS authorization, real NFC hardware behavior, C60/BLE proxy attestation, secure-element key custody, clock/network fault testing, clinical review of reset safety, external evidence anchoring and real HIS/EMR reconciliation.

## References

[1]: ./schemas.py "Opaque pairing and workflow request schemas"
[2]: ./main.py "Ward workflow endpoints and state transitions"
[3]: ./models.py "Session, digest, pointer and forensic persistence models"
[4]: ./DEVICE_TRUST_BASELINE_REPORT.md "Device Trust baseline"
[5]: ./PRODUCT_DIFFERENTIATORS.md "Strategic product differentiators"
