# Smart Ward Hub — Edge Hub Architecture

## Purpose

The Edge Hub is the ward-local runtime that accepts authenticated telemetry from registered devices, validates a single versioned packet contract, performs local safety evaluation, buffers data offline, and writes durable aggregates or forensic packages without requiring continuous connectivity to the hospital core.

The Edge Hub stores **pseudonymized references only**. It must not store patient names, HN values, or a patient-token mapping table. The mapping between `patient_token` and identifiable hospital records belongs to the HIS or another controlled identity service.

## Directory structure

```text
smart-ward-hub/
├── database.py                 # SQLite WAL engine and SQLAlchemy sessions
├── models.py                   # Zero-PII relational models and durable aggregates
├── schemas.py                  # Pydantic contracts, including TelemetryPacket v1
├── security.py                 # Configured bearer-token scopes; fail-closed behavior
├── device_trust.py             # Canonical Ed25519 envelope verification and key fingerprints
├── edge_runtime.py             # Thread-safe bounded buffers and checkpoint recovery
├── main.py                     # FastAPI routes, pairing, ingestion, triage, FHIR, forensics
├── test_edge_runtime.py        # PII guard, overflow, ordering, recovery tests
├── test_security.py            # Auth, scopes, Zero-PII, schema-lockdown tests
├── test_device_trust.py        # Enforce-mode enrollment, mutation, replay, revocation tests
├── test_device_trust_observe.py # Observe-mode continuity test
├── run_all_tests.py            # Master regression runner
├── simulate_pilot_30days.py    # Software-only pilot simulation
├── SECURITY_BASELINE.md        # Security evidence and residual risk
└── KNOWLEDGE_UPDATE_2026-08.md # Verified research guidance from Notebook and references
```

## Trust boundaries

| Boundary | Data permitted | Required control |
|---|---|---|
| Wristband → Edge Hub | Device identity, sequence, sensor values, timestamps, battery | Device authentication, schema validation, replay/order checks |
| Edge Hub operational store | Device IDs, bed IDs, pseudonymous patient tokens, aggregates, alerts | SQLite permissions, WAL, encryption/backup policy, least privilege |
| Edge Hub → Nurse UI | Bed context, alert state, operational metrics | Scoped authorization, no direct PII, audit logging |
| Edge Hub → HIS/EMR | FHIR bundle and pseudonymous reference as agreed by hospital | mTLS, OAuth2/OIDC service identity, acknowledgment, retry/idempotency |
| Edge Hub → Evidence service | Digest, signature, timestamp, chain-of-custody metadata | Key custody, append-only external anchor, trusted timestamp |

## TelemetryPacket v1

The canonical packet uses one contract only:

```json
{
  "schema_version": "1.0",
  "device_id": "MAC-A1:B2:C3:D4:E5:F6",
  "sequence": 42,
  "timestamp": "2026-08-19T10:00:00Z",
  "ppg": 0.82,
  "accel_x": 0.01,
  "accel_y": -0.02,
  "accel_z": 1.00,
  "skin_temp": 36.7,
  "battery_pct": 88.0,
  "heart_rate": 76.0,
  "spo2": 98.0
}
```

`sequence` is monotonic per device. A duplicate or out-of-order packet returns HTTP 409 and is not appended. The `edge_runtime.py` store rejects identity fields such as `name`, `patient_id`, `patient_name`, `patient_token`, `hn`, and `hospital_number` so PII cannot enter the raw telemetry buffer through accidental field reuse.

## Buffer and recovery behavior

`EdgeTelemetryStore` is thread-safe and bounded per device. When a device reaches the configured maximum, the oldest sample is evicted and the response exposes a `dropped_samples` counter. The store periodically writes an atomic JSON checkpoint to `SW_TELEMETRY_STATE_PATH`. On process restart it restores the most recent bounded snapshot and the last accepted sequence for each device.

The checkpoint is an operational recovery aid, not a forensic archive. It must be protected with filesystem permissions and should be encrypted or placed on an encrypted volume in production. Forensic packages remain a separate durable evidence layer.

## Runtime configuration

```bash
export SW_AUTH_TOKENS_JSON='{"edge-service-token":["pairing:write","telemetry:write","telemetry:read","forensics:read","handover:read","handover:sync"]}'
export SW_TELEMETRY_STATE_PATH=/var/lib/smart-ward-hub/edge_telemetry_state.json
export SW_TELEMETRY_CHECKPOINT_EVERY=128
uvicorn main:app --host 127.0.0.1 --port 8000
```

The current token mechanism is a configurable security baseline. Production should replace static tokens with OAuth2/OIDC and use mTLS for Hub-to-HIS communication.

## Operational rules

The Edge Hub must fail closed when authentication is not configured. A failed FHIR synchronization must retain local aggregates. Auto-Purge is allowed only after a verified acknowledgment with HTTP status 200 and an idempotent bundle identifier. A RED alert is a clinical decision-support signal and must not be treated as an automated diagnosis or treatment instruction.

## Current evidence level

The implementation and regression suite verify functional software behavior. They do not establish clinical sensitivity/specificity, hardware durability, battery life, radio performance, regulatory compliance, or legal admissibility of forensic records. Those claims require independent validation and governance review.


## Strategic product differentiator: Device Trust & Secure Provisioning

Smart Ward Hub is positioned as a **Sovereign Edge Patient Monitoring Platform**, not merely a telemetry dashboard. A future Device Trust & Secure Provisioning Layer will establish a controlled trust chain from manufacturer-authenticated device identity to canonical `TelemetryPacket v1`, sequence/replay protection, Zero-PII Edge processing, frozen forensic packages, and an independently administered evidence anchor.

The device-trust layer must remain separate from patient pairing. Factory enrollment verifies device provenance and key lifecycle; operational pairing then binds a registered device to a bed and `patient_token` under the existing authenticated operator flow. Manufacturer private keys must not be stored in the repository or as plaintext master secrets on the Hub. The intended production design uses asymmetric certificate verification or an equivalent public-key trust model, followed by signed telemetry over a canonical serialization of the complete packet.

This is a **strategic differentiator with an implemented software baseline and an open hardware/manufacturer roadmap**. The current software evidence supports Ed25519 public-key enrollment, canonical signed telemetry verification in enforce mode, per-device sequence enforcement, basic credential lifecycle states, bounded recovery, Zero-PII processing, and tamper-evident local evidence. Manufacturer CA verification, secure-element/HSM-backed key custody, and external WORM anchoring remain planned or externally validated capabilities.

Device trust must degrade safely. A geofence or device-authentication anomaly should generate an alert, audit event, and controlled quarantine/degraded-trust state; it must not automatically brick a patient-monitoring device or stop monitoring solely because of a transient network or location signal.

See `PRODUCT_DIFFERENTIATORS.md` for the approved stakeholder language, product claims, and Device Trust roadmap.


## Ward interaction workflow and session evidence

The approved ward interaction model separates intentional **Input** from fast **Output**. Input is an authenticated operator action that selects a bed and associates an enrolled device/session. Output begins with an NFC pointer lookup, but an active session enters `RESET_PENDING` and requires explicit visual confirmation before the pairing is closed. NFC is a lookup index only; Device Trust signatures and sequence protection remain the telemetry proof.

Raw HN/AN and patient identity data must be tokenized by an Admission Gateway or HIS-authorized service before entering Hub Core. Hub Core accepts only opaque `patient_token`/`encounter_token` values and maintains no identity mapping table.

Hot-swap closes the old session with a routine summary digest, creates a new session for the replacement device, and links both through an opaque `handover_id`. Discharge closes the session and returns the device to `READY_FOR_CHARGE`. Routine Session Close stores a low-volume chained digest; an unresolved incident requires an Incident-Triggered Freeze with the recent high-resolution Edge window before reset or discharge can proceed.

See `WARD_WORKFLOW_CONTRACT.md` for API, state-machine, audit and validation details.


## Physical Hub reference design

The recommended first physical form is a countertop Ward Edge Appliance at the nurse station with a high-brightness touch display, one obvious NFC tap zone, optional Admission Gateway scanner, local BLE/proxy boundary, supervised power/UPS path and a separate charging dock. The Hub is designed to remain useful during HIS/WAN interruption and must expose offline, power, trust and storage states visibly.

The physical design must keep the fast interaction model while preserving safety: deliberate bed selection for pairing, NFC pointer lookup for output, `RESET_PENDING` and explicit confirmation before session close, separate hot-swap/discharge actions, and incident freeze before reset when required. See `HUB_REFERENCE_DESIGN.md` for the reference enclosure, UI hierarchy, network topology, power-failure sequence and prototype stages.


## Fixed Hub plus Roaming Tablet for large wards

For a large ward, the recommended deployment is one authoritative Fixed Ward Hub per ward or operational zone plus managed Roaming Tablets for nurse walk-rounds. The Fixed Hub remains the source of truth for telemetry, sessions, alerts, forensic evidence, Device Trust and destructive transitions. Roaming Tablets display a minimum non-PII snapshot and submit authenticated, idempotent commands with expected revision; they do not become independent telemetry owners or direct HIS/FHIR clients.

A disconnected Roaming Tablet shows `OFFLINE — LAST KNOWN STATE` with freshness age. RESET confirmation, discharge, hot-swap, pairing changes, credential changes and purge-related actions require live Fixed Hub acknowledgement in the initial pilot. See `ROAMING_TABLET_ARCHITECTURE.md` for sync, offline queue, revision conflict, tablet identity and acceptance rules.


## Outside-in Ward Workflow

For a controlled ward entrance, the Acer Spin may face outward as an Admission Console while the Edge source of truth remains in the protected ward zone. The console handles authenticated admission preparation and tokenized handoff; it does not become a public identity lookup or independent database. The Fixed Hub completes authoritative session/pairing state, while the BMAX Roaming Tablet supports walk-round operation inside the ward.

This arrangement reduces unnecessary nurse movement without weakening Zero-PII: raw HN/AN remains within the authorized Admission Gateway boundary and only opaque tokens cross into Hub Core. See `OUTSIDE_IN_WARD_WORKFLOW.md` for zoning, privacy placement, failure, audit and acceptance gates.
