# Smart Ward Hub — P1 Device Trust and Secure Provisioning Handoff

**วันที่:** 20 สิงหาคม 2026 (GMT+7)

## สถานะ

Smart Ward Hub ยังคงเป็น **controlled production prototype** ที่มี **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation**, **pilot deployment configuration pending** และ **clinical validation pending**

เฟสนี้ยกระดับ P1-003 จากแนวคิด key custody ไปสู่ software contract baseline สำหรับ provisioning lifecycle โดยไม่จัดเก็บ private key และไม่อ้างว่า manufacturer CA, HSM หรือ secure element ถูกติดตั้งแล้ว

## ผลลัพธ์

| Control | Software evidence | External gate |
|---|---|---|
| Public identity | `device_id`, unique `key_id`, Ed25519 public-key fingerprint | Manufacturer provenance and anti-cloning evidence |
| Activation approval | Dual-control approver IDs required | Hospital IAM separation of duties |
| Custody attestation | CA/secure-element/non-exportability flags recorded | Real CA chain, attestation and hardware-in-loop test |
| Rotation | `previous_key_id` linkage; old credential suspended after new key activation | Firmware rollout, rollback and fleet coordination |
| Revocation | Reason required; revoked credential is terminal | Independent revocation distribution and offline policy |
| Lost device | Incident ID required; credential becomes `LOST` and revoked | MDM/asset process and replacement drill |
| Material safety | Private-key material rejected and absent from snapshots | HSM/secure element extraction-resistance evidence |

## Validation result

`test_key_custody_contract.py` passes dual-control activation, explicit software-fixture `UNVERIFIED` status, key rotation linkage, terminal revocation, lost-device transition and registry snapshot private-key exclusion. The test is deterministic and uses synthetic device identifiers only.

The software fixture is intentionally permitted only through `allow_software_fixture=True`. This keeps local development useful while preventing a software-only activation from being mistaken for hardware-backed trust. No production private key, factory secret, seed map or certificate private material is required or stored by this contract.

## Remaining gates

The P1-003 task remains **In Progress**. It requires an approved manufacturer CA or equivalent trust authority, secure-element/HSM custody, key generation and extraction policy, operator separation, rotation/revocation distribution, firmware interoperability, lost-device handling, clock/network behavior and hardware-in-loop evidence before Device Trust can be promoted from software baseline to deployment evidence.

The patient-safety boundary remains fail-safe: trust anomalies should audit, alert and enter controlled degraded-trust/quarantine handling rather than automatically brick a device or stop monitoring during a transient failure. Any future monitoring interruption requires clinical review and rollback evidence.
