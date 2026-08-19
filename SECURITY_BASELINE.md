# Smart Ward Hub — Security Baseline

## ขอบเขตและสถานะการอ้างสิทธิ์

เอกสารฉบับนี้เป็น **engineering evidence record** ของซอฟต์แวร์ต้นแบบ Edge Hub ไม่ใช่ใบรับรอง HIPAA/PDPA ไม่ใช่ผลการรับรองทางคลินิก และไม่ใช่ความเห็นทางกฎหมาย สถานะที่ถูกต้องของระบบคือ **P0-hardened software baseline** และ **pilot deployment configuration pending**.

ระบบยังควรถูกนำเสนอในฐานะ **controlled production prototype** ที่มี **pilot-ready foundation** และมีผล **functional verification passed** ตามชุดทดสอบซอฟต์แวร์ที่ระบุไว้ ขณะที่ **clinical validation pending**.

## Controls ที่มีหลักฐานจากโค้ดและการทดสอบ

| Control | สถานะ | หลักฐาน | ขอบเขตที่ยังต้องระวัง |
|---|---|---|---|
| Edge patient record เก็บเฉพาะ `patient_token` | Implemented | `models.py`, `test_security.py` | ต้องตรวจ host, backup และ downstream exports เพิ่ม |
| Telemetry contract ล็อกเป็น `TelemetryPacket` v1 | Implemented | `schemas.py`, `test_security.py` | ต้องมี schema registry และ migration policy สำหรับ v2 |
| Bearer authentication และ scope authorization | Implemented baseline | `security.py`, `test_security.py` | Static token ใช้ได้เฉพาะ local/test; OIDC จริงยัง pending |
| OIDC/JWT fail-closed | Implemented/Ready-to-configure | `oidc.py`, `security.py`, `test_p0_hardening.py` | ยังไม่ผ่านการทดสอบกับ IdP, JWKS, revocation และ clock policy จริง |
| mTLS launcher | Ready-to-configure | `run_mtls.sh`, `.env.example` | ยังไม่ทดสอบ certificate, CA trust, rotation และ network จริง |
| SQLite WAL, busy timeout และ migration-first startup | Implemented baseline | `database.py`, Alembic files, `test_p0_hardening.py` | ยังต้องทำ power-loss และ hardware disk testing |
| Active-only pairing uniqueness | Implemented | `models.py`, initial Alembic migration | ยังต้องทดสอบ concurrency บน deployment topology จริง |
| Per-device monotonic sequence replay protection | Implemented | `edge_runtime.py`, `test_edge_runtime.py`, `test_residual_controls.py` | Device identity, counter reset และ clock policy ต้องกำหนดกับ hardware จริง |
| Process-local sliding-window rate limiting | Implemented, process-local | `edge_controls.py`, middleware ใน `main.py`, `test_residual_controls.py` | Multi-process/multi-node ต้องใช้ gateway หรือ coordinated limiter; capacity ต้อง calibrate ใน pilot |
| Handover sync idempotency และ single-purge gate | Implemented for single-process Edge owner model | `HandoverRecord.synced`, `SyncAttempt`, `HANDOVER_SYNC_LOCK`, `test_residual_controls.py` | ห้ามลบ idempotency evidence โดยไม่ผ่าน retention/restore policy |
| Structured JSONL audit events และ request ID | Implemented baseline | `edge_controls.py`, middleware และ endpoint hooks ใน `main.py` | ต้องส่งต่อไปยัง centralized/WORM audit pipeline และกำหนด access/retention |
| Zero-PII audit redaction | Implemented baseline | `_redact()`, actor subject hashing, `test_residual_controls.py` | ต้องทำ host-level log review และ downstream scan |
| Local forensic anchor adapter | Experimental/local adapter | `FileAnchorStore`, `test_residual_controls.py` | ยังไม่ใช่ external immutable/WORM anchor และไม่มี independent key custody |
| SHA-256 forensic hash chain | Experimental | `main.py`, `test_forensics.py`, `test_residual_controls.py` | ใช้คำว่า tamper-evident เท่านั้น ไม่ใช่ tamper-proof |
| FHIR/handover acknowledgment ก่อน purge | Implemented contract baseline | `main.py`, `test_fhir.py`, residual idempotency test | ยังต้องทดสอบกับ HIS จริงและ failure modes ของ network |

## Runtime configuration

ตัวแปรสำคัญสำหรับ residual controls มีดังนี้:

| Variable | ค่าเริ่มต้น | ความหมาย |
|---|---:|---|
| `SW_RATE_LIMIT_PER_MINUTE` | `6000` | จำนวน request ต่อ client key ต่อ sliding window 60 วินาที; เป็น process-local |
| `SW_AUDIT_LOG_PATH` | `./audit_events.jsonl` | JSONL audit sink ที่เปิด append และ `fsync` ต่อ event |
| `SW_IDEMPOTENCY_TTL_SECONDS` | `86400` | ค่ากำกับ retention policy ใน configuration; destructive purge gate ใช้สถานะ `HandoverRecord.synced` แบบไม่หมดอายุเพื่อความปลอดภัย |
| `SW_FORENSIC_ANCHOR_PATH` | ไม่ตั้งค่า | หากตั้งค่า จะเขียน local append-only anchor JSONL หลัง freeze; ยังไม่ใช่ external WORM |

ใน pilot ควรแยก directory สำหรับ database, checkpoint, audit และ anchor ออกจาก source code และจำกัดสิทธิ์ filesystem ให้เฉพาะ service account. Secrets, private keys และ OIDC configuration ต้องมาจาก secret manager หรือ protected environment เท่านั้น.

## หลักฐานการทดสอบ

`python3 run_all_tests.py` ผ่านครบทั้ง functional levels 1–6, P0 hardening, residual controls, Device Trust, ward workflows, Outside-in bed availability/admission preparation และ Roaming Tablet synchronization. ชุด residual controls ตรวจ rate-limit response `429`, per-device replay rejection `409`, handover sync ซ้ำโดยไม่ purge ซ้ำ, JSONL audit redaction, request ID และ local forensic anchor output.

ผล reliability harness เป็น **software simulation/verification** ไม่ใช่ hardware หรือ clinical test: 30 devices, 600 concurrent requests, ทุก request ได้สถานะ 200, p50 227.988 ms, p95 690.216 ms, p99 926.509 ms และ max 1215.514 ms. ผล pilot simulation ครอบคลุม 30 simulated days, 30 devices, 900 daily packets และ concurrent ingestion 30 requests ใน 175.730 ms. หลักฐานทั้งสองชุดระบุชัดว่า hardware, battery, clinical และ external network validation ยังไม่ได้ทำ.

## Residual risks ที่ยังไม่ปิด

| Risk area | สถานะปัจจุบัน | ขั้นตอนปิดความเสี่ยงที่ต้องทำภายนอกซอฟต์แวร์ |
|---|---|---|
| IdP/OIDC จริง | Unverified | ทดสอบ issuer, audience, JWKS rotation, expiration, revocation, clock skew และ incident response กับ IdP ของโรงพยาบาล |
| mTLS และ certificate lifecycle | Unverified | ใช้ certificate/CA จริง, ทดสอบ rotation/revocation, trust store, firewall และ network segmentation |
| Hardware, power และ network | Unverified | ทดสอบ wristband จริง, battery, packet loss, reconnect, disk failure, power-loss recovery และ latency |
| Clinical performance | Unverified | ทำ clinical protocol, sensitivity/specificity, false-positive review, alarm fatigue review และ clinical sign-off |
| External forensic anchoring | Experimental | เชื่อม independently administered append-only/WORM service และกำหนด key custody, timestamp, retention และ verification drill |
| Key custody และ secret rotation | Planned | ใช้ HSM/secret manager, rotation, revocation, dual control และ evidence access policy |
| Host hardening | Unverified | OS baseline, least privilege, patching, firewall, disk encryption, monitoring, backup และ restore drill |
| HIS/EMR integration | Unverified | ทดสอบ FHIR contract กับ endpoint จริง, retry, timeout, authentication, reconciliation และ safe purge |

การลด PII ใน Edge schema ไม่ได้หมายความว่าระบบมี compliance 100% โดยอัตโนมัติ และผล functional verification ไม่ควรถูกเรียกว่า “clinical-ready”, “tamper-proof”, “HIPAA/PDPA compliant 100%” หรือ “production-ready”.

## References

[1]: ./test_residual_controls.py "Residual-control regression tests"
[2]: ./reliability_validation_result.json "Software reliability validation result"
[3]: ./pilot_simulation_result.json "30-day software pilot simulation result"
[4]: ./P0_HARDENING_REPORT.md "P0 hardening report"
[5]: ./RISK_REGISTER.md "Smart Ward Hub risk register"


## Strategic differentiator: Device Trust & Secure Provisioning

Device Trust & Secure Provisioning is recorded as a **strategic product differentiator and roadmap capability**. It extends the current trust boundaries from device registration and sequence protection toward manufacturer-authenticated identity, signed canonical telemetry, key lifecycle management and externally anchored evidence.

The current software baseline does **not** claim manufacturer CA verification, secure-element/HSM key custody, or external WORM anchoring. It now implements Ed25519 public-key enrollment, canonical signed telemetry verification in `enforce` mode, and basic credential lifecycle states, all with focused regression evidence. Manufacturer CA provisioning, hardware-backed key custody and external anchoring remain planned or externally validated. The project must not import hardcoded factory master secrets or device seed keys into source code, and must not use shared HMAC as a substitute for a manufacturer digital-signature trust chain.

The approved product claim is:

> Manufacturer-authenticated device identity with signed telemetry and tamper-evident forensic evidence; hardware and clinical validation pending.

Geofence or device-trust anomalies must use a fail-safe patient-safety policy: alert, audit, and controlled degraded-trust/quarantine handling are acceptable design directions; automatic device bricking or automatic monitoring shutdown is not an approved default.


### Device Trust software baseline matrix

| Control | Status | Evidence | Boundary |
|---|---|---|---|
| Device Trust mode flag: disabled/observe/enforce | Implemented | `config.py`, `.env.example`, observe/enforce tests | Default is disabled for compatibility; pilot should stage through observe |
| Ed25519 public-key enrollment | Implemented software baseline | `device_trust.py`, `main.py`, `test_device_trust.py` | Enrollment is operator-authorized; manufacturer CA provenance is not yet verified |
| Canonical signed `TelemetryPacket v1` | Implemented software baseline | `device_trust.py`, mutation regression | Real firmware cross-language interoperability is pending |
| Signed-field mutation rejection | Implemented | `test_device_trust.py` | Does not prove hardware private-key protection |
| Credential lifecycle: active/suspended/revoked/expired | Implemented baseline | `models.py`, Alembic migration, lifecycle regression | HSM/secure-element custody and independent revocation service are pending |
| Observe-mode continuity | Implemented | `test_device_trust_observe.py` | Unverified telemetry is allowed by design in shadow mode and must not be treated as trusted evidence |
| Enforce-mode fail-closed ingestion | Implemented | `test_device_trust.py` | Requires clock, provisioning and operational calibration before pilot |


## Ward workflow safety baseline

The workflow layer now enforces an Admission Gateway boundary, state-aware reset, session-linked evidence and NFC pointer semantics. Hub Core rejects common raw HN/AN formats at the pairing contract; production still requires the hospital's Admission Gateway to perform authoritative tokenization and authorization before forwarding an opaque token.

| Workflow control | Status | Evidence | Remaining boundary |
|---|---|---|---|
| Raw HN/AN rejected at Hub pairing boundary | Implemented baseline | `schemas.py`, `test_session_workflows.py` | Real Admission Gateway/HIS authorization pending |
| NFC pointer separated from cryptographic trust | Implemented baseline | `NfcPointer`, `/api/v1/nfc/*`, workflow test | NFC hardware and pointer revocation operations pending |
| `RESET_PENDING` before output reset | Implemented baseline | session reset endpoints and workflow test | UI visual confirmation and ward usability validation pending |
| Hot-swap creates new session and handover link | Implemented baseline | `WardSession`, hot-swap endpoint and test | Real wristband/BLE gateway behavior pending |
| Routine Session Close summary digest | Implemented baseline | `SessionCloseDigest`, chained digest test | Retention and external anchoring policy pending |
| Incident freeze before unsafe reset/discharge | Implemented baseline | session-linked `ForensicPackage`, incident workflow test | Clinical incident review and external evidence validation pending |
| Volatile buffer clear wording and behavior | Implemented application control | `EdgeTelemetryStore.pop()` | Not physical memory zeroization; host/storage retention remains separate |


## Outside-in bed availability and admission preparation baseline

The software baseline now provides a non-PII bed availability snapshot, explicit bed states (`AVAILABLE`, `RESERVED`, `OCCUPIED`, `CLEANING`, `BLOCKED`, `MAINTENANCE`), reservation expiry, idempotent admission preparation, cancellation and pairing commit/release. The loopback-only `/admission` console is intended for the controlled outside-facing Acer console; it must not be exposed directly to a public corridor or visitor network.

Admission preparation accepts opaque `patient_token`/`encounter_token` only. Raw HN/AN remains an external Admission Gateway responsibility and is rejected by the Hub schema. Audit evidence records request/actor/console/bed outcome without retaining the raw patient token. This is a software control baseline; real HIS/Admission Gateway, physical privacy placement, operator authentication, network segmentation and clinical workflow validation remain open gates.


## Roaming Tablet synchronization security baseline

The roaming software baseline provides an authenticated non-PII snapshot with a deterministic revision/cursor and a durable command record with `command_id`, `idempotency_key`, `tablet_id`, `expected_revision`, actor identity, outcome and audit evidence. Stale tablet state returns a conflict instead of overwriting Fixed Hub state. Alert acknowledgement, admission-task acknowledgement and safe `RESET_REQUEST` are supported; `RESET_CONFIRM`, discharge, hot-swap, pairing changes, credential changes, incident freeze and purge remain live Fixed Hub actions in the initial pilot.

The baseline does not yet prove managed Android device identity, hardware-backed tablet credentials, real OIDC/IdP integration, encrypted Android cache, real ward Wi-Fi roaming, push notification delivery or multi-process distributed command coordination. Roaming state must therefore remain a **pilot-ready software foundation**, not a claim of validated mobile clinical deployment.
