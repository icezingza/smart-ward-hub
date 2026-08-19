# Smart Ward Hub — Strategic Product Differentiators

**สถานะ:** Product positioning record  
**Product status:** controlled production prototype; pilot-ready foundation; clinical validation pending

## 1. Core positioning

Smart Ward Hub ไม่ได้วางตำแหน่งเป็นเพียงระบบรับสัญญาณชีพหรือ dashboard ของโรงพยาบาล แต่เป็น **Sovereign Edge Patient Monitoring Platform** ที่ออกแบบให้การติดตามผู้ป่วยยังทำงานได้ใกล้จุดดูแล แม้การเชื่อมต่อกับระบบส่วนกลางจะไม่ต่อเนื่อง พร้อมรักษาขอบเขตข้อมูลให้แคบ ตรวจสอบลำดับข้อมูล และสร้างหลักฐานเหตุการณ์ที่ตรวจพบการแก้ไขได้

จุดเด่นเชิงกลยุทธ์ที่ต้องบันทึกไว้เป็นแกนของผลิตภัณฑ์คือ:

> **Sovereign Device Trust & Secure Provisioning:** ยืนยันว่าอุปกรณ์ที่ส่งข้อมูลเข้าสู่ Ward Edge เป็นอุปกรณ์ที่ผ่านการลงทะเบียนและมีตัวตนเชิงเข้ารหัส พร้อมวางเส้นทางความน่าเชื่อถือจาก device identity ไปยัง signed telemetry, replay protection และ tamper-evident evidence โดยไม่ดึง PII ของผู้ป่วยเข้ามาไว้บน Edge โดยไม่จำเป็น

แนวคิดนี้เป็น **strategic differentiator และ product direction** ที่มี software baseline แล้วในชั้น `Device Trust & Secure Provisioning Layer` ซึ่งแยกจาก patient pairing และยังต้องพัฒนาต่อด้าน manufacturer CA, hardware-backed keys และ external anchoring. ต้องไม่ถูกสื่อสารเกินหลักฐานว่าเป็น anti-spoofing 100%, tamper-proof หรือ production-ready security certification.

## 2. จุดขายหลักของผลิตภัณฑ์

| จุดขาย | คุณค่าต่อโรงพยาบาล | หลักฐาน/สถานะปัจจุบัน |
|---|---|---|
| **Sovereign Edge / Offline-first** | การประมวลผลและเก็บข้อมูลสำคัญที่ Ward Edge ลดการพึ่งพา cloud หรือ connectivity ต่อเนื่อง | SQLite WAL, bounded buffer, checkpoint recovery และ pilot simulation; hardware/network validation pending |
| **Zero-PII by design** | Edge ใช้ `patient_token` และไม่เก็บชื่อหรือ HN โดยตรง ลดขอบเขตข้อมูลที่ต้องปกป้อง | `models.py`, `schemas.py`, security regression; host/downstream scan pending |
| **Patient Safety Intelligence** | ตรวจ pattern ของ fall และ vital anomaly ในพื้นที่ใกล้ผู้ป่วย พร้อมเก็บ alert lifecycle/evidence สำหรับ human review | triage และ simulation ผ่าน functional verification; clinical validation pending |
| **Tamper-Evident Evidence** | freeze forensic package, hash chain, verification และ local anchor adapter ช่วยตรวจพบความไม่สอดคล้องของหลักฐาน | SHA-256 chain และ tests ผ่าน; external WORM, trusted timestamp และ key custody pending |
| **HIS/EMR Interoperability** | สร้าง FHIR handover bundle และกำหนด acknowledgment gate ก่อน purge ลดความเสี่ยงจาก sync ที่ไม่สมบูรณ์ | FHIR contract และ idempotent sync tests ผ่าน; real HIS integration pending |
| **Device Trust & Secure Provisioning** | วางรากฐานให้ Hub รับข้อมูลจากอุปกรณ์ที่มี identity และ provenance ที่ตรวจสอบได้ ไม่ใช่เพียงตรวจ payload รูปแบบถูกต้อง | public-key enrollment, Ed25519 signed telemetry, sequence/replay protection และ lifecycle baseline implemented; manufacturer CA, secure hardware และ external anchoring pending |
| **Safe Trust Degradation** | หาก device/network/geofence trust ลดลง ระบบควรแจ้งเตือนและรักษา monitoring continuity แทนการหยุดติดตามผู้ป่วยโดยอัตโนมัติ | เป็น safety design principle; hardware/geofence implementation pending |

## 3. Device-to-evidence trust chain

แนวคิดหลักของผลิตภัณฑ์คือการสร้าง trust chain แบบเป็นชั้น ไม่ใช่การอ้างว่ามี security feature เดียวที่แก้ทุกความเสี่ยง:

```text
Factory / Manufacturer Identity
        ↓
Secure Device Enrollment and Key Lifecycle
        ↓
Ward Edge Device Registration
        ↓
Canonical TelemetryPacket v1 + Signed Security Envelope
        ↓
Monotonic Sequence and Replay Protection
        ↓
Zero-PII Edge Buffer and Patient-Safety Triage
        ↓
Durable Aggregate / Frozen Forensic Package
        ↓
Tamper-Evident Hash Chain
        ↓
External Append-only / WORM Evidence Anchor (planned validation gate)
```

ในชั้นที่มี implementation แล้ว ระบบมี `TelemetryPacket v1`, Ed25519 public-key enrollment, canonical signed telemetry envelope, per-device sequence enforcement, bounded thread-safe buffer, durable forensic package และ local hash verification. ชั้น manufacturer certificate/CA, secure element/HSM และ external WORM anchor เป็น roadmap/validation gates ที่ยังไม่ควรถูกนำเสนอว่าเสร็จสมบูรณ์แล้ว

## 4. Product language ที่ควรใช้

### Recommended wording

> “Smart Ward Hub is a sovereign, offline-first ward edge platform with Zero-PII data minimization, patient-safety decision support, replay-aware telemetry ingestion, and tamper-evident forensic evidence. Its Device Trust baseline verifies canonical signed telemetry, while manufacturer-authenticated provisioning and hardware-backed key custody remain validation gates.”

> “The platform is designed to establish a device-to-evidence trust chain: registered device identity, canonical telemetry, sequence protection, local safety intelligence, and externally anchored evidence as a controlled deployment gate.”

### Wording ที่ห้ามใช้จากหลักฐานปัจจุบัน

| ห้ามใช้ | เหตุผล |
|---|---|
| “Anti-spoofing 100%” | ยังไม่มี hardware key custody, secure-element testing และ adversarial validation |
| “Tamper-proof” | local hash chain และ local anchor เป็น tamper-evident ภายใน trust boundary เดียว |
| “Clinical-ready” | ยังไม่มี clinical protocol, sensitivity/specificity และ governance sign-off |
| “HIPAA/PDPA compliant 100%” | software schema อย่างเดียวไม่ใช่ regulatory compliance ทั้งระบบ |
| “Production-ready” | ยังมี OIDC/mTLS จริง, hardware/network, HIS, host hardening และ power-loss gates |
| “Device will brick immediately outside geofence” | อาจทำลาย patient-safety continuity จาก false positive หรือ network outage |

## 5. Roadmap ของจุดเด่น Device Trust

| Phase | Capability | Acceptance evidence | สถานะ |
|---|---|---|---|
| DT-0 | Current device registration and per-device sequence control | duplicate/out-of-order/restart replay tests | Implemented baseline |
| DT-1 | Manufacturer public-key certificate verification | forged certificate rejected; public key only on Hub | Planned P0 |
| DT-2 | Signed telemetry envelope over canonical v1 fields | any field modification fails verification | Implemented software baseline |
| DT-3 | Key lifecycle: active, rotate, suspend, revoke, expire | lifecycle audit and recovery tests | Implemented baseline; hardware custody pending |
| DT-4 | Secure element/HSM-backed key custody | extraction-resistance and power-loss evidence | External validation |
| DT-5 | Safe geofence/trust degradation | alert/quarantine without automatic monitoring stop | Planned P1; safety review required |
| DT-6 | External append-only/WORM evidence anchor | independent verification and retention drill | External validation |

## 6. Strategic message for stakeholders

สำหรับผู้บริหารโรงพยาบาล จุดขายไม่ควรเป็นเพียง “มี AI” แต่ควรเป็นการสร้าง **trusted ward-local operating layer** ที่ลดการส่งข้อมูลเกินจำเป็น, ทำงานต่อได้เมื่อระบบกลางไม่พร้อม, ทำให้การรับ telemetry มี provenance และลำดับที่ตรวจสอบได้, และช่วยรักษา evidence continuity สำหรับการทบทวนโดยเจ้าหน้าที่

สำหรับฝ่ายเทคนิค จุดแตกต่างคือการออกแบบ trust boundary ตั้งแต่ device enrollment ไปจนถึง evidence preservation โดยไม่รวม private key หรือ identity mapping ที่ละเอียดอ่อนเข้าไว้ใน Edge source code และไม่บังคับให้ patient monitoring หยุดทันทีเมื่อ trust signal ลดลง

สำหรับฝ่ายคลินิกและ governance จุดขายต้องถูกนำเสนอเป็น **decision-support foundation** ไม่ใช่ระบบวินิจฉัยอัตโนมัติ และทุก capability ที่เกี่ยวกับ alert threshold, geofence, device quarantine หรือ evidence admissibility ต้องผ่าน clinical, security และ operational review แยกกัน

## 7. Claim boundary

เอกสารนี้บันทึกจุดขายเชิงกลยุทธ์ ไม่ใช่หลักฐานว่า Device Trust layer เสร็จสมบูรณ์แล้ว. สถานะที่ถูกต้องคือ **P0-hardened software baseline with Device Trust signed-telemetry and lifecycle baseline; manufacturer provisioning roadmap remains open**.
 การนำไปใช้จริงต้องผ่าน pilot deployment configuration, hardware validation, external security validation, real HIS integration และ clinical validation ตามลำดับ.

## References

[1]: ./EDGE_HUB_ARCHITECTURE.md "Edge Hub architecture and trust boundaries"
[2]: ./SECURITY_BASELINE.md "Security baseline and evidence boundaries"
[3]: ./RISK_REGISTER.md "Risk register"
[4]: ./RESIDUAL_HARDENING_REPORT.md "Residual hardening report"


## 8. Ward workflow as a product differentiator

The operational differentiator is not merely NFC convenience. It is a **state-aware, fail-safe, auditable tap workflow**: intentional bed selection for Input, NFC pointer lookup for fast Output, `RESET_PENDING` before destructive transition, separate sessions for hot-swap, and a clear distinction between routine session digest and incident-triggered forensic freeze.

This allows Smart Ward Hub to reduce interaction cost without treating “one tap” as permission to silently discard monitoring evidence. The workflow preserves Zero-PII by requiring Admission Gateway tokenization before Hub Core, preserves Device Trust by treating NFC as a pointer rather than proof, and preserves Patient Safety by blocking reset when an unresolved incident has not been frozen.


## 9. Outside-in Ward Workflow for large wards

Smart Ward Hub can extend beyond a stationary nurse-station screen with an **Outside-in Ward Workflow**. An Acer Spin or other controlled console faces the ward entrance for authenticated admission preparation, while the protected Fixed Hub remains the authoritative Edge source of truth and a BMAX-class Tablet supports walk-round inspection inside the ward.

This creates a practical operational advantage: a nurse can prepare an admission from the controlled area outside the ward without walking into the ward for every registration step, then complete physical device pairing and safety confirmation inside the protected workflow. The design reduces unnecessary movement without exposing raw HN/AN to Hub Core or turning an outside console into a public patient lookup.

Approved product wording is: **“Outside-in Ward Workflow: admission starts at a controlled ward entrance, local truth and evidence stay inside the protected Edge boundary, and managed roaming Tablets support walk-round care.”** The software baseline now implements non-PII bed availability snapshots, reservation timeout, idempotent admission preparation, loopback-only Admission Console access and pairing commit/release. Real HIS/Admission Gateway integration, privacy placement, operator ergonomics and clinical workflow validation remain open gates. See `OUTSIDE_IN_WARD_WORKFLOW.md`.


## 10. Sovereign Ward Operating Layer for large wards

For large or multi-room wards, Smart Ward Hub extends from a stationary console into a **Sovereign Ward Operating Layer**: the Fixed Hub keeps authoritative local state and evidence, while managed Roaming Tablets give nurses mobility during walk-rounds without copying the patient identity store or splitting clinical state across devices.

The current software baseline implements a non-PII snapshot cursor, freshness/trust/session indicators, revision-aware command submission, durable command idempotency, alert acknowledgement and safe `RESET_REQUEST` handling. The product message must remain bounded: real managed Android identity, hospital OIDC, encrypted mobile cache, ward Wi-Fi roaming, push notifications and clinical human-factors validation remain external gates.

Approved wording is: **“Fixed Hub truth, mobile ward reach: nurses can walk-round with a managed Tablet while authoritative patient-device state and evidence remain sovereign at the Ward Edge.”** This is a software-verified foundation for large-ward deployment, not a claim of validated mobile clinical operation.
