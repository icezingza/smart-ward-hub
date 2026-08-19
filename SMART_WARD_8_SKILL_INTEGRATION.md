# Smart Ward Hub — 8-Skill Integration

**วันที่:** 20 สิงหาคม 2026 (GMT+7)  
**สถานะ:** Project-local control-plane baseline created; deployment and hospital validation remain pending

## Executive decision

การสร้าง 8-Skill integration **สมควรทำ** เพราะช่วยยกระดับ Smart Ward Hub จากชุดซอฟต์แวร์ที่ผ่าน functional regression ไปสู่ระบบที่มี **operational governance, evidence discipline, approval gates, backup/recovery discipline และ risk routing** ที่ชัดเจนขึ้น โดยไม่เพิ่ม clinical authority ให้กับ agent และไม่ทำให้ control plane กลายเป็นแหล่งข้อมูลผู้ป่วยชุดที่สอง

รูปแบบที่เลือกไม่ใช่การทำซ้ำ global skills ทั้งหมด แต่เป็น **project-local overlays** ใน `.claude/skills/` ซึ่งกำหนดกติกาเฉพาะของ Smart Ward Hub ให้แต่ละ skill ทำงานสอดคล้องกับ Fixed Edge Hub, Zero-PII, Device Trust และ clinical safety boundary

## What was created

| Area | Path | Purpose | Status |
|---|---|---|---|
| Skill registry | `.agents/registry/skills.yaml` | Registry ของ 8 skills, role, allowed/forbidden targets และ non-negotiable boundaries | Implemented |
| Permissions | `.agents/policies/permissions.yaml` | Least privilege, approval gates, secret rules และ approved claims | Implemented |
| Pilot workflow | `.agents/workflows/pilot-gates.yaml` | ลำดับ inventory → routing → host → dry-run → backup → trust → recurring checks → review → approval → clinical shadow mode | Implemented |
| Evidence guidance | `.agents/evidence/README.md` | Redaction, status vocabulary และการแยก simulation จาก hardware/clinical evidence | Implemented |
| Eight overlays | `.claude/skills/*/SKILL.md` | Smart Ward-specific instructions for the eight reference skills | Implemented |

## Eight-skill mapping

| Skill | Smart Ward responsibility | What it must not do |
|---|---|---|
| `create-vps` | เตรียมและ harden Acer Spin N17H2 Fixed Edge Hub, firewall, operator, storage และ host prerequisites | ไม่ยุ่งกับ patient identity หรือเปิด network โดยไม่มี approval |
| `setup-control-room` | dry-run, setup, upgrade, manifest, migration review และ rollback gates | ไม่รัน vendor installer หรือ production apply โดยเดาเอง |
| `agent-task-router` | จัดกลุ่มงานตาม risk, capability, dependency และ approval | ไม่ทำ clinical triage, alarm suppression หรือ admission authorization |
| `agent-registry-manager` | จัดการ registry ของ service, adapter, agent และ Device Trust lifecycle metadata | ไม่เก็บ raw telemetry, patient record หรือ private key |
| `agent-backup-manager` | WAL-aware backup, checksum, retention และ isolated restore evidence | ไม่ copy active SQLite เฉพาะ `.db` และไม่ claim restore จนกว่าจะทดสอบจริง |
| `agent-security-auditor` | ตรวจ Zero-PII, auth, OIDC/mTLS, Device Trust, rate limit, input validation และ residual risk | ไม่สรุป compliance/clinical readiness จากชื่อฟีเจอร์หรือ functional tests |
| `agent-team-cron-planner` | วาง recurring health, backup, audit และ forensic-anchor verification jobs | ไม่ automate clinical decision, alert resolution หรือ unapproved export |
| `agent-control-room` | status, approvals, incidents, evidence links และ rollback state | ไม่เป็น clinical source of truth หรือแสดง component healthy เมื่อ evidence stale |

## Why this improves the system

### 1. It adds operational control without changing clinical logic

Smart Ward Hub already has a Fixed Edge Hub as the source of truth and a set of patient-safety workflows. The eight skills now coordinate host preparation, backups, audits, registry state and approvals around that core. They may observe, verify, route and record; they do not reinterpret telemetry or autonomously decide what should happen to a patient.

### 2. It makes evidence status explicit

Every operational conclusion is expected to use one of five labels: `Implemented`, `Experimental`, `Planned`, `Not Found` or `Unverified`. This prevents software simulation results from being presented as proof of Acer hardware behavior, hospital network reliability, real IdP integration, external WORM anchoring or clinical validity.

### 3. It strengthens the Zero-PII boundary

The project-local control plane explicitly prohibits raw HN, names, national IDs, addresses, phone numbers, free-text clinical notes, bearer tokens, JWTs, private keys and full telemetry payloads in registry, policy, workflow and evidence artifacts.

### 4. It introduces approval and rollback gates

Apply, restore, export, credential rotation/revocation, network exposure, host changes and clinical workflow changes now require explicit approval plus prerequisites such as backup, reviewed diff, destination allowlist, redaction and rollback path.

### 5. It supports the product differentiators

The integration operationalizes the product’s core differentiators: **Sovereign Edge / Offline-first**, **Zero-PII**, **Patient Safety Intelligence**, **Tamper-Evident Evidence**, **HIS/EMR Interoperability**, **Device Trust & Secure Provisioning**, **Outside-in Ward Workflow** and **Sovereign Ward Operating Layer**.

## Boundary with the future BMAX client

The BMAX i11_s remains a roaming operational client candidate, not an authority. When implemented, it should consume the existing snapshot/cursor and idempotent command contracts. It must not own SQLite, patient identity mapping, forensic evidence, alert truth or destructive reset confirmation. Deferring the UI until HIS, identity, network, hardware and clinical workflow gates are stable remains the safer sequence.

## Evidence status and residual risk

The 8-Skill integration itself is an **Implemented project-local control-plane baseline**. It does not prove that the following gates are complete:

| Gate | Current status | Required evidence |
|---|---|---|
| Real OIDC issuer/JWKS and token lifecycle | Planned / Unverified | Real IdP integration, rotation, audience and revocation tests |
| Real mTLS certificate chain and rotation | Planned / Unverified | Hospital PKI or test CA handshake and renewal evidence |
| Acer Spin N17H2 bench validation | Planned | Reboot, thermal, charging, network and service recovery transcript |
| Power-loss and storage recovery | Planned | Controlled power cut, WAL recovery, disk-full and corruption drill |
| External forensic anchoring | Planned | Independent append-only/WORM destination and verification drill |
| Key custody and provisioning | Planned | Custody model, rotation, revocation and lost-device procedure |
| Clinical/human-factors validation | Pending | Shadow-mode protocol, stop conditions and clinical review |
| Real HIS/Admission Gateway integration | Contract baseline only | Sandbox or hospital integration test |

## Conclusion

The correct conclusion is: **8-Skill integration is worthwhile and has been implemented as a governance/control-plane baseline. Smart Ward Hub remains a controlled production prototype with a P0-hardened software baseline, a pilot-ready foundation and clinical validation pending. Pilot deployment configuration is still pending external validation.**

It should be committed alongside the Smart Ward Hub code, provided the repository review confirms that no runtime state, credentials or private artifacts are included.
