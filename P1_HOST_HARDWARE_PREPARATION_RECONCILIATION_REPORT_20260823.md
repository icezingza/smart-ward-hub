# P1 Host-Hardware Preparation Reconciliation — Readiness Report

**โครงการ:** Smart Ward Hub Reconcile  
**วันที่จัดทำ:** 23 สิงหาคม 2026  
**Decision:** `P1_HOST_HARDWARE_PREPARATION_RECONCILED_PENDING_TARGET_HOST_EVIDENCE`  
**ขอบเขต:** local deterministic reconciliation; no target-host execution  
**สถานะผลิตภัณฑ์:** `CONTROLLED_PRODUCTION_PROTOTYPE` / `NOT_PRODUCTION_READY`

## 1. สรุปผล / Executive Summary

Guard นี้ cross-checks หลักฐานเตรียมความพร้อมที่มีอยู่จริงใน software repository ระหว่าง `deployment_readiness.py`, P1-002 host-hardening template, P0 Acer bench packet และ locked external-gate boundary. ผลตรวจยืนยันว่า deployment defaults แบบ pilot-safe ผ่านใน deterministic fixture, host-hardening manifest ยังเป็น software preparation template, และ Acer Spin N17H2 ถูกผูกเป็น `FIXED_EDGE_HUB_CANDIDATE` โดย bench packet ครบ schema/coverage/stop conditions แต่ยังไม่มี observed result หรือ physical execution.

การตัดสินใจจึงเป็น `RECONCILED_PENDING_TARGET_HOST_EVIDENCE`: artifacts ภายในสอดคล้องกันและไม่ overclaim แต่ไม่ได้หมายความว่า target Acer ผ่าน OS, disk, firewall, COM, USB/NFC/BLE, power-loss, thermal, backup/restore หรือ network tests แล้ว.

## 2. ผลตรวจหลัก / Reconciliation Results

| พื้นที่ | ผลที่ยืนยันได้ | ขอบเขตที่ยังไม่ยืนยัน |
|---|---|---|
| Deployment environment | `PASS`; pilot mode, docs/seed/auto-create disabled, loopback, explicit hosts, OIDC shape, external runtime paths, Device Trust enforce | live IdP/JWKS, host ACL, service identity, real network |
| Host-hardening manifest | `HOST_HARDENING_SOFTWARE_PREPARATION_READY`; `host_execution_status=NOT_STARTED` | Windows account, ACL, encryption, patch, firewall, service recovery |
| Fixed Hub target | `Acer Spin N17H2`, `FIXED_EDGE_HUB_CANDIDATE` | actual hardware/driver/COM and physical bench |
| Bench packet | 11 preconditions / 13 steps / 11 stop conditions | physical execution and observed results |
| Cross-artifact physical state | deployment `UNVERIFIED`, host `UNVERIFIED`, hardware `UNVERIFIED` | no physical validation claim |
| Clinical state | `PENDING`; no patient data used | clinical protocol, ground truth, safety sign-off |
| Authorization | external authority `NONE`; production/clinical false; runtime `NONE` | all external authorization and gate decisions |

## 3. Machine-readable evidence

หลักฐานหลักอยู่ที่ `evals/micro_rag/evidence/p1-host-hardware-preparation-reconciliation-local.json`.

| Field | Value |
|---|---|
| `generated_at_utc` | `2026-08-22T22:15:23.727660Z` |
| `evidence_scope` | `LOCAL_DETERMINISTIC_RECONCILIATION_ONLY` |
| `all_passed` | `true` |
| `target_model` | `Acer Spin N17H2` |
| `target_role` | `FIXED_EDGE_HUB_CANDIDATE` |
| `host_execution_status` | `NOT_STARTED` |
| `physical_execution_performed` | `false` |
| `observed_result_count` | `0` |
| `ready_for_target_host_execution` | `false` |
| `real_target_host_evidence` | `UNVERIFIED` |
| `external_submission_allowed` | `false` |
| `authorization_promoted` | `false` |
| `patient_data_used` | `false` |
| `external_gate_snapshot` | `7 BLOCKED / 3 OPEN / 0 PASSED` |

## 4. Focused และ phase-end verification

Focused/adversarial suite ผ่าน **8 cases** ได้แก่ local-only decision, deployment defaults/path separation, wildcard/non-loopback fail-closed, host execution promotion rejection, external-owner injection rejection, bench target/observed-result/physical-execution promotion rejection, raw identity/secret marker rejection, returned-evidence mutation isolation และ explicit authority/gate boundary.

Phase-end hardening ผ่าน:

| Gate | Result |
|---|---|
| Focused suite rerun | `PASSED` |
| AST network/provider/transport/scheduler side-effect import scan | `PASSED` |
| Execution/authority/secret boundary scan | `PASSED` |
| Runtime/cross-artifact boundary | `PASSED` |
| Exporter round-trip on temporary path | `PASSED` |
| JSON serialization/Zero-PII marker scan | `PASSED` |
| Returned-evidence mutation isolation | `PASSED` |
| `git diff --check` | `PASSED` |

## 5. Residual target-host evidence

การปิด residual gap ต้องใช้ evidence จาก Acer Spin N17H2 จริงภายใต้ approved non-production window ได้แก่ OS/patch inventory, dedicated service identity, filesystem ACL, disk encryption/key custody, firewall/listening ports, trusted time, power/battery/thermal, USB/NFC/BLE/COM, network interruption, reboot recovery, controlled power removal, low-disk drill, backup/restore และ certificate lifecycle. การทดสอบดังกล่าวต้องมี operator, stop authority, rollback owner, evidence custodian, redaction และ signed handoff ที่ตรวจสอบได้.

ไฟล์ `ACER_BENCH_READONLY_INVENTORY.md` เป็น negative/read-only inventory เท่านั้น และไม่ยืนยัน hardware reliability, driver compatibility, power-loss, network segmentation หรือ clinical validation.

## 6. Claim boundary

> `P1_HOST_HARDWARE_PREPARATION_RECONCILED_PENDING_TARGET_HOST_EVIDENCE` หมายถึง software deployment defaults, host preparation manifest และ bench packet มีสถานะสอดคล้องกันใน local fixture เท่านั้น ไม่ใช่การรัน bench จริงและไม่ใช่การอนุมัติให้เริ่ม hardware execution.

ค่าล็อกคือ `host_execution_status=NOT_STARTED`, `physical_execution_performed=false`, `observed_result_count=0`, `ready_for_target_host_execution=false`, `physical_validation=UNVERIFIED`, `hardware_evidence=UNVERIFIED`, `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE` และ `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.

External Gates ยังคง **7 `BLOCKED` / 3 `OPEN` / 0 `PASSED`**. งานนี้ไม่มี real host execution, real HIS/IdP/mTLS, clinical validation, WORM custody หรือ production authorization.

## 7. Repository evidence

- `p1_host_hardware_preparation_reconciliation.py`
- `export_p1_host_hardware_preparation_reconciliation.py`
- `test_p1_host_hardware_preparation_reconciliation.py`
- `test_p1_host_hardware_preparation_reconciliation_phase_end_hardening.py`
- `deployment_readiness.py`
- `p1_002_host_hardening_readiness.py`
- `p0_hardware_bench_evidence_readiness.py`
- `ACER_BENCH_READONLY_INVENTORY.md`
- `P0_HARDWARE_BENCH_CHECKLIST.md`
- `evals/micro_rag/evidence/p1-host-hardware-preparation-reconciliation-local.json`

## References

[1]: `deployment_readiness.py` — local pilot deployment configuration validator.
[2]: `p1_002_host_hardening_readiness.py` — P1 host-hardening preparation contract.
[3]: `p0_hardware_bench_evidence_readiness.py` — Acer bench packet readiness contract.
[4]: `ACER_BENCH_READONLY_INVENTORY.md` — read-only negative host inventory.
[5]: `evals/micro_rag/evidence/p1-host-hardware-preparation-reconciliation-local.json` — machine-readable reconciliation evidence.
