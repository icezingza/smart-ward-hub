# Internal Foundation Hardening Report

**วันที่:** 22 สิงหาคม 2026 (GMT+7)  
**ขอบเขต:** งานภายใน repository และ software simulation เท่านั้น  
**สถานะ:** `SOFTWARE_FOUNDATION_HARDENED_EXTERNAL_VALIDATION_PENDING`  
**Product status:** `NOT_PRODUCTION_READY`  
**Pilot status:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## 1. Executive decision

Smart Ward Hub ยังสามารถพัฒนาฐานภายในให้มั่นคงและปลอดภัยขึ้นได้อีก โดยไม่ต้องรอ external authorization และไม่จำเป็นต้องเปิด production network งานที่ทำได้จากภายในควรมุ่งที่ **fail-closed startup**, **bounded resource usage**, **SQLite/WAL integrity**, **backup/restore verification**, **zero-PII and secret hygiene**, **auditability**, **operational observability** และ **repeatable regression gates**

รอบนี้เพิ่ม `internal_foundation_readiness.py` เป็น read-only evaluator สำหรับตรวจ pilot configuration, loopback binding, explicit allowed hosts, runtime-path separation, OIDC configuration shape, bounded numeric settings, known runtime-artifact residue, private-key markers และ locked authorization boundary ผลลัพธ์เป็น software evidence ไม่ใช่การรับรอง Acer host, Windows service, disk encryption, real IdP/mTLS หรือ clinical workflow

## 2. สิ่งที่ทำได้จากภายในและลำดับความสำคัญ

| Priority | Internal workstream | ผลลัพธ์ที่ควรได้ | สถานะ |
|---:|---|---|---|
| P0 | Startup/readiness fail-closed | ระบบไม่ประกาศ restored/ready หาก config, path, auth, state หรือ artifact hygiene ไม่ผ่าน | Implemented/ขยายด้วย evaluator |
| P0 | Bounded memory and input limits | จำกัด telemetry buffer, device count, payload size และส่ง memory-pressure signal เมื่อเข้า threshold | Implemented ใน `edge_runtime.py`, `config.py`, `main.py` และ internal preflight; queue/cross-component bounds ยังเป็นงานถัดไป |
| P0 | SQLite/WAL integrity | `WAL`, busy timeout, foreign keys, integrity check, migration/schema check, checkpoint consistency และ recovery gate | Software baseline implemented; drill บน Acer ยัง pending |
| P0 | Backup/restore | SQLite backup API, manifest, SHA-256, isolated restore, post-restore checks และ documented RPO/RTO | Software baseline implemented; destination/retention/real restore pending |
| P1 | Zero-PII/secret hygiene | raw HN/AN/MRN/contact/secret/private key ไม่เข้า edge evidence, logs หรือ snapshots | Implemented ในหลาย contract; ต้องรักษาเป็น regression invariant |
| P1 | Authentication and authorization | OIDC shape validation, static-token restriction, scope enforcement, invalid-auth tests และ no self-authorization | Software controls implemented; real IdP/rotation/revocation pending |
| P1 | Audit and evidence | append-only local audit, request/correlation ID, redaction, hash binding, evidence manifest และ reproducible test transcript | Local baseline implemented; external custody/WORM pending |
| P1 | Observability | health/readiness, disk/WAL, backup freshness, auth failures, sequence gaps, queue/alert state และ reconciliation status | Contract/runbook prepared; real scrape/alert ownership evidence pending |
| P1 | Rollback and recovery rehearsal | version/hash rollback, stop ingestion, restore isolated state, reconcile pairing/alerts/sync/forensic state, post-rollback health check | Software procedures/tests exist; target-host drill pending |
| P2 | Dependency and release hygiene | pinned dependency review, vulnerability review, migration freeze, reproducible build, clean runtime tree และ release manifest | ทำได้ภายในและควรทำทุก release; external acceptance ยัง pending |
| P2 | Failure-injection matrix | disk-full, corrupt checkpoint, stale response, replay, duplicate, timeout, auth outage, audit failure และ partial recovery | หลายกรณีมีแล้ว; ควรเพิ่ม cross-component recovery matrix |

## 3. สิ่งที่รอบนี้ตรวจแล้ว

| Check | Evidence | Result |
|---|---|---|
| Pilot environment, docs disabled, no seed/auto-create, loopback, host allowlist | `deployment_readiness.py`, `test_deployment_readiness.py` | PASS |
| Telemetry per-device bounded ring buffer, sequence rejection and checkpoint restart | `edge_runtime.py`, `test_edge_runtime.py` | PASS |
| SQLite backup API, manifest/checksum/integrity and isolated restore | `backup_restore.py`, `test_backup_restore.py` | PASS |
| Numeric configuration bounds and fail-closed unsafe values | `internal_foundation_readiness.py`, `test_internal_foundation_readiness.py` | PASS |
| Canonical device identifier ingress pattern | `schemas.py`, `test_internal_foundation_readiness.py` | PASS |
| Global device/sample bounds and memory-pressure signal | `edge_runtime.py`, `config.py`, `main.py`, `test_edge_runtime.py` | PASS |
| Runtime artifacts and private-key marker scan | `test_internal_foundation_phase_end_hardening.py` | PASS |
| No network/provider/scheduler side effect in foundation evaluator | Phase-end AST scan | PASS |
| Locked authorization boundary | evaluator and phase-end runtime assertion | PASS |

## 4. Immediate internal backlog

### 4.1 ตรวจต่อ: cross-component bounded resources

ระดับ telemetry store ตอนนี้มีเพดาน `max_devices`, `max_sample_bytes`, per-device ring buffer และ `memory_pressure` signal แล้ว โดย preflight ตรวจค่า environment bounds และ ingress schema ใช้ canonical device identifier pattern การทำต่อควรขยายแนวคิดเดียวกันไปยัง maximum checkpoint bytes, bounded audit-line size, queue depth และ aggregate payloads โดยการ reject ต้องเป็น deterministic และไม่ทำให้ state sequence ขยับ

### 4.2 ทำต่อ: startup preflight aggregator

ผูก internal foundation evaluator เข้ากับ startup/preflight command ที่คืนผลแยกเป็น `PASS`, `ADVISORY` และ `FAIL` พร้อม exact remediation และไม่ประกาศ production readiness เอง การอ่านสถานะควรเป็น read-only และต้องไม่สร้าง database, seed data, network connection หรือ external authorization side effect

### 4.3 ทำต่อ: recovery matrix

สร้าง cross-component failure-injection suite สำหรับ checkpoint/WAL/audit/anchor/backup/idempotency state โดยตรวจว่าการ restore ที่ไม่สมบูรณ์นำไปสู่ `RECONCILIATION REQUIRED` ไม่ใช่ green state และไม่ resume telemetry จนกว่า schema, ownership, pairing, alerts, pending sync และ forensic bindings จะผ่าน

### 4.4 ทำต่อ: operational evidence bundle

สร้าง local-only status snapshot ที่รวม source revision, configuration hash แบบไม่รวม secret, schema/migration revision, health/readiness, disk headroom, backup freshness, last successful restore, audit-chain status, unresolved alerts, sync backlog และ rollback target พร้อม redaction และ correlation ID

### 4.5 ทำต่อ: dependency/release gate

ตรวจ dependency manifest, lock source revision, migration checksum, clean runtime tree, forbidden claims, secret markers และ reproducible test command เข้า phase-end gate เดียวกัน การตรวจนี้ช่วยให้ฐาน software release คงที่ แต่ไม่แทน external review หรือ target-host acceptance

## 5. ข้อจำกัดที่ทำไม่ได้จากภายในเพียงอย่างเดียว

ไม่สามารถใช้ local code หรือ simulation แทน real OIDC/JWKS, mTLS handshake/rotation/revocation, HIS sandbox exchange, Acer Windows account/firewall/disk encryption/power-loss/serial bench, OEM key custody, external WORM/trusted timestamp, clinical committee approval, consent/waiver, human-factors review, staff training, independent reviewer appointment หรือ signed external decision ได้

ดังนั้นการทำ internal hardening ต่อไปจะทำให้ระบบ **คงที่ ปลอดภัย ตรวจสอบซ้ำได้ และพร้อมเข้าสู่การทดสอบภายนอกมากขึ้น** แต่จะไม่เปลี่ยน `NOT_PRODUCTION_READY`, ไม่ปิด 7 blocked gates, ไม่ทำให้ 3 open gates กลายเป็น passed และไม่เปลี่ยน `clinical validation pending`

## 6. Claim boundary

สิ่งที่พูดได้จากงานภายในคือ **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**

ห้ามพูดว่า `clinical-ready`, `production-ready`, `tamper-proof` หรือ `HIPAA/PDPA compliant 100%` จาก software tests, local simulation หรือ readiness template เพียงอย่างเดียว

## 7. Evidence paths

- `internal_foundation_readiness.py`
- `test_internal_foundation_readiness.py`
- `test_internal_foundation_phase_end_hardening.py`
- `deployment_readiness.py`
- `edge_runtime.py`
- `backup_restore.py`
- `config.py`
- `schemas.py`
- `main.py`
- `PRODUCTION_READINESS_ROADMAP_20260820.md`
- `P1_002_HOST_HARDENING_READINESS_REPORT.md`
- `BACKUP_RESTORE_CONTRACT.md`
- `OPERATIONS_RUNBOOK.md`
- `PRODUCTION_READINESS_EVIDENCE_AUDIT.md`
- `tasks.md`
