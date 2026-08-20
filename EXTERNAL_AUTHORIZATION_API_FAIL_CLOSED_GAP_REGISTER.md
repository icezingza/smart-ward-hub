# External Authorization API Simulator — Fail-Closed Gap Register

**ตรวจเมื่อ:** 2026-08-20
**ขอบเขต:** `external_authorization_api_simulator.py`, `controlled_pilot_handoff.py`, Wave 0 governance contracts และ regression ที่มีอยู่

> รายงานนี้เป็น software security review ของตัวจำลองเท่านั้น ไม่ใช่การตรวจ External Authorization API จริง และไม่ใช่ production approval

## Executive finding

ตัวจำลอง v2 หลัง Wave A–D hardening มี atomic transition, private snapshots, append-only audit-store abstraction, explicit incident fail-stop, deterministic lock serialization, expiry/revocation/stale-cache checks, bounded retry/reconciliation advice, chunk-manifest integrity, strict finding evidence binding, governance package binding และ simulator-side response authenticity denial แล้ว อย่างไรก็ตามหลักฐานทั้งหมดเป็น **software verification หรือ simulation-only** และยังไม่ใช่ endpoint, transport, identity, custody หรือ reviewer evidence จริง

สถานะรวมจึงเป็น **P0-hardened software baseline / Experimental integration simulation** และยังไม่ใช่ `Production-ready` หรือ `External Authorization verified`

## Gap matrix

| ID | Finding | Severity | Current status | Impact | Required remediation |
|---|---|---:|---|---|---|
| EA-001 | `issue_finding()` เปลี่ยน finding/status ก่อนตรวจ `occurred_at` ผ่าน `_record_event()` | Critical | Software control verified | v2 validates input and builds event before commit | คง regression และตรวจ implementation เมื่อเปลี่ยน persistence boundary |
| EA-002 | `start_review()` เปลี่ยน status ก่อนยืนยันว่า timestamp/audit event ใช้งานได้ | High | Software control verified | candidate/event commit order is regression-tested | คง regression และตรวจ durable transaction boundary ภายนอก |
| EA-003 | ไม่มี decision expiry, revocation, supersession หรือ stale decision model | Critical | Software control verified | expiry/revocation lifecycle is present and remains externally unverified | external decision owner, durable revocation and independent read-back remain required |
| EA-004 | `poll()` ไม่รับ observed version/ETag และ response ไม่มี audit event ID ของ poll | Medium | Software control verified | revision, event hash, audit event ID and cache-version checks are present | real distributed ETag/cache behavior remains unverified |
| EA-005 | ไม่มี timeout, retry budget, uncertain commit และ reconciliation protocol | High | Software control partially verified | `COMMIT_UNKNOWN`, reconciliation and bounded retry advice are regression-tested | real timeout/proxy behavior and durable remote idempotency remain external |
| EA-006 | ไม่มี partial upload/chunk integrity หรือ payload-size limit | High | Software control partially verified | bounded chunk manifest, sequence, per-chunk hash, size and finalize checks are present | real upload service limits and transport interruption remain external |
| EA-007 | input type validation ยังไม่ครบ เช่น `artifact_refs` ไม่ใช่ list, hash/version รูปแบบผิด, enum/role ไม่ถูกต้อง | High | Software control verified | strict submit/finding/chunk schema and wrong-type regression are present | maintain schema contract across a real API implementation |
| EA-008 | unknown submission ID ใช้ `KeyError` แทน typed fail-closed API error | Medium | Software control verified | unknown submission returns typed fail-closed error | real API error envelope and logging policy remain external |
| EA-009 | in-memory `submissions`, `audit_events` และ `findings` เปิดให้ caller แก้ได้โดยตรง | Critical | Software control verified | private storage, defensive snapshots and mutation regression are present | durable storage access control remains external |
| EA-010 | audit chain ตรวจพบ tamper เมื่อเรียก `audit()` แต่ไม่ป้องกันการเขียน event ย้อนหลัง | High | Software control partially verified | append-only store abstraction and audit fail-stop incident are regression-tested | in-memory store is not independent WORM or durable custody |
| EA-011 | ไม่มี concurrency/serialization control | High | Software control verified | RLock, monotonic event sequence and concurrent submit race regression are present | multi-process/distributed serialization remains unverified |
| EA-012 | ใช้เวลาจาก caller โดยไม่มี server clock, skew policy หรือ window expiry check | High | Software control verified | timezone-aware timestamps, injected server clock, skew policy and observed time are tested | trusted external clock and network time policy remain external |
| EA-013 | package binding ตรวจ manifest/scope/window แต่ไม่ตรวจ governance state, freeze external verification หรือ artifact set completeness | High | Software control partially verified | constructor binds governance state, validation snapshot and freeze boundary; artifact refs remain local refs | required evidence completeness and external freeze verification remain external |
| EA-014 | finding validation ไม่บังคับ severity/category enum, evidence refs ที่ trace ได้จริง หรือ reviewer role ที่เหมาะสม | Medium | Software control partially verified | strict fields, severity, reviewer role and evidence membership are regression-tested | reviewer appointment and external evidence authority remain unverified |
| EA-015 | ไม่มี response authenticity model สำหรับ external decision | Critical | Simulation-only denial control | simulator rejects locally authorized response and returns `SIMULATION_ONLY`/untrusted result | signed response, key ID trust chain and independent read-back require a real external service |
| EA-016 | ไม่มี revocation propagation, cache invalidation และ restart recovery | Critical | Software control partially verified | cache version, expiry/revocation state and hashed restart snapshot recovery are tested | distributed cache invalidation and external revocation propagation remain unverified |
| EA-017 | ไม่มี audit redaction/size policy สำหรับ payload ที่เก็บใน event | High | Software control verified | allowlisted audit payloads, hash refs and bounded event size are enforced | durable log retention/access controls remain external |
| EA-018 | ไม่มี contract version negotiation และ backward-incompatible change guard | Medium | Software control verified | exact contract-version negotiation and unsupported-version rejection are tested | real API migration/rollback evidence remains external |
| EA-019 | ไม่มี explicit incident state เมื่อ audit, manifest, clock หรือ integrity check ล้มเหลว | High | Software control verified | explicit incident ID, recovery-required state and command blocking are regression-tested | stop-authority notification and recovery approval remain external |
| EA-020 | simulator ไม่มี network boundary test เพราะเป็น in-memory และไม่จำลอง TLS/mTLS/OIDC/ACL | Critical | Unverified | functional simulation ไม่บอกความปลอดภัยของ endpoint จริง | จัดทำ external test plan และทดสอบใน non-production environment ด้วย owner/approval จริงก่อนใช้ production claim |

## Priority order

ตารางต่อไปนี้ใช้สำหรับจัดลำดับ implementation โดยไม่เปิด clinical หรือ production boundary:

| Wave | Items | Acceptance gate |
|---|---|---|
| A — State integrity | EA-001, EA-002, EA-009, EA-010, EA-011, EA-019 | atomic transitions, private state, audit fail-stop และ deterministic race tests |
| B — Decision validity | EA-003, EA-004, EA-012, EA-016 | expiry/revocation/version/clock/unknown-state fail-closed tests |
| C — Delivery reliability | EA-005, EA-006, EA-007, EA-008, EA-017 | bounded payload, typed errors, retry/reconciliation และ audit redaction |
| D — Governance binding | EA-013, EA-014, EA-015, EA-018 | external evidence binding, signed-response contract และ version guard |
| E — Real external validation | EA-020 | real endpoint, IdP/mTLS, ACL, custody, reviewer and independent read-back evidence |

## Claim classification

| Control area | Classification now | Reason |
|---|---|---|
| Offline submit/poll/finding happy path | Implemented | มี source และ regression evidence |
| Idempotency and basic rejection cases | Implemented | มี positive/negative tests |
| Audit hash-chain calculation | Experimental | ตรวจ integrity ได้ แต่ storage ยัง mutable และ in-memory |
| Atomic state transitions | Software verified | validate → event → commit and race regression |
| Expiry/revocation/stale decision | Software verified/partial | lifecycle and cache controls are local only |
| Retry/timeout/partial commit | Software verified/partial | bounded advice, COMMIT_UNKNOWN and chunk checks are local only |
| OIDC/mTLS/TLS/ACL/real endpoint | Unverified | ไม่มี external infrastructure evidence |
| Clinical/production authorization | Not Applicable to simulator | local code ห้ามสร้าง authority และต้องคง false/NONE |

## Current software disposition

Wave A–D software controls มี regression evidence แล้วใน `test_external_authorization_api_simulator.py` และ `EXTERNAL_AUTHORIZATION_API_WAVE_A_D_HARDENING_PLAN.md` แต่ `EA-020` ยัง `EXTERNAL_UNVERIFIED` และ simulator ยังเป็น in-memory เท่านั้น ทุกการเปลี่ยนแปลงต้องคง `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`, `clinical_validation_authorized=false`, `production_authorized=false` และ `runtime_authority=NONE`

## Immediate next step

เตรียม Wave E non-production external validation package สำหรับ endpoint จริง, OIDC/mTLS, ACL, signed response, expiry/revocation, custody, outage/retry และ independent read-back โดยต้องมี external owner, approved test window, stop authority และ no-authorization decision แยกจาก local regression
