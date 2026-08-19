# Smart Ward Hub — Reference Design

**สถานะ:** Controlled production prototype reference design  
**การใช้งาน:** ใช้กำหนดต้นแบบ hardware/UI/Edge integration; ยังไม่ใช่ final industrial design หรือ clinical-certified device

## 1. แนวคิดหลัก

Smart Ward Hub ควรถูกออกแบบเป็น **Ward Edge Appliance** ที่ทำงานได้แม้ HIS หรือ WAN ขัดข้อง โดยมีหน้าที่หลักคือรับข้อมูลจากอุปกรณ์, ประมวลผลความปลอดภัยใกล้ผู้ป่วย, แสดงสถานะให้เจ้าหน้าที่ และเก็บ evidence ภายใต้ Zero-PII boundary ไม่ใช่เป็น thin client ที่ต้องส่งข้อมูลผู้ป่วยทั้งหมดขึ้น cloud

การออกแบบควรแยกเป็น 4 ชั้น:

| ชั้น | หน้าที่ | หลักการ |
|---|---|---|
| Physical Hub | จอ, NFC, scanner, speaker, status light, compute และ power | ทำความสะอาดง่าย, ไม่มีส่วนที่กดผิดง่าย, serviceable |
| Interaction | pairing, output reset, hot-swap, discharge, incident | ลด interaction cost แต่ไม่ลด safety gate |
| Edge Runtime | BLE/proxy, Device Trust, ring buffer, triage, SQLite, forensic | Offline-first, fail-safe, Zero-PII |
| Integration Boundary | Admission Gateway, HIS/FHIR, OIDC/mTLS, backup/anchor | แยก trust boundary และเปิดใช้งานตาม pilot gate |

## 2. รูปแบบตัวเครื่องที่แนะนำ

รูปแบบที่เหมาะกับ prototype ตามข้อสรุปล่าสุดคือ **Tablet-only countertop kiosk สำหรับ nurse station** ไม่ใช่ Notebook และไม่ใช่เพียงจอ remote โดยตัว Tablet ต้องทำหน้าที่เป็นทั้งหน้าจอและ Edge compute appliance ที่รัน local service, SQLite/WAL, Device Trust, buffer, triage และ forensic workflow ได้ในเครื่องเดียว

```text
┌────────────────────────────────────────────────────────────┐
│  Smart Ward Hub — Edge Ward Console                       │
│                                                            │
│  [Ward status] [Offline/Sync] [Security] [Clock]           │
│                                                            │
│  BED-01  ● Stable      BED-02  ▲ Attention                 │
│  BED-03  ● Stable      BED-04  ! RED / Human review        │
│                                                            │
│        ┌───────────────┐                                   │
│        │ NFC TAP ZONE  │  ← ring light + short sound        │
│        └───────────────┘                                   │
│                                                            │
│  [optional barcode scanner input through Admission Gateway] │
│  [service cover / USB / Ethernet on rear side only]         │
└────────────────────────────────────────────────────────────┘
      │ protected DC power + UPS/supervision
      └── separate multi-bay charging dock for C60 devices
```

### Physical modules

| Module | Reference choice | Design constraint |
|---|---|---|
| Compute | Rugged Linux-capable x86/ARM tablet or controlled Windows IoT tablet | Local service supervision, encrypted storage, secure boot/TPM where available, kiosk policy and recovery support |
| Display | 10–15 inch high-brightness touch display | Large tap targets, glove use assessment, cleaning-compatible surface |
| NFC | Reader placed in a single high-contrast landing zone | NFC is only a pointer; do not treat UID as device proof |
| Barcode/QR | Optional scanner connected to Admission Gateway boundary | Raw HN/AN must be tokenized before Hub Core |
| BLE | Tablet BLE interface where stable; optional external BLE/attested proxy when C60 cannot sign directly | Proxy identity and key custody must be independently validated; proxy is not the device root of trust |
| Audio/light | Short confirmation beep and ring/status LED | Must not be the only safety confirmation for reset or incident actions |
| Storage | Tablet encrypted local storage with SQLite WAL and checkpoint partition | Separate database, audit, checkpoint and forensic paths; storage wear and recovery must be tested |
| Network | Wired Ethernet as primary; Wi-Fi only if hospital security approves | Ward VLAN isolation, no direct public internet dependency |
| Power | Protected DC supply with UPS or supervised battery path | Power-loss and graceful recovery tests are external gates |
| Charging | Separate labeled multi-bay dock | Do not make charging placement part of an unsafe automatic reset trigger |

A camera is not required for the core design. Omitting it reduces privacy scope and avoids introducing face or barcode image retention unless a hospital requirement explicitly justifies it.

## 3. Interaction design

### Input: deliberate pairing

The nurse selects a bed, then taps a registered device or resolves its NFC pointer. The Hub validates the opaque patient/encounter token, device registry, Device Trust status and operator scope before creating a new `WardSession`. The UI should show the selected bed and target device together before the final commit.

### Output: state-aware reset

An NFC tap on an active device is a **reset request**, not an immediate destructive command. The Hub enters `RESET_PENDING`, emits a short signal and shows the device, bed and session status. The operator must explicitly confirm `RESET`. If the session has an unresolved incident and no incident forensic package, reset remains blocked.

### Hot-swap and discharge

Hot-swap is available only for the same patient/encounter and creates a new session with a new device sequence boundary and an opaque `handover_id`. Discharge closes the session and returns the device to `READY_FOR_CHARGE`. These actions should be separate buttons or workflows, even if both ultimately clear the active pairing.

### Suggested UI information hierarchy

| Region | Information |
|---|---|
| Header | Ward identity, current time, offline/sync status, storage/power warnings |
| Bed grid | Bed number, device state, trust state, battery, latest signal age and alert level |
| Selected-bed panel | Opaque session/device reference, pairing action, hot-swap and reset state |
| Alert panel | Human-review queue, severity, time, acknowledgement and escalation state |
| Security panel | Device Trust mode, unverified count, revoked/expired credentials and audit status |
| Maintenance panel | Migration/readiness, backup freshness, certificate/token expiry and operator role |

Color must never be the only signal. RED should combine color, text, icon and a clear human-review action. “Offline” must be visible without implying that local monitoring has stopped.

## 4. Edge software layout

```text
C60 / BLE devices
       │
       ▼
BLE or Attested Ingestion Proxy
       │  device_id, key_id, signature, sequence
       ▼
Device Trust Verification
       │
       ├── disabled / observe / enforce mode
       ├── canonical TelemetryPacket v1
       └── sequence and replay guard
       ▼
EdgeTelemetryStore (bounded per-device buffer)
       │
       ├── triage and silent-fall decision support
       ├── alert lifecycle and human review
       ├── routine SessionCloseDigest
       └── Incident Forensic Freeze
       ▼
SQLite WAL source of truth + local audit/anchor adapters
       │
       └── optional HIS/FHIR sync through authenticated boundary
```

The Admission Gateway may be physically attached to the same tablet kiosk through a scanner or separate authorized service, but it must remain a separate logical process/service boundary. Its responsibility is to convert raw HN/AN into an opaque token; Hub Core must not persist the raw value in application logs, cache, checkpoints or database rows.

When the C60 cannot sign telemetry, the BLE Gateway may provide a transitional attested-ingestion-proxy signature. The UI and evidence model must label this as **proxy-attested transport**, not manufacturer-authenticated device identity. A future OEM device with hardware-backed signing can move the trust anchor closer to the wristband.

## 5. Network and security topology

```text
[Wearables/BLE]
      │ local radio
      ▼
[Wearable BLE] ──> [Tablet BLE or optional proxy boundary]
                                      │
                                      ▼
                              [Tablet Edge VLAN]
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                 [Kiosk UI/API]              [SQLite WAL]
                         │                         │
                         └──── authenticated HIS/FHIR egress ────┘
```

The Hub should continue local monitoring when HIS/WAN is unavailable. External sync is an integration path, not a prerequisite for local alert evaluation. Administrative access should use a separate maintenance path with OIDC/mTLS and should not be exposed through the ward-facing UI network.

The minimum security baseline includes secure boot or measured boot where supported, encrypted storage, least-privilege service account, disabled unused ports, firewall allow-list, certificate/token rotation, audit export, backup/restore drill and physical tamper/maintenance procedure. These are pilot gates, not claims already proven by software simulation.

## 6. Power and failure behavior

The power path should be designed so the Hub can detect low power, persist critical state and recover without duplicating telemetry. A reference path is protected DC input → tablet dock/UPS supervision → Tablet Edge runtime, with separate charging power for the C60 device dock. The Hub must show `POWER_DEGRADED` before shutdown and record a request/audit event for an orderly stop when possible.

The acceptance sequence is:

1. normal operation with local telemetry;
2. short power interruption with no duplicate pairing or handover;
3. hard power loss during telemetry ingestion;
4. restart and checkpoint recovery;
5. disk-full and audit-path failure behavior;
6. manual clinical fallback if monitoring continuity cannot be guaranteed.

No claim about power-loss safety is valid until this is tested on the selected hardware.

## 7. Prototype build stages

| Stage | Build | Exit gate |
|---|---|---|
| P0 | UI mock + NFC reader + simulated device gateway | Interaction flow and state terminology approved |
| P1 | Tablet-only bench kiosk with real NFC, BLE interface/proxy and supervised dock power | Auto-boot, restore, pairing, reset, hot-swap, discharge and offline continuity pass |
| P2 | Hardware-in-loop with C60 and representative network faults | Signature/proxy behavior, clock drift, reconnect and power-loss evidence |
| P3 | Ward shadow mode | Clinical workflow review, alarm fatigue observation, no automatic destructive action |
| P4 | Controlled pilot | OIDC/mTLS/HIS configuration, backup/restore, operator training and stop conditions approved |

## 8. Design decision summary

The Hub should be **a Tablet-only kiosk that auto-runs at boot, restores the latest known operational state, is small enough for a nurse station, visible enough to function as a safety console, and isolated enough to preserve sovereignty and Zero-PII**. NFC should make the interaction fast, but never replace cryptographic trust. The one-tap experience should reduce interaction cost without bypassing `RESET_PENDING`, incident freeze or human confirmation. The first physical prototype should validate auto-boot, stale-state recovery, ergonomics and failure behavior before any claim about clinical readiness or hardware security is made.


## 9. Current hardware allocation decision

For the current codebase, the Acer Spin N17H2 is the stronger **Edge host prototype** because its x86 Windows/Linux path can run the existing Python/FastAPI service, SQLite/WAL and kiosk templates. The BMAX i11_s is the stronger **lightweight touch/UI candidate**, but it must first pass Android device-owner/kiosk, local runtime, storage, NFC/BLE and power tests before it can be the single sovereign Edge device.

If only one device may be used immediately, start with Acer and validate the Tablet-only auto-run/restore behavior there. Use BMAX in a later touch-display or Android-native experiment unless its actual firmware and device-owner capabilities prove suitable for the local Edge backend.
