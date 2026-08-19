# P2-004 — Persistence Ownership, Retention & Access-Control Contract

**สถานะเริ่มต้น:** software design / not externally approved

เอกสารนี้กำหนด governance metadata สำหรับ registry snapshot และ derived index snapshot โดยไม่ทำให้ JSON snapshot กลายเป็น production source of truth อัตโนมัติ การมีไฟล์ snapshot ที่ hash ถูกต้องหมายถึงตรวจพบความสอดคล้องของ artifact เท่านั้น ไม่ใช่การอนุมัติการเก็บข้อมูล, access policy, clinical use หรือ external retention

## 1. Required policy fields

| Field | Requirement | Fail-closed rule |
|---|---|---|
| `policy_version` | Versioned contract identifier | Missing/unknown version rejects policy |
| `artifact_type` | `registry_snapshot` or `index_snapshot` | Unknown artifact type rejects policy |
| `owner_role` | Accountable data/product owner role | Must be non-empty and not a personal identity field |
| `custodian_role` | Operational custodian role | Must be non-empty and distinct from owner role for dual control |
| `storage_class` | `local_ephemeral`, `local_encrypted`, `managed_object_store`, `external_worm` | Unknown class rejects policy |
| `allowed_root` | Approved storage root reference | Absolute path outside approved project/runtime root rejects policy |
| `encryption_at_rest` | Boolean | Must be `true` for non-ephemeral storage |
| `access_mode` | `read_only`, `append_only`, or `controlled_write` | Unknown mode rejects policy |
| `retention_days` | Positive integer or explicit `0` for ephemeral | Negative/non-integer values reject policy |
| `backup_required` | Boolean | Non-ephemeral artifact without backup is not deployable |
| `integrity_verification` | `sha256_manifest`, `signed_manifest`, or `external_receipt` | Must not be empty |
| `raw_identity_allowed` | Boolean | Must always be `false` |
| `clinical_data_allowed` | Boolean | Must always be `false` for synthetic P2-004 artifact path |
| `external_authority` | Boolean | Must remain `false` until separately approved |
| `approval_state` | `UNAPPROVED`, `SOFTWARE_VERIFIED`, `EXTERNALLY_APPROVED` | Only `SOFTWARE_VERIFIED` is reachable by local tests |

## 2. Minimum policy profiles

| Artifact | Default software profile | Meaning |
|---|---|---|
| Registry snapshot | `local_ephemeral`, `read_only`, retention `0` | Rebuildable synthetic fixture artifact; no durable operational authority |
| Index snapshot | `local_ephemeral`, `read_only`, retention `0` | Derived artifact that must be rebuilt from registry when stale |
| Production registry snapshot | No default | Requires owner/custodian, encryption, backup, retention, access review and external approval |
| Clinical retrieval corpus | No default | Requires clinical governance, versioned approval, audit and human review; outside this software gate |

## 3. Ownership and access rules

The owner is accountable for the content and lifecycle decision; the custodian operates storage and restore procedures. Neither role grants clinical authorization. A local snapshot may be read by tests only when its manifest/index hash matches the source registry and all content remains synthetic, approved and zero-PII.

A policy cannot grant runtime authority. The runtime must reject snapshot use when the policy is missing, unapproved, expired, path-invalid, encryption-inconsistent, raw-identity-enabled, clinical-data-enabled, or inconsistent with the current registry/index manifest.

## 4. Retention and disposal rules

Retention is an operational governance decision, not a technical default. `retention_days=0` means ephemeral for the software fixture path and must not be silently converted into indefinite retention. Non-ephemeral storage requires backup/restore evidence, disposal procedure, access review and an owner-signed retention decision. External WORM retention remains `EXTERNAL_UNVERIFIED` until a real service receipt and chain-of-custody evidence exist.

## 5. Acceptance criteria

1. Invalid policy values are rejected deterministically.
2. `raw_identity_allowed=true` and `clinical_data_allowed=true` are always rejected by the local contract.
3. Owner and custodian roles are required and distinct.
4. Non-ephemeral storage requires encryption and backup.
5. A valid local policy remains `SOFTWARE_VERIFIED`, never `EXTERNALLY_APPROVED`.
6. The policy hash is deterministic and can be tied to registry/index artifact hashes.
7. No policy method can authorize clinical validation, production deployment or external gate closure.

## 6. Explicit boundary

This contract is a **software governance control**. It does not prove disk encryption, managed object-store immutability, backup recoverability, access-control enforcement, WORM retention, clinical governance or production deployment readiness. Those require separate external evidence and remain pending.
