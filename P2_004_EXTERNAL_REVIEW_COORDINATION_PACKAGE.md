# P2-004 — External Review Coordination Package

**Package type:** software evidence coordination and external-review preparation

**Current decision:** `BLOCKED_INCOMPLETE_EVIDENCE`

**Pilot gate:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

**Clinical validation authorized:** `false`

**Production authorized:** `false`

**Runtime authority:** `NONE`

## 1. Purpose and boundary

เอกสารนี้รวบรวมผล P2-004 registry/index hardening, repeated-sample protocol, model-specific reports, readiness preflight และ 10 External Gates เพื่อให้ผู้ตรวจสอบภายนอกใช้วางแผน review ต่อได้ ไม่ใช่คำอนุมัติ clinical validation, clinical deployment, production deployment หรือ regulatory compliance

## 2. Evidence map

| Evidence | Current result | Class | Review meaning |
|---|---|---|---|
| DocumentRegistry/RebuildableIndex v2 | Regression passed | `SOFTWARE_VERIFIED` | Deterministic software control only |
| Persistence ownership contract | Validator passed | `SOFTWARE_VERIFIED` | Governance metadata; external owner/retention still unverified |
| Gemini 2.5 index-backed rerun | 0/8; all provider HTTP 429 | `EXTERNAL_UNVERIFIED` / provider-limited | Not a quality score; clean provider-window rerun required |
| Gemini 3 index-backed rerun | 6/8; two provider HTTP 429 | `EXTERNAL_UNVERIFIED` / provider-limited | Six bounded accepted cases; insufficient repeated samples |
| Repeated-sample aggregate | One live sample per model | `SOFTWARE_VERIFIED` | Correctly remains `INSUFFICIENT_SAMPLES` |
| Runtime readiness preflight | `NOT_READY` | `SOFTWARE_VERIFIED` plus external blockers | Does not grant runtime authority |
| 10-gate coordination package | 7 `BLOCKED`, 3 `OPEN` | `COORDINATION_ARTIFACT_UNVERIFIED` | External evidence and owners remain required |

## 3. Current 10-gate matrix

| Gate | Status | Blocker / required next evidence |
|---|---|---|
| GV-01 | `BLOCKED` | Clinical governance protocol, signed scope and consent/waiver decision |
| GV-02 | `OPEN` | Privacy/security review, retention decision and access-control review |
| GV-03 | `BLOCKED` | Real HIS/Admission transcript, FHIR reconciliation and recovery evidence |
| GV-04 | `BLOCKED` | Real OIDC validation, mTLS handshake and key-rotation transcript |
| GV-05 | `OPEN` | Acer host hardening, firewall ACL and service recovery evidence |
| GV-06 | `BLOCKED` | Physical serial loopback, power-loss and disk-full drills; current Acer inventory has no enumerated COM port |
| GV-07 | `BLOCKED` | Independent WORM receipt, trusted timestamp and cross-boundary verification |
| GV-08 | `BLOCKED` | Manufacturer provenance, hardware key custody and revocation distribution |
| GV-09 | `BLOCKED` | Staff training, manual fallback SOP and alarm-fatigue review |
| GV-10 | `OPEN` | Independent analysis plan, adjudication plan and audit export review |

## 4. Review workflow

1. Reviewer verifies package manifest, source references, model revision, corpus revision, registry/index hashes and timezone-aware timestamps.
2. Reviewer checks that every model result is classified as accepted, provider-limited, runtime/adapter failure or quality rejection without mixing denominators.
3. Reviewer confirms repeated-sample minimum is met before accepting any aggregate as `ACCEPTED_FOR_EXTERNAL_REVIEW`.
4. Reviewer records findings with gate ID, evidence reference, severity, disposition and closure owner.
5. Reviewer verifies all blocked gates are explicitly reopened before new evidence submission.
6. Reviewer decides whether the package is accepted for external analysis only; any clinical or production decision remains outside this package.

## 5. Current blockers

The current package is blocked by insufficient compatible repeated samples, provider rate limiting, absent runtime semantic backend/access-control evidence, absent external persistence ownership/retention approval, pending clinical retrieval governance and the seven blocked external gates listed above.

## 6. Required reviewer decisions

| Decision | Current state |
|---|---|
| Accept software evidence for external review | Can be considered only as bounded coordination evidence; current repeated-sample decision remains blocked |
| Accept model quality score | `NO` — insufficient samples and provider-limited cases |
| Authorize clinical validation | `NO` |
| Authorize production deployment | `NO` |
| Authorize runtime semantic retrieval | `NO` |
| Close P2-004 | `NO` |

## 7. References

- `P2_004_REPEATED_SAMPLE_PROTOCOL.md`
- `P2_004_HARDENING_EVIDENCE.md`
- `P2_004_PERSISTENCE_OWNERSHIP_CONTRACT.md`
- `evals/micro_rag/evidence/MICRO_RAG_V2_RERUN_EVIDENCE.md`
- `evals/micro_rag/evidence/p2-004-external-review-handoff-20260820.json`
- `P1_007_EXTERNAL_VALIDATION_COORDINATION_PACKAGE.md`
- `GV10_INDEPENDENT_REVIEW_DOSSIER.md`

## 8. Product claim boundary

The repository status remains **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation**, **clinical validation pending** and **pilot deployment configuration pending**. This package must not be described as clinical-ready, production-ready, tamper-proof or clinical validation evidence.
