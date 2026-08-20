# Controlled-Pilot Operations — Blocker Analysis

**Generated:** `2026-08-20T00:00:00Z`
**Operations state:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`
**Manifest hash:** `5f4cd2b5eb0251bcb07c9b1a429f1b28b75bb98a2481c5f24fdc2ab329630b05`

> ผลการตรวจนี้เป็น software/evidence coordination analysis เท่านั้น ไม่ใช่ External Authorization, clinical validation หรือ production approval

## Summary

| Metric | Result |
|---|---:|
| Total gates | 10 |
| Blocked gates analyzed | 7 |
| Open gates | 3 |
| Evidence-submitted gates | 0 |
| Manifest integrity checks passed | 6/6 |

## Blocker matrix

| Gate | Severity | Owner | Current evidence | Missing external evidence | Next action |
|---|---|---|---|---|---|
| GV-01 | CRITICAL | `clinical_owner` | software refs available | approved_protocol, consent_or_waiver, signed_scope | Appoint clinical owner/committee and approve protocol, scope and consent/waiver decision. |
| GV-04 | CRITICAL | `security_owner` | software refs incomplete | real_oidc_validation, real_mtls_handshake, key_rotation_transcript | Validate real IdP OIDC discovery/token claims, mTLS handshake, certificate lifecycle and key rotation transcript. |
| GV-06 | HIGH | `reliability_owner` | software refs available | serial_loopback_s015, power_loss_drill, disk_full_drill | Provision a non-production serial loopback fixture, enumerate a real COM port on Acer, then execute serial, power-loss and disk-full drills. |
| GV-08 | CRITICAL | `security_owner` | software refs available | manufacturer_provenance, hardware_key_custody, revocation_distribution | Obtain manufacturer provenance, hardware key custody, dual-control issuance, rotation, revocation and lost-device evidence. |
| GV-03 | HIGH | `integration_owner` | software refs incomplete | real_his_transcript, fhir_ack_reconciliation, failure_recovery | Run a sandboxed real-HIS/Admission contract session with structured acknowledgement, reconciliation and failure recovery evidence. |
| GV-07 | HIGH | `forensic_owner` | software refs available | external_worm_receipt, trusted_timestamp, cross_boundary_verify | Connect an independently managed append-only/WORM anchor and capture receipt identity, trusted timestamp and cross-boundary readback. |
| GV-09 | HIGH | `ward_manager` | software refs available | staff_training, manual_fallback_sop, alarm_fatigue_review | Approve staff training, manual fallback SOP, alarm-fatigue review and ward escalation/stop procedures. |

## Cross-cutting stop conditions

1. Do not promote the operations state while any blocker remains `BLOCKED` or external evidence remains `NOT_VERIFIED`.
2. Do not start physical, HIS, IdP, WORM, hardware-key or clinical activity without the named owner, isolated scope, rollback/stop condition and recorded approval.
3. A blocked gate must be explicitly reopened with a reason before new evidence is submitted.
4. Local manifest SHA-256 and signed-style receipt are tamper-evident simulation controls only; they do not prove external custody or cryptographic signing.
5. Clinical and production authorization remain false; runtime authority remains `NONE`.

## References

- `CONTROLLED_PILOT_OPERATIONS_GATE.md`
- `CONTROLLED_PILOT_OPERATIONS_REVIEW_CHECKLIST.md`
- `P2_004_EXTERNAL_REVIEW_COORDINATION_PACKAGE.md`
- `RISK_REGISTER.md`
