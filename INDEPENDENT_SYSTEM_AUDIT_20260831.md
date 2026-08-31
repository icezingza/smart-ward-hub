# Smart Ward Hub — Independent System Audit

**Task ID:** SWH-AUDIT-20260831-01  
**Audit timestamp:** 2026-08-31T15:09:34Z–2026-08-31T15:13:06Z  
**Audited revision:** `042c1305db3b43fd7273cff2cb575b70e9a10fae`  
**Working tree:** modified `docker-compose.yml`; untracked `scripts/simulate_presentation.py`  
**Status:** `Unverified` for pilot, clinical, regulatory and production readiness

## 1. Documentation Review และภาพรวม

Smart Ward Hub has a stronger-than-average documentation and fail-closed design baseline for a controlled healthcare prototype. The repository contains real FastAPI endpoints, SQLite/Alembic persistence, scoped bearer/OIDC authentication, device-trust primitives, tamper-evident forensic controls, extensive software simulations and explicit evidence-boundary language.

It is not ready for a hospital pilot or market launch. The decisive blockers are external identity/mTLS validation, real HIS integration, hardware/key custody, clinical governance, privacy/legal artifacts, independent forensic custody, production operations evidence and an incomplete current regression run. No ISO 27001, SOC 2, PDPA, GDPR, clinical or production claim is supported by this audit.

### Strengths

- Claims policy explicitly rejects `tamper-proof`, `air-gapped`, clinical-ready and 100% compliance language.
- The API uses scoped authorization on protected routes, ORM queries, bounded request schemas, trusted-host middleware, restrictive CORS defaults and security response headers.
- SQLite WAL, foreign-key enforcement on SQLAlchemy connections, migrations and integrity/recovery controls exist.
- The repository separates software simulations from hardware, HIS, IdP, clinical and independent-review gates.

### Audit dashboard

| Audit area | Status | Short result |
|---|---|---|
| Documentation versus code | `Partially Verified` | Claims ส่วนใหญ่มี implementation pointer แต่ functional-pass claim ยัง reproduce ไม่ครบ |
| Code and architecture | `Partially Verified` | FastAPI 31 routes, ORM 15 tables, Alembic 6 revisions; external systems remain absent |
| Security | `Fail` | Core controls exist แต่ Aegis silently disables and production transport/container hardening is incomplete |
| Compliance | `Unverified` | ไม่มีหลักฐานรับรอง PDPA/GDPR, ISO 27001, SOC 2 หรือ clinical/regulatory readiness |
| Performance | `Unverified` | มีเพียง local `/health` smoke benchmark; ไม่มี representative k6/JMeter evidence |
| Legal and business | `Fail` | Legal/privacy package missing; business economics and customer evidence remain TBD |
| Market launch | `Blocked` | External, clinical, hardware, operations and support gates remain open |

### Critical/high risks

| ID | Severity | Finding | Evidence | Required action |
|---|---|---|---|---|
| A-001 | Critical | Pilot/clinical/external authorization remains open | `README.md:33-41`; readiness documents | Keep deployment blocked until named owners and external gates produce signed evidence |
| A-002 | High | Aegis integration silently disables itself because `security.py` calls `os.getenv` without importing `os`, and catches all exceptions | `security.py:19-36` | Import `os`, narrow exception handling, fail closed when Aegis is configured, add a regression proving manager initialization |
| A-003 | High | Current master regression is not green in this environment | Five modules passed; `test_forensics_signed.py` stopped on Windows-mounted temp key permissions; exit 1 | Make temp/key permission handling portable and rerun the complete suite on Python 3.12 CI-equivalent runtime |
| A-004 | High | Docker production hardening is incomplete | `Dockerfile:21-42`; no non-root user, no `.dockerignore`; compose publishes `8000:8000`, lacks TLS/healthcheck/read-only controls | Add non-root runtime, minimal build context, TLS/reverse-proxy boundary, healthcheck, capability/filesystem limits and explicit secrets |
| A-005 | High | CD vulnerability scan may scan stale/wrong image | `.github/workflows/cd.yml:123-130` scans `:latest`, while tag builds need not create `latest` | Scan the immutable `${{ steps.build.outputs.digest }}`; pin Trivy action to a commit, not `master` |
| A-006 | High | Legal/privacy/compliance package does not exist | No Privacy Policy, Terms, DPA/DPIA, RoPA, NDA/IP register or compliance control matrix found | Legal/privacy owners must create jurisdiction- and intended-use-specific controlled documents |
| A-007 | High | Business case is hypotheses, not a validated plan | `docs/BUSINESS_MODEL_HYPOTHESES.md:3-41`; all economics are TBD | Conduct buyer/user interviews, establish baseline KPIs and build signed pricing/cost/financial assumptions |
| A-008 | High | Production compose mixes migrations with `SW_AUTO_CREATE_DB=true` | `docker-compose.yml:12-25`; `.env.example` says false | Set false outside test/dev and require Alembic lineage; add startup check for expected head |
| A-009 | Medium | `/health` is liveness-like but reports `healthy` without dependency/readiness gates and exposes environment/runtime capacity metadata | `main.py:428-440` | Split `/livez` and authenticated/restricted `/readyz`; verify DB, migration head, storage, audit and trust prerequisites |
| A-010 | Medium | Supply-chain controls are incomplete | broad dependency ranges; GitHub Actions use mutable major tags and Trivy `master`; no license inventory/SBOM verification evidence | Lock dependencies with hashes, pin actions by SHA, add license policy and verify signed SBOM/provenance against image digest |

## 2. Claims versus Implementation Matrix

| Claim จากเอกสาร | Implementation status | หลักฐานจริง | วิธีตรวจสอบ | ผลการตรวจ | ข้อจำกัด/ข้อเสนอแนะ |
|---|---|---|---|---|---|
| Sovereign Edge / offline-first | Implemented baseline | `database.py:14-40`, Edge telemetry store, recovery modules | Inspect code; create temp DB; query PRAGMAs | `Partially Verified`: WAL และ integrity check ผ่าน | ต้องทดสอบ physical power loss, disk full และ ward outage |
| Zero-PII Edge | Implemented boundary | Opaque `patient_token`; identity-rejection schemas/tests | Inspect models/schemas/tests and API payloads | `Partially Verified` | Linkable tokens/telemetry ยังอาจเป็น personal/health data; ต้องทำ DPIA และ end-to-end data map |
| Bounded telemetry/replay rejection | Implemented baseline | `TelemetryPacket`, ring-buffer limits, sequence tests | Run pairing and telemetry modules | `Software Verified` ใน modules ที่รัน | ยังไม่มี real device, firmware, BLE/radio evidence |
| AI triage และ silent fall | Implemented simulation | `test_triage.py` | Run standalone test module | `Software Verified` | ไม่ยืนยัน sensitivity, specificity, clinical safety หรือ alarm fatigue |
| Tamper-evident forensics | Implemented baseline | Hash chain, RSA-PSS vault, verification endpoint | Run forensic/vault tests and inspect chain | `Software Verified` | ไม่มี WORM, trusted timestamp, HSM custody หรือ legal admissibility proof |
| HIS/FHIR interoperability | Contract implemented | Handover/sync routes and contract tests | Inspect endpoints/tests | `Implementation Present` | ไม่มี real HIS, mTLS, profile validation หรือ external receipt transcript |
| Bearer/OIDC authorization | Partially implemented | Scoped `Depends(require_scope(...))`; `oidc.py` | Curl protected API with/without token | 401 without token; 200 with local test token | Real IdP/JWKS/mTLS unverified; Aegis defect A-002 |
| Ed25519 Device Trust | Software baseline | Credential tables, enrollment/lifecycle endpoints, signature tests | Inspect model/routes/tests | `Implementation Present` | Manufacturer CA, secure element, provisioning and revocation drill absent |
| Outside-in admission | Implemented baseline | Bed/admission routes and local console | Inspect routes; call local bootstrap | `Implementation Present` | Real Admission Gateway, privacy placement and human factors unverified |
| Roaming tablet authority | Implemented API baseline | Snapshot/command routes, revision and idempotency | Inspect code/tests | `Implementation Present` | Android/MDM identity, encrypted cache and Wi-Fi roaming unverified |
| MQTT/WebSocket/Serial/BLE | Adapter/simulation baseline | Adapter, framing and pressure modules | Inspect modules and historical tests | `Implementation Present` | Physical Serial/BLE and firmware interoperability unverified |
| Micro-RAG bilingual/adversarial | Evaluation baseline | Registry, response adapter and eval suite | Inspect eval package/reports | `Implementation Present` | Provider repeatability and clinical corpus governance unverified |
| Master functional verification passed | Test runner exists | `run_all_tests.py`; historical reports | Run in isolated venv | `Not reproduced`: exit 1 after 5 passed modules | Fix WSL temp-key portability and rerun full Python 3.12 CI-equivalent suite |
| Pilot-ready foundation | Governance/software foundation exists | PRD, risk register, gate dossiers | Reconcile all external gates | `Proposed`; pilot remains blocked | ห้ามใช้เป็น pilot authorization หรือ clinical-ready claim |

## 3. Code & Architecture Audit

The implemented topology is a FastAPI edge service with 31 HTTP routes, SQLAlchemy/SQLite persistence, a process-local RAM telemetry store, append-only audit/forensic files and external adapter contracts. The Fixed Hub is intentionally authoritative; roaming and outside clients issue bounded requests rather than becoming a second source of truth.

Fifteen ORM tables cover patients, beds, admission preparations, devices and credentials, NFC pointers, sessions, pairings, telemetry aggregates, alerts, forensic packages, handovers, sync attempts and roaming commands. Six linear Alembic revisions run from `9e9c98c2eb7f` to `8c9d0e1f2a33`.

The temporary smoke database passed `PRAGMA integrity_check` and used WAL. It was created through `Base.metadata.create_all`, so it had no `alembic_version` table. That is acceptable for isolated tests but is not migration lineage evidence. Raw SQLite connections also report `foreign_keys=0`; application SQLAlchemy connections enable it through the connection event in `database.py:34-40`.

## 4. Security & Compliance Audit

### Application security

- **SQL injection:** No direct request-derived SQL interpolation was found in the reviewed API path; SQLAlchemy filtering dominates. The interpolated PRAGMAs use validated configuration values. Status: `No finding in reviewed scope`, not a proof of absence.
- **XSS:** The kiosk escapes dynamic values before `innerHTML`; admission UI uses `textContent`/DOM APIs. CSP is absent. Status: `Partially controlled`.
- **CSRF:** Bearer-header APIs do not use ambient cookie authentication. Local bootstrap endpoints are host/locality constrained and require a bootstrap token in pilot/production. Status: `Low current exposure`, but reverse-proxy trust must be validated.
- **Authentication/authorization:** Protected routes declare scopes and live smoke testing confirmed 401 without credentials. Real OIDC and Aegis paths remain unverified; A-002 is open.
- **Encryption:** Optional RSA-PSS signing and OIDC verification exist. Database-at-rest encryption is not implemented by SQLite configuration shown here; volume encryption/SQLCipher and key custody are external. TLS is not configured in compose.
- **Logging:** JSONL audit sink and request IDs exist, but durable centralized monitoring, retention, rotation, alerting and access review remain unverified.

### Compliance classification

| Framework | Status | Why |
|---|---|---|
| Thailand PDPA | `Unverified` | No lawful-basis/notice/rights/retention/breach/DPIA package and no controller-processor allocation |
| GDPR | `Unverified` | No Article 30 record, DPIA, DPA/SCC decision, data-subject process or breach workflow evidence |
| ISO/IEC 27001 | `Unverified` | No certified ISMS scope, SoA, internal audit, management review or certification evidence |
| SOC 2 | `Unverified` | No system description, control ownership, observation period or independent attestation |
| Clinical/regulatory | `Unverified` | Intended use, device classification, QMS, risk management, clinical evaluation and human-factors evidence are not approved |

## 5. Performance & Scalability

The only new quantitative result from this audit is a local liveness-endpoint smoke benchmark: 100 requests at concurrency 10 completed in 426 ms, approximately 234 requests/second. Single requests observed 5–16 ms. This measures a cheap `/health` handler on one local process; it says nothing about telemetry writes, SQLite contention, alert generation, cryptography, HIS latency, multi-worker consistency or ward hardware.

No k6/JMeter artifact or production-like workload profile was found. Existing pressure/ward/30-day simulations are software evidence, not a capacity plan. Before pilot, define SLOs and run a reproducible workload covering telemetry, pairing, alert acknowledgment, roaming snapshot/commands, WAL checkpointing, outage/recovery and disk pressure with p50/p95/p99, error rate, queue depth, memory, CPU and database lock metrics.

## 6. Verification & Evidence

Live verification used an isolated virtual environment, loopback FastAPI server and `/tmp` SQLite files only. The service returned HTTP 200 for `/health`, HTTP 401 for a protected route without credentials and HTTP 200 with the configured local test credential. WAL and database integrity were confirmed. No production endpoint, patient record, hospital network or external provider was touched.

The master regression result is `Fail/Incomplete`, not green: five modules passed before `test_forensics_signed.py` failed because the Windows-mounted temporary key did not satisfy POSIX mode `0400`. This is consistent with fail-closed key permission enforcement, but it is also a portability gap in the test harness.

Evidence quality labels used here:

| Label | Meaning |
|---|---|
| `Software Verified` | Code path was executed successfully in this isolated checkout |
| `Partially Verified` | Some implementation and runtime evidence exists, but material gates remain |
| `Implementation Present` | Source exists; complete runtime behavior was not reproduced |
| `Unverified` | No sufficient current evidence |
| `Blocked` | Required approval/external dependency prevents legitimate execution |

## 7. Legal, Business & Market Launch Readiness

Privacy Policy and Terms of Service cannot be responsibly finalized from source code alone. They require the legal entity, intended users, jurisdictions, data-controller/processor roles, lawful basis, retention, subprocessors, contact channels, incident obligations and hospital contracts. Drafting generic documents now would create false assurance.

NDA, IP assignment, open-source license obligations, trademark clearance and patentability/FTO evidence were not found. There is also no root LICENSE file. The investor/presentation material in the repository is not a validated investor deck because traction, market size, pricing, financial model, team, use of funds and verified outcomes are absent or hypothetical.

Beta testing, UX findings, market plan, brand clearance and support/maintenance SLA evidence were not found. Real beta testing is blocked until governance authorizes a non-production or shadow-mode protocol with synthetic/de-identified data, stop criteria, incident handling and named owners.

### Market launch readiness matrix

| Launch workstream | Status | Evidence/gap | Exit gate |
|---|---|---|---|
| Controlled beta | `Blocked` | ไม่มี approved protocol, site, named clinical owner หรือ feedback dataset | Governance-approved synthetic/shadow protocol and stop criteria |
| UX/UI validation | `Unverified` | มี local kiosk/admission UI แต่ไม่มี usability/human-factors report | Representative users, scripted tasks, severity-ranked findings and remediation |
| Branding/marketing | `Unverified` | มี presentation content แต่ไม่มี trademark clearance หรือ evidence-approved claims pack | Brand/legal approval and claim-to-evidence review |
| Support/maintenance | `Unverified` | Runbook exists แต่ไม่มี SLA, escalation rota, patch cadence หรือ replacement process | Signed operating model, support hours, RACI, SLA/SLO and incident drills |
| Commercial launch | `Blocked` | Buyer/pricing/unit economics remain hypotheses/TBD | Validated buyer, pricing, cost model, contract and measurable pilot conversion gate |

## 8. Strategic Recommendations / Next Actions

1. Fix A-002 and the WSL-safe forensic key test, then reproduce the entire master suite on Python 3.12 and archive exact counts/logs.
2. Harden Docker/CD: non-root, `.dockerignore`, immutable digest scan, action SHA pinning, secret injection, TLS boundary, health/readiness checks and `SW_AUTO_CREATE_DB=false`.
3. Run threat-model-driven tests for auth, scope matrix, local bootstrap/proxy spoofing, body streaming without `Content-Length`, rate-limit topology, audit redaction and forensic deletion/custody.
4. Obtain real IdP/OIDC+mTLS and HIS sandbox owners; run negative, expiry, revocation, retry and reconciliation tests with signed transcripts.
5. Appoint privacy, security, clinical, operations and legal owners; complete DPIA/data-flow/retention/access/incident and intended-use decisions.
6. Execute hardware bench, power-loss, storage exhaustion, backup/restore and key provisioning/revocation drills on approved non-production equipment.
7. Validate business hypotheses with interviews and a controlled pilot scorecard before building financial forecasts or investor claims.

## 9. Audit Plan พร้อมตัวอย่างคำสั่ง

Commands below are templates for an approved non-production environment. Replace placeholders; never send real patient identifiers or credentials into logs.

### API authorization and readiness

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/api/v1/kiosk/bootstrap
curl -i -H 'Authorization: Bearer <REDACTED_NONPROD_TOKEN>' \
  http://127.0.0.1:8000/api/v1/kiosk/bootstrap
```

### Database migration and integrity

```sql
PRAGMA journal_mode;
PRAGMA integrity_check;
PRAGMA foreign_key_check;
SELECT version_num FROM alembic_version;
SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name;
```

### CI-equivalent software verification

```bash
python3.12 -m venv /tmp/swh-verification-venv
/tmp/swh-verification-venv/bin/pip install -r requirements.txt
/tmp/swh-verification-venv/bin/python -m pip check
/tmp/swh-verification-venv/bin/python run_all_tests.py
```

### Load test gate

```bash
# Run only against an approved isolated target after defining workload and SLOs.
k6 run -e BASE_URL=http://127.0.0.1:8000 loadtest.js
```

Required k6 scenarios: authenticated telemetry ingestion, duplicate/replay rejection, alert acknowledgement, roaming snapshots, SQLite contention, outage/reconnect and recovery. Record p50/p95/p99, throughput, error rate, CPU, memory, WAL growth, lock time and dropped samples. Do not use the 234 req/s `/health` smoke result as a capacity claim.

## Appendix A — Commands and observed results

```text
git rev-parse HEAD
=> 042c1305db3b43fd7273cff2cb575b70e9a10fae

python3 --version
=> Python 3.14.4

python3 -m compileall -q .
=> exit 0

git diff --check
=> exit 0

/tmp/swh-audit-venv/bin/python -m pip check
=> No broken requirements found; exit 0

/tmp/swh-audit-venv/bin/python run_all_tests.py
=> five modules passed; stopped at test_forensics_signed.py; exit 1
=> RuntimeError: forensic signing key is group/other accessible; chmod 0400 required

curl http://127.0.0.1:8765/health
=> HTTP 200, 15.719 ms

curl http://127.0.0.1:8765/api/v1/kiosk/bootstrap
=> HTTP 401, 5.230 ms

curl -H 'Authorization: Bearer [REDACTED]' http://127.0.0.1:8765/api/v1/kiosk/bootstrap
=> HTTP 200, 7.203 ms

SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
=> 15 application tables

PRAGMA journal_mode;
=> wal

PRAGMA integrity_check;
=> ok

SELECT version_num FROM alembic_version;
=> no such table in create_all smoke database

100 local GET /health, concurrency 10
=> 426 ms total; approximately 234 req/s
```

## Appendix B — Evidence limitations

No production system, hospital network, patient data, real IdP, real HIS, WORM provider, physical serial/BLE device, HSM/secure element or clinical workflow was accessed. No destructive test, restore, deployment, external scan or stress test was performed. Remote GitHub Actions and Artifact Registry state were not verified. Results apply only to the stated revision plus the pre-existing dirty working tree at the stated time.
