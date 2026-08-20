# External Authorization API Simulator — Wave A–D Hardening Plan

**ตรวจเมื่อ:** 2026-08-20
**ขอบเขต:** offline/in-memory simulator, regression และ repository evidence เท่านั้น
**สถานะ:** software-hardening plan; ไม่ใช่ external authorization และไม่ใช่ production approval

## วัตถุประสงค์

ปิดช่องว่างที่ตรวจและ harden ได้ใน local software โดยคง no-authorization boundary ไว้ตลอดเวลา ทุก response ต้องระบุ `simulation=true`, `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false` และ `runtime_authority=NONE` ส่วน endpoint จริง, IdP/mTLS, ACL, custody, trusted timestamp, external reviewer และ independent read-back ยังคงเป็น external validation scope ของ EA-020

## Disposition matrix

| Wave | Gaps | สถานะหลัง v2 | งาน software ที่ทำต่อ | หลักฐานรับรอง | ขอบเขตที่ยังปิดไม่ได้ใน repository |
|---|---|---|---|---|---|
| A — State integrity | EA-001, EA-002, EA-009, EA-010, EA-011, EA-019 | `PARTIAL_SOFTWARE_BASELINE` | immutable audit-store abstraction, transaction guard, deterministic serialization, concurrent command regression และ explicit incident record ที่หยุด state-changing commands | targeted negative tests, race tests, audit snapshot/hash evidence | append-only/WORM จริง, external notification, operator recovery approval |
| B — Decision validity | EA-003, EA-004, EA-012, EA-016 | `PARTIAL_SOFTWARE_BASELINE` | decision revision/ETag, server-observed time, expiry/revocation cache version, restart/replay fixture และ unknown-status fail-closed behavior | lifecycle, stale-poll และ restart/recovery tests | external revocation propagation, distributed cache, external decision authority |
| C — Delivery reliability | EA-005, EA-006, EA-007, EA-008, EA-017 | `PARTIAL_SOFTWARE_BASELINE` | bounded retry/reconciliation, bounded artifact/chunk validation, strict field typing และ redacted/size-bounded audit payload | mutation/fault-injection tests และ bounded-size evidence | real network timeout behavior, TLS/proxy limits, external upload service |
| D — Governance binding | EA-013, EA-014, EA-015, EA-018 | `PARTIAL_SOFTWARE_BASELINE` | governance freeze/verification binding, manifest evidence refs, signed-response verification contract และ version negotiation guard | package-binding, authenticity-negative และ compatibility tests | external signature trust chain, key custody, real reviewer decision |
| E — Real external validation | EA-020 | `EXTERNAL_UNVERIFIED` | จัดทำ test plan/owner/approval boundary เท่านั้น | external validation coordination package | endpoint จริง, OIDC/mTLS, ACL, custody, reviewer, independent read-back |

## Acceptance boundary

การปิด gap ใน Wave A–D จะถูกบันทึกเป็น `SOFTWARE_VERIFIED` หรือ `SIMULATION_ONLY` ตามหลักฐานเท่านั้น และจะไม่เปลี่ยนสถานะ 10 External Gates เป็น `PASSED` โดยอัตโนมัติ ไม่สร้าง `AUTHORIZED_BY_EXTERNAL_OWNER` จาก local code และไม่ยกระดับ product claim จาก **controlled production prototype** หรือ **P0-hardened software baseline**

## Stop conditions

ให้หยุด state-changing commands เมื่อ audit chain, persistence snapshot, manifest binding, clock policy, version compatibility หรือ response authenticity อยู่ในสถานะไม่ทราบแน่ชัด ให้สร้าง incident reference ที่ไม่บรรจุ raw identity และใช้ explicit recovery approval ก่อนเปิด state-changing path อีกครั้ง การทำงานต่อใน local simulator ไม่ถือเป็นการอนุญาตให้เปิด clinical workflow หรือ production network

## ลำดับการดำเนินงาน

1. ปิด Wave A ด้วย store abstraction, incident fail-stop และ concurrency regression
2. ปิด Wave B ด้วย decision version/cache/restart controls
3. ปิด Wave C ด้วย retry/reconciliation, bounded upload schema และ audit redaction
4. ปิด Wave D ด้วย governance binding, authenticity contract และ version negotiation
5. รัน master regression, สร้าง evidence record ใหม่, อัปเดต gap/risk/handoff และคง `NOT_PRODUCTION_READY`
6. เตรียม Wave E external test package โดยไม่เปลี่ยน authorization flags

> ผลสำเร็จของแผนนี้หมายถึง **functional verification passed** ในขอบเขตจำลองเท่านั้น ไม่ใช่ **clinical-ready**, **production-ready**, **tamper-proof** หรือ **HIPAA/PDPA compliant 100%**

## หลักฐานอ้างอิงภายใน

- `EXTERNAL_AUTHORIZATION_API_FAIL_CLOSED_GAP_REGISTER.md`
- `EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md`
- `EXTERNAL_AUTHORIZATION_API_SIMULATION_CONTRACT.md`
- `WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md`
- `PRODUCTION_READINESS_EVIDENCE_AUDIT.md`
- `controlled_pilot_handoff.py`
- `wave0_governance.py`
- `external_validation_package.py`

**Owner role:** `integration_owner` + `security_auditor`
**Independent verification required:** `true`
**External authority:** `NONE`
**Clinical validation authorized:** `false`
**Production authorized:** `false`
**Runtime authority:** `NONE`
**Pilot gate:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`
**Prepared by role:** `integration_owner`
**Chain-of-custody reference:** `repo://EXTERNAL_AUTHORIZATION_API_WAVE_A_D_HARDENING_PLAN.md`
**Redaction:** `PASS`
**Prepared timestamp:** `2026-08-20T08:00:00+00:00`

## References

[1]: EXTERNAL_AUTHORIZATION_API_FAIL_CLOSED_GAP_REGISTER.md
[2]: EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md
[3]: EXTERNAL_AUTHORIZATION_API_SIMULATION_CONTRACT.md
[4]: WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md
[5]: PRODUCTION_READINESS_EVIDENCE_AUDIT.md
[6]: controlled_pilot_handoff.py
[7]: wave0_governance.py
[8]: external_validation_package.py
