# Smart Ward Hub — Next Phase Priority Matrix

**Decision:** พักการสร้าง BMAX Android Roaming client/UI ไว้ชั่วคราว  
**Current status:** P0-hardened software baseline; controlled production prototype; pilot-ready foundation; clinical validation pending

## 1. Priority decision

การทำ BMAX client สามารถเลื่อนได้ เพราะ Fixed Hub มี roaming snapshot/command API, cursor/revision, idempotency และ safety boundary แล้ว การสร้าง UI ก่อนยืนยันระบบโรงพยาบาลจริงอาจทำให้ต้องแก้ซ้ำเรื่อง identity, network, tokenization, notification และ workflow ownership

## 2. Priority order

| Priority | Workstream | Why it matters now | Evidence/gate |
|---|---|---|---|
| P0 | HIS/Admission Gateway contract | กำหนด token issuer, TTL, revocation, acknowledgement และ mapping ระหว่าง admission กับ Hub | Contract test กับ sandbox HIS หรือ gateway ของโรงพยาบาล |
| P0 | OIDC and mTLS real integration | Static tokens และ local TLS config ยังไม่ใช่ identity/transport evidence ของโรงพยาบาลจริง | Real issuer/JWKS, audience, certificate chain, rotation and revocation test |
| P0 | Power-loss and storage recovery | Patient monitoring ต้องรู้ว่าหลังไฟดับ, disk-full หรือ filesystem error ระบบกลับมาปลอดภัยอย่างไร | Hardware power-cut, WAL recovery, checkpoint corruption, disk-full drill |
| P0 | Hardware bench validation | ตรวจ Acer host, charger, battery health, thermal behavior, USB/NFC/BLE gateway และ wired/network adapter | Soak test, reboot, local service recovery and device connectivity record |
| P1 | Backup/restore and host hardening | Application controls ไม่ครอบคลุม OS, physical host, encrypted storage, backup หรือ restore | Encrypted backup, restore drill, least privilege, firewall, patch and monitoring checklist |
| P1 | Key custody and provisioning | Device Trust software baseline ยังไม่มี manufacturer CA, secure element/HSM หรือ managed tablet identity | OEM/provisioning design, key rotation, revocation and lost-device drill |
| P1 | Clinical shadow-mode and human factors | Alert thresholds, RESET_PENDING, admission placement and walk-round workflow ต้องผ่าน clinical review | Approved protocol, stop conditions, alarm-fatigue review and staff walkthrough |
| P1 | External forensic anchoring | Local anchor เป็น tamper-evident ภายใน trust boundary เดียวเท่านั้น | Independent append-only/WORM service, trusted time, retention and verification drill |
| P2 | BMAX roaming client/UI | ทำหลัง identity, API, network, command semantics and device-management gates stable | Android kiosk, encrypted cache, managed identity, reconnect/conflict and usability tests |
| P2 | Multi-process/multi-ward scale-out | Current process-local limiter/state model assumes single Edge owner per ward | Coordinated limiter, shared state, distributed idempotency and topology test |

## 3. Work that can be done without BMAX now

The team can continue implementing and validating HIS/Admission Gateway adapters, OIDC/mTLS configuration contracts, hardware bench scripts, power-loss/recovery drills, backup/restore procedures, host hardening checklists, key lifecycle contracts, external-anchor adapter interfaces and clinical shadow-mode documentation without building the final Android UI.

## 4. Work deliberately deferred

The BMAX client should remain a thin authenticated operational client. It should not own telemetry, SQLite source of truth, patient identity mapping, forensic evidence or destructive reset authority. Its future implementation should consume the existing roaming snapshot/command APIs rather than introduce a second workflow contract.

## 5. Exit criteria before returning to BMAX client work

Return to BMAX client implementation after the project has a confirmed HIS/Admission Gateway contract, real authentication/transport configuration, a validated Acer/Edge bench, documented power-loss recovery, approved Tablet identity model, stable roaming API contract and clinical/human-factors review of the walk-round workflow.

## 6. Communication boundary

The correct product wording remains **pilot-ready foundation**, **functional verification passed**, **controlled production prototype** and **clinical validation pending**. Do not call any workstream clinical-ready, production-ready, tamper-proof or 100% compliant from software tests alone.
