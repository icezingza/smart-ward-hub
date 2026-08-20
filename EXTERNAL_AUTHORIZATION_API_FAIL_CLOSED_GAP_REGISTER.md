# External Authorization API Simulator — Fail-Closed Gap Register

**ตรวจเมื่อ:** 2026-08-20
**ขอบเขต:** `external_authorization_api_simulator.py`, `controlled_pilot_handoff.py`, Wave 0 governance contracts และ regression ที่มีอยู่

> รายงานนี้เป็น software security review ของตัวจำลองเท่านั้น ไม่ใช่การตรวจ External Authorization API จริง และไม่ใช่ production approval

## Executive finding

ตัวจำลองปัจจุบันผ่าน lifecycle พื้นฐาน ได้แก่ submit, poll, simulated review, finding, idempotency, raw-identity rejection, manifest binding และ audit hash-chain ในกรณีปกติ อย่างไรก็ตามยังมีช่องว่างสำคัญก่อนจะถือว่าเป็น **production-grade integration contract** โดยเฉพาะการทำให้ state transition เป็น atomic, การรองรับ expiry/revocation/stale decision, การจัดการ network uncertainty และการป้องกัน mutation ของ in-memory state จาก caller หรือ concurrent execution

สถานะรวมจึงเป็น **Experimental / Software baseline** และยังไม่ใช่ `Production-ready` หรือ `External Authorization verified`

## Gap matrix

| ID | Finding | Severity | Current status | Impact | Required remediation |
|---|---|---:|---|---|---|
| EA-001 | `issue_finding()` เปลี่ยน finding/status ก่อนตรวจ `occurred_at` ผ่าน `_record_event()` | Critical | Not Found | naive timestamp หรือ audit failure อาจทำให้ state ถูกแก้แล้วแต่ไม่มี audit event เป็น partial commit | validate ทุก input และเตรียม event ก่อน commit; ใช้ transaction/rollback simulation และทดสอบ failure injection |
| EA-002 | `start_review()` เปลี่ยน status ก่อนยืนยันว่า timestamp/audit event ใช้งานได้ | High | Not Found | เกิด `IN_SIMULATED_REVIEW` โดยไม่มี audit trail ที่สมบูรณ์ | ทำ state transition แบบ validate → event → commit หรือ rollback เมื่อ event ไม่สำเร็จ |
| EA-003 | ไม่มี decision expiry, revocation, supersession หรือ stale decision model | Critical | Not Found | decision เก่าหรือถูกเพิกถอนอาจถูกใช้เป็น approval ต่อ | เพิ่ม decision record, effective/expiry, revoked_at, supersedes, current-version lookup และ fail-closed status |
| EA-004 | `poll()` ไม่รับ observed version/ETag และ response ไม่มี audit event ID ของ poll | Medium | Experimental | client อาจใช้ stale response หรือพิสูจน์ไม่ได้ว่าเห็น status ใดเมื่อใด | เพิ่ม monotonic revision, observed_at, source_event_id, stale response rejection และ read-only audit response |
| EA-005 | ไม่มี timeout, retry budget, uncertain commit และ reconciliation protocol | High | Not Found | network timeout หลัง server commit อาจทำให้ retry ซ้ำหรือสรุปผิดว่า submission ไม่สำเร็จ | เพิ่ม request correlation, retry class, idempotency replay response, reconciliation endpoint/state และ bounded retry policy |
| EA-006 | ไม่มี partial upload/chunk integrity หรือ payload-size limit | High | Not Found | malformed/oversized package อาจทำให้ memory exhaustion หรือ artifact set ไม่ครบ | เพิ่ม content length, maximum fields/refs, per-artifact hash, bounded payload, upload-finalize state และ reject incomplete package |
| EA-007 | input type validation ยังไม่ครบ เช่น `artifact_refs` ไม่ใช่ list, hash/version รูปแบบผิด, enum/role ไม่ถูกต้อง | High | Partial | runtime exception หรือ malformed state อาจหลุดจาก API error contract | เพิ่ม schema validator แบบ strict และทดสอบทุก field ด้วย wrong type, null, empty, oversized และ Unicode edge cases |
| EA-008 | unknown submission ID ใช้ `KeyError` แทน typed fail-closed API error | Medium | Not Found | caller ได้ internal exception และอาจเปิดเผย implementation detail | เพิ่ม `REJECTED_UNKNOWN_SUBMISSION` พร้อม redacted response และ audit ของ failed lookup ตาม policy |
| EA-009 | in-memory `submissions`, `audit_events` และ `findings` เปิดให้ caller แก้ได้โดยตรง | Critical | Not Found | caller สามารถ bypass lifecycle หรือแก้ audit/state โดยไม่ผ่าน validator | ห่อ state ด้วย private storage, immutable snapshots/copies, controlled command methods และ mutation tests |
| EA-010 | audit chain ตรวจพบ tamper เมื่อเรียก `audit()` แต่ไม่ป้องกันการเขียน event ย้อนหลัง | High | Experimental | integrity failure เกิดขึ้นหลัง state ถูกใช้ไปแล้ว และไม่มี fail-stop/incident state | ทำ append-only store abstraction, verify-before-read, lock chain หลัง append และเปลี่ยน state เป็น `AUDIT_INTEGRITY_FAILURE` เมื่อผิด |
| EA-011 | ไม่มี concurrency/serialization control | High | Not Found | submit/review/finding ซ้อนกันอาจสร้าง duplicate หรือ state order ที่ไม่ deterministic | เพิ่ม lock/transaction boundary, monotonic event sequence และ concurrent race regression |
| EA-012 | ใช้เวลาจาก caller โดยไม่มี server clock, skew policy หรือ window expiry check | High | Partial | client อาจส่ง timestamp ย้อน/อนาคตและทำให้ audit ordering/expiry ผิด | เพิ่ม injected clock, allowed skew, server observed time, monotonic ordering และ expiry enforcement |
| EA-013 | package binding ตรวจ manifest/scope/window แต่ไม่ตรวจ governance state, freeze external verification หรือ artifact set completeness | High | Partial | package local ที่ยังไม่พร้อมอาจถูก submit เป็น review-ready โดยขาด required evidence | ผูก submit กับ Wave 0 validation, required evidence classes, external verification status และ blocker matrix |
| EA-014 | finding validation ไม่บังคับ severity/category enum, evidence refs ที่ trace ได้จริง หรือ reviewer role ที่เหมาะสม | Medium | Partial | finding อาจมีข้อมูลคลุมเครือและปิด gap ไม่ได้ | strict enum, evidence existence/manifest membership, role authorization และ required-action schema |
| EA-015 | ไม่มี response authenticity model สำหรับ external decision | Critical | Not Found | local response อาจถูกนำไปอ้างเป็น decision จริงหรือถูกแก้ระหว่างทาง | สำหรับระบบจริงต้องมี signed response/MAC, key ID, trust chain, verification result และ independent read-back; simulator ต้องคง `NONE` |
| EA-016 | ไม่มี revocation propagation, cache invalidation และ restart recovery | Critical | Not Found | client/offline cache อาจใช้ authorization ที่ถูกเพิกถอนแล้ว | เพิ่ม revocation event, cache version, restart replay, fail-closed on unknown status และ recovery test |
| EA-017 | ไม่มี audit redaction/size policy สำหรับ payload ที่เก็บใน event | High | Partial | payload ใหญ่หรือข้อมูลต้องห้ามอาจถูกเก็บใน audit | บันทึกเฉพาะ allowlisted metadata, hash refs แทน content, max event size และ redaction regression |
| EA-018 | ไม่มี contract version negotiation และ backward-incompatible change guard | Medium | Not Found | client/server schema mismatch อาจทำให้ interpretation ของ status ผิด | เพิ่ม API/contract version, supported-version check, migration and rollback evidence |
| EA-019 | ไม่มี explicit incident state เมื่อ audit, manifest, clock หรือ integrity check ล้มเหลว | High | Not Found | ระบบยังอาจรับคำสั่งต่อหลัง evidence boundary เสีย | เพิ่ม fail-stop state, incident ID, stop authority notification, recovery approval และ post-incident evidence |
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
| Atomic state transitions | Not Found | พบ mutation-before-audit failure path |
| Expiry/revocation/stale decision | Not Found | ยังไม่มี decision lifecycle |
| Retry/timeout/partial commit | Not Found | ยังไม่จำลอง delivery uncertainty |
| OIDC/mTLS/TLS/ACL/real endpoint | Unverified | ไม่มี external infrastructure evidence |
| Clinical/production authorization | Not Applicable to simulator | local code ห้ามสร้าง authority และต้องคง false/NONE |

## Immediate next step

เริ่ม Wave A ด้วยการเพิ่ม transaction-like state transition และ integrity fail-stop ก่อน จากนั้นจึงเพิ่ม decision lifecycle สำหรับ expiry/revocation/stale polling. ทุกการเปลี่ยนแปลงต้องมี negative-path regression และต้องคง `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`, `clinical_validation_authorized=false`, `production_authorized=false` และ `runtime_authority=NONE`
