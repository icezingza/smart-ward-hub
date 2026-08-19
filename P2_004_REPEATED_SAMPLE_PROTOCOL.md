# P2-004 — Repeated Model Sample Protocol & Review Decision Rules

**สถานะ:** protocol design; ยังไม่มี external approval

## 1. วัตถุประสงค์

Protocol นี้ใช้กำหนดว่าผล model-specific evaluation จะถูกนำไป review ต่อได้เมื่อใด โดยต้องรักษา model revision, corpus, registry/index provenance, prompt hash และ adapter version ให้เทียบกันได้ การทำซ้ำเป็นหลักฐานของ **software evaluation reproducibility** เท่านั้น ไม่ใช่ clinical accuracy, clinical validation, regulatory compliance หรือ production approval

## 2. Fixed evaluation identity

ทุก sample ในชุดเดียวกันต้องใช้ค่าต่อไปนี้ตรงกัน:

| Identity field | Requirement |
|---|---|
| `model_id` / `model_revision` | ต้องตรงกันและ catalog ต้องถูกตรวจสอบก่อนรัน |
| `corpus_revision` | ต้องตรงกัน |
| `retrieval_source` | ต้องเป็น `document-registry-v2/rebuildable-index-v2` สำหรับ current path |
| `registry_manifest_hash` / `index_hash` | ต้องตรงกัน |
| `adapter_version` | ต้องตรงกัน |
| case suite | ต้องมี 8 fixed cases ครบ |
| prompt/retrieval configuration | ต้องมี hash และตรงกัน |
| timestamp | ต้องเป็น timezone-aware UTC |
| redaction | Completed cases ต้อง `PASS` |

ห้าม aggregate ผลจาก fixture-direct path ปนกับ registry/index-backed path แม้ใช้ model revision เดียวกัน เพราะ retrieval provenance ไม่เท่ากัน

## 3. Sample-size rule

`min_samples=2` เป็น minimum software threshold สำหรับเปลี่ยนจาก `INSUFFICIENT_SAMPLES` ไปสู่การ review ต่อได้ โดยแต่ละ sample ต้องเป็นคนละ `run_id` และมี fixed evaluation identity ตรงกัน แนะนำให้คณะกรรมการกำหนดจำนวนซ้ำที่มากกว่านี้ตามวัตถุประสงค์และ provider availability ก่อนตัดสินใจภายนอก

Provider-limited cases ไม่ถูกนับเป็น quality denominator แต่ยังถูกนับเป็น evidence completeness blocker หากมีอยู่ใน sample set ใด ๆ

## 4. Quality denominator และ failure classes

| Classification | นับใน quality denominator | ผลต่อ decision |
|---|---:|---|
| Accepted case | ใช่ | ใช้คำนวณ completed-case pass rate |
| Quality/contract rejection | ใช่ | เปิด `QUALITY_REQUIRES_REVIEW` |
| Provider HTTP 429/5xx หรือ transient transport | ไม่ใช่ | เปิด `PROVIDER_LIMITED_REQUIRES_REVIEW` |
| Runtime/adapter error | ไม่ใช่ | เปิด `RUNTIME_OR_ADAPTER_REQUIRES_REVIEW` |
| Missing/duplicate/incompatible provenance | ไม่ใช่ | reject aggregation แบบ fail-closed |

ห้ามรายงาน `passed_cases / total_cases` เป็น quality score หาก denominator มี provider failures หรือจำนวน sample ยังต่ำกว่า minimum

## 5. Decision matrix

| Aggregated state | Decision | สิ่งที่อนุญาต | สิ่งที่ห้ามอ้าง |
|---|---|---|---|
| `INSUFFICIENT_SAMPLES` | `BLOCKED_INCOMPLETE_EVIDENCE` | ขอ rerun เพิ่ม | quality reliability, clinical readiness, production readiness |
| `PROVIDER_LIMITED_REQUIRES_REVIEW` | `BLOCKED_PROVIDER_WINDOW` | ขอ rerun ใน provider window ที่เหมาะสม | model quality failure/pass จาก provider-limited cases |
| `QUALITY_REQUIRES_REVIEW` | `REQUIRES_HUMAN_REVIEW` | เปิด finding และตรวจ raw bounded output/evidence | clinical safety หรือ approval |
| `REPEATED_EVALUATED_WITH_ADAPTER` | `ACCEPTED_FOR_EXTERNAL_REVIEW` | ส่งต่อ review package พร้อม provenance | clinical validation, runtime authority, production authorization |
| incompatible provenance | `REJECTED_FAIL_CLOSED` | แก้ source identity แล้วสร้าง sample ใหม่ | รวมผลข้าม corpus/index/prompt |

แม้ได้ `ACCEPTED_FOR_EXTERNAL_REVIEW` ระบบต้องคง `clinical_validation_authorized=false`, `production_authorized=false` และ `runtime_authority=NONE`

## 6. Rerun procedure

ผู้เตรียม evaluation ต้องบันทึก catalog verification, model revision, run ID, prompt hash, retrieval config hash, registry/index hashes, case-level transport status, bounded error class และ redaction status ก่อนส่ง sample เข้า aggregator ห้ามแก้ไข raw model output เพื่อทำให้ผ่าน; การ redaction ต้อง preserve provenance และบันทึกว่าเป็น output ที่ถูก redact แล้ว

## 7. Current decision

ผลปัจจุบันของ Smart Ward Hub ยังอยู่ที่ `INSUFFICIENT_SAMPLES` สำหรับทั้ง pinned Gemini 2.5 และ alternate Gemini 3 index-backed paths เพราะแต่ละ model มี live sample เพียงหนึ่ง run นอกจากนี้ Gemini 2.5 มี provider failures ครบ 8 cases และ Gemini 3 มี provider failures 2 cases จึงยังไม่เข้าเงื่อนไข `ACCEPTED_FOR_EXTERNAL_REVIEW`

## 8. Boundary

Protocol นี้เป็น software evaluation governance เท่านั้น ไม่ใช่ clinical protocol, patient-care protocol หรือ authorization record และไม่ปิด GV-01, GV-03, GV-04, GV-06, GV-07, GV-08, GV-09 หรือ GV-10 โดยอัตโนมัติ
