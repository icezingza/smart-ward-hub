# Smart Ward Hub — Outside-in Ward Workflow

**Status:** Outside-facing Admission Console and Bed Availability software baseline  
**Purpose:** ลงทะเบียนผู้ป่วยจากหน้าวอร์ด ลดการเดินเข้าออก และรักษา Zero-PII/source-of-truth boundary  
**Clinical status:** clinical validation pending

## 1. Design decision

สำหรับวอร์ดที่มีพื้นที่กว้างหรือมีทางเข้าออกที่ควบคุมชัดเจน ควรแบ่งระบบเป็น 3 zones:

```text
[Outside / Ward entrance]
  Admission Console
  Acer Spin / fixed touch notebook
  Scanner + authenticated admission workflow
          │ tokenized handoff over controlled ward network
          ▼
[Inside / Nurse station or protected equipment zone]
  Fixed Edge Hub
  Source of truth: SQLite/WAL, Device Trust, telemetry, triage, evidence
          │ managed ward Wi-Fi
          ▼
[Inside / Ward floor]
  BMAX Roaming Tablet
  Walk-round view, alerts, NFC pointer, safe commands
```

The Acer-facing console can be physically oriented toward the outside of the ward while the protected Edge service and storage remain inside the trusted ward zone. The outer screen must not display raw patient identity after the admission transaction completes, and it must not expose the administrative API directly to a public corridor or visitor network.

## 2. Device roles

| Zone | Device | Primary role | Must not do |
|---|---|---|---|
| Outside entrance | Acer Spin N17H2 / Admission Console | Admission registration, tokenization handoff, bed/encounter preparation and operator confirmation | Must not become a public unauthenticated identity lookup or expose full ward telemetry |
| Inside protected station | Fixed Edge Hub | Authoritative pairing, telemetry, session, alerts, forensic evidence, Device Trust and HIS/FHIR boundary | Must not depend on the outer console remaining powered for local monitoring |
| Inside ward floor | BMAX i11_s / Roaming Tablet | Walk-round display, acknowledge/escalate, NFC pointer lookup and safe session requests | Must not become an independent telemetry source or overwrite Hub state offline |

If only one device is available for the first bench prototype, the Acer may temporarily perform both outside admission and Fixed Hub roles. The deployment should still preserve logical zones and API boundaries so the design can later separate the physical console from the Edge source of truth.

## 3. Outside admission flow

```text
Operator authenticates outside ward
        ↓
Scan Admission Slip / HIS-approved identifier
        ↓
Admission Gateway resolves raw HN/AN
        ↓
Hub receives opaque patient_token/encounter_token only
        ↓
Operator selects bed or prepared ward destination
        ↓
Fixed Hub creates admission/session preparation record
        ↓
Inside nurse receives new admission task on fixed/roaming UI
        ↓
NFC device pairing happens inside the controlled ward workflow
```

The outside console may temporarily process raw HN/AN only inside an authorized Admission Gateway boundary. Raw HN/AN must not be written to the Hub Core database, audit log, checkpoint, roaming cache or forensic package. The handoff to Hub Core is an opaque token plus the minimum encounter/bed metadata required to complete pairing.

The current software baseline exposes a local Outside Admission Console at `/admission`, an authoritative non-PII snapshot at `GET /api/v1/outside/bed-availability` (or loopback-only `/api/v1/outside/local-bed-availability`), admission preparation at `POST /api/v1/outside/admission-preparations` (or loopback-only `/api/v1/outside/local-admission-preparations`), idempotent replay by `idempotency_key`, cancellation, bed-state management and reservation expiry. A successful preparation returns `PREPARED`/`RESERVED` semantics; physical pairing is still a separate step and commits the preparation to `COMMITTED`/`OCCUPIED`.

A registration at the outside console is not the same as physical device pairing. The system should use explicit statuses such as `ADMISSION_PREPARED`, `AWAITING_DEVICE_PAIRING`, `PAIRED_ACTIVE`, `RESET_PENDING`, `SESSION_CLOSED` and `READY_FOR_CHARGE`.

## 4. Privacy and physical placement

The outer console should use a privacy angle or privacy filter, minimize text displayed after the scan, auto-lock quickly, disable screenshots/clipboard where possible and avoid showing a ward-wide patient list. The screen should show only the admission task and the selected bed/encounter context needed by the authorized operator.

The console should be mounted on the **inside edge of the ward entrance or a controlled registration alcove**, not in a public corridor where visitors can read the screen or reach USB/NFC/service ports. The fixed Edge storage and maintenance ports should remain on the protected side. If the nurse must stand outside while registering, the UI should complete the tokenization and hand off a task without requiring raw identity to remain visible.

## 5. Tokenized data contract

| Data | Outside console | Hub Core | Roaming Tablet |
|---|---|---|---|
| Raw HN/AN | Admission Gateway only, temporary and access-controlled | No | No |
| Patient name | Only if required by hospital-authorized admission UI | No | No in the Zero-PII baseline |
| `patient_token` | May receive/forward after tokenization | Yes, pseudonymous reference | Minimum required for session workflow, preferably not displayed |
| `encounter_token` | May receive/forward after tokenization | Yes, session-scoped reference | Minimum required for reconciliation |
| Bed number | Yes | Yes | Yes |
| `device_id/key_id` | Lookup/task metadata only | Yes | Yes, subject to scope |
| Telemetry | No full telemetry by default | Yes, authoritative | Freshness/alert summary only |

## 6. Failure and safety behavior

If the connection between the outside console and Fixed Hub is unavailable, the console must show `ADMISSION HANDOFF UNAVAILABLE` and must not imply that the patient is registered in the ward. It may retain a short-lived, encrypted, access-controlled pending task only if hospital policy approves; the task becomes authoritative only after the Fixed Hub acknowledges it.

If the Fixed Hub is offline but local monitoring remains healthy, an admission task may be queued according to policy, but physical pairing and clinical session activation should be completed through the documented manual fallback or a controlled local workflow. The outside console must never create a second independent source of truth.

If the Roaming Tablet is offline, the inside fixed display remains authoritative. The roaming device shows last-known state and cannot complete destructive actions such as reset, discharge or hot-swap until it reconnects to the Fixed Hub.

## 7. Security and audit requirements

The outside console requires operator authentication, short session timeout, role/scope restriction and audit of admission preparation, tokenization handoff, bed selection, failure and cancellation. Device identity and admission identity must remain separate. A successful admission preparation must not imply that a C60 device has been cryptographically enrolled or paired.

All handoff operations require a `request_id`, `command_id`, `idempotency_key`, `actor_id`, `console_id`, timestamp and outcome. Duplicate handoff submissions must return the original authoritative result rather than create a second admission/session.

## 8. Acceptance gates

| Gate | Pass condition |
|---|---|
| Outside registration | Operator can prepare an admission without entering the ward |
| Zero-PII handoff | Raw HN/AN is absent from Hub database, logs, cache, checkpoint and roaming payload |
| Privacy placement | Visitor cannot read the screen or access service ports under normal placement |
| Connectivity failure | No false success; pending handoff is visibly distinct from accepted registration |
| Duplicate scan | Idempotency prevents duplicate admission/session creation |
| Inside pairing | Device pairing remains a separate authenticated action with NFC/Device Trust verification |
| Ward continuity | Fixed Hub continues local monitoring if the outside console is unavailable |
| Roaming continuity | BMAX can display last-known state with freshness and reconciliation status |
| Audit | Admission preparation, handoff, cancellation and failure are traceable without raw patient identity |

## 9. Product value

This layout creates an **Outside-in Ward Workflow**: registration begins at the controlled ward entrance, the authoritative Edge state stays inside the protected ward zone, and nurses move through the ward with a lightweight roaming tablet. The software baseline now verifies bed availability, reservation, expiry, idempotent admission preparation and pairing commit; real HIS/Admission Gateway integration, privacy placement and clinical workflow validation remain open gates.

## References

[1]: ./WARD_WORKFLOW_CONTRACT.md "Ward workflow and session contract"
[2]: ./ROAMING_TABLET_ARCHITECTURE.md "Fixed Hub plus Roaming Tablet architecture"
[3]: ./TABLET_HARDWARE_DECISION.md "Acer/BMAX hardware-role decision"
[4]: ./schemas.py "Opaque patient token pairing contract"
