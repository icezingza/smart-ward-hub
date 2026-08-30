# Smart Ward Hub — สถานะระบบและแผนสู่ Pilot

## Slide 1 — Smart Ward Hub

**Sovereign Ward Operating Layer**

ระบบ Edge-first สำหรับ patient monitoring ที่ออกแบบให้ Fixed Hub ประจำวอร์ดเป็น source of truth ภายในพื้นที่ แม้การเชื่อมต่อภายนอกไม่เสถียร

**สถานะล่าสุด:** `controlled production prototype` · `P0-hardened software baseline` · `functional verification passed` · `pilot-ready foundation` · `pilot deployment configuration pending` · `clinical validation pending`

Visual: `presentation_assets/smart_ward_reference.webp`

Source: `README.md`, `SMART_WARD_HANDOFF_STATUS.md`

## Slide 2 — Product thesis: สร้างระบบ ไม่ใช่เพียง dashboard

Smart Ward Hub รวม Edge persistence, telemetry ingestion, patient-safety intelligence, Cryptographically Verifiable Tamper-Evident Audit Trail, HIS/EMR interoperability, Device Trust และ ward workflow ไว้ใน control plane เดียว

**จุดขายหลัก**

- Sovereign Edge / Offline-first
- Zero-PII Edge boundary
- Patient Safety Intelligence
- Cryptographically Verifiable Tamper-Evident Audit Trail
- Hospital-Controlled Data Boundary
- Traceability & Forensic Readiness
- HIS/EMR Interoperability
- Device Trust & Secure Provisioning
- Outside-in Ward Workflow
- Sovereign Ward Operating Layer

## Slide 3 — Architecture: Fixed Hub เป็น authority

**Fixed Hub — Acer Spin N17H2 candidate**

SQLite WAL เป็น source of truth, RAM ring buffer เป็น speed layer, FastAPI เป็น local control plane และ checkpoint เป็น recovery layer

**Operational clients**

- Outside Admission Console: ตรวจเตียงว่างและเตรียม admission จากนอกวอร์ด
- Roaming Tablet: อ่าน snapshot/ส่ง command เมื่อ Hub reachable; ไม่ใช่ source of truth
- BMAX i11_s: candidate สำหรับ roaming UI; implementation deferred

**Trust boundaries**

IoT adapters → Hub validation → local forensic chain → optional external anchor → HIS/EMR integration → clinical governance

Visual: `presentation_assets/tablet_care_reference.webp`

Source: `architecture.md`, `ZERO_TRUST_TRUST_BOUNDARIES.md`, `TABLET_HARDWARE_DECISION.md`

## Slide 4 — Core workflow: จาก telemetry สู่ evidence

```text
Pairing / Admission Token
        ↓
TelemetryPacket v1 + sequence guard
        ↓
AI triage baseline + silent-fall signal + alert lifecycle
        ↓
Incident freeze / SHA-256 forensic chain
        ↓
FHIR handover + structured acknowledgment
        ↓
Exact-scope purge only after matching acknowledgment
```

**Safety boundary:** ระบบสร้าง signal และ evidence ไม่ใช่ diagnosis หรือ treatment order

Source: `main.py`, `schemas.py`, `test_fhir.py`, `test_forensics.py`, `CLINICAL_SAFETY_SHADOW_MODE.md`

## Slide 5 — Ward workflow และ hardware strategy

**Outside-in admission** ช่วยให้เจ้าหน้าที่ตรวจ bed availability และเตรียม admission จากด้านนอกวอร์ด โดย Hub รับเฉพาะ opaque `patient_token` / `encounter_token`

**Fixed Hub** เป็น authority สำหรับ pairing, session, alert, reset และ purge

**Roaming Tablet** ใช้ snapshot revision, freshness banner, command ID และ idempotency; destructive actions ต้องผ่าน live Hub

**Acer Spin N17H2** อยู่ในบทบาท Fixed Hub candidate: inventory แบบ read-only พบ Windows 11 Pro build 26200, Python 3.14.3 และยังไม่พบ COM port

**BMAX i11_s** อยู่ในบทบาท roaming UI candidate และยัง deferred

## Slide 6 — Functional verification: software evidence ที่มีแล้ว

Master regression ครอบคลุม Phase 1–6, P0 hardening, residual controls, Device Trust, ward workflow, outside-in admission, roaming, Micro-RAG, P2-002 adapters, Serial framing, pressure simulation และ deployment/recovery tests

**ตัวอย่าง evidence**

- SQLite WAL, migration-first startup และ safe sync/purge lifecycle
- High-concurrency telemetry และ bounded recovery
- 30 simulated days และ 30 devices / 600 concurrent software reliability harness
- Serial framing, CRC32, partial reads และ network pressure scenarios
- Backup/restore isolated-target dry run
- Deployment readiness fail-closed checks

**ผลสรุป:** master regression ล่าสุด exit code `0`; เป็น software verification และ deterministic simulation เท่านั้น

Source: `run_all_tests.py`, `P0_STATUS_REPORT.md`, `OPERATIONAL_TRUNK_HANDOFF.md`

## Slide 7 — Security, Device Trust และ evidence integrity

**Implemented software baseline**

- Zero-PII token boundary และ audit redaction
- Bearer scope authorization; OIDC/JWT-ready; mTLS launcher/file-hygiene baseline
- Ed25519 signed telemetry, observe/enforce modes และ credential lifecycle
- Key-custody contract: dual control, rotation, revocation, lost-device และ private-key exclusion
- FileAnchorStore hardening: input validation, source-tree separation, record hash, idempotency, receipt/readback
- External anchor adapter contract: receipt identity และ mutation fault matrix

**ยังไม่ verified**

Manufacturer CA, HSM/secure element, host ACL/encryption, independent WORM service, trusted timestamp, real IdP/PKI และ cross-boundary verification

Visual: `presentation_assets/healthcare_security_reference.jpeg`

## Slide 8 — AI-native project system และ Micro-RAG

ระบบถูกจัดระเบียบด้วย `prd.md`, `design.md`, `architecture.md`, `agents.md`, `memory.md`, `tasks.md`, `rules.md` และ `skills.md` พร้อม project-local skill overlays และ registry/policy/workflow files

**Micro-RAG evidence**

- Thai/English bilingual corpus และ adversarial injection fixtures
- Hallucination suite, model-agnostic response adapter และ approved document registry
- Gemini 3 Flash Preview current v2: `8/8` ผ่าน adapter/redaction checks
- Pinned Gemini 2.5 Flash rerun: `2/8`; six calls provider HTTP `429` จึงยังไม่ปิด pinned-target gate

**ข้อจำกัด:** runtime semantic retrieval, human review และ clinical governance ยัง pending

Source: `MICRO_RAG_*`, `evals/micro_rag/`, `SMART_WARD_8_SKILL_INTEGRATION.md`

## Slide 9 — Current status matrix

| Area | Status | Evidence boundary |
|---|---|---|
| P0 software baseline | Functional verification passed | HIS/IdP/PKI/Acer/clinical gates open |
| P1-001 backup/restore | Dry-run complete | Real encrypted destination and restore pending |
| P1-002 host hardening | In Progress | Acer account/ACL/firewall/patch evidence pending |
| P1-003 Device Trust custody | In Progress | Manufacturer CA/HSM/secure element pending |
| P1-004 external anchor | In Progress | Independent WORM and trusted timestamp pending |
| P1-005 clinical shadow-mode | In Progress | Governance approval and real shadow review pending |
| P2-002 Edge IoT | In Progress | Physical Acer serial/broker/BLE/RF evidence pending |
| P2-004 Micro-RAG | In Progress | Pinned Gemini 2.5 rerun and runtime review pending |
| P2-001 roaming UI | Deferred | BMAX implementation after priority gates |

## Slide 10 — Roadmap, claims and next decisions

**Next external gates**

1. Hospital HIS/Admission Gateway contract and real structured acknowledgment
2. Real OIDC/JWKS and mTLS/PKI validation
3. Acer deployment, host hardening, physical serial bench and power/storage drills
4. Independent forensic anchor with trusted receipt and retention
5. Clinical shadow-mode governance, human-factors review and alarm-fatigue review
6. Pinned Gemini 2.5 Micro-RAG rerun after provider quota window

> Product claim boundary: **functional verification passed** is not **clinical-ready**, **tamper-proof**, **HIPAA/PDPA compliant 100%** or **production-ready**.

> CISO wording: **Hospital-Controlled Data Boundary**, not air-gapped; **Traceability & Forensic Readiness**, not a guarantee against litigation or a guaranteed legal outcome.

**Decision point:** move from software foundation to controlled external validation only when each owner, evidence artifact, rollback path and stop condition is explicitly assigned

Source: `P0_STATUS_REPORT.md`, `RISK_REGISTER.md`, `tasks.md`, `P1_004_HANDOFF.md`, `P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md`

## Appendix — Evidence map

Key evidence files: `README.md`, `P0_STATUS_REPORT.md`, `P1_004_HANDOFF.md`, `P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md`, `FILE_ANCHOR_STORE_PRODUCTION_GAP_REVIEW.md`, `OPERATIONAL_TRUNK_HANDOFF.md`, `P2_EDGE_IOT_ADAPTER_READINESS_REPORT.md`, `MICRO_RAG_READINESS_REPORT.md`, `SERIAL_BENCH_VALIDATION_PLAN.md`, `ACER_BENCH_READONLY_INVENTORY.md` and `tasks.md`.

All claims in this deck are bounded by the evidence register. Physical, external security, HIS, independent anchoring and clinical results remain unverified or pending unless explicitly identified otherwise.
