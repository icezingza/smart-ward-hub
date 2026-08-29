# Smart Ward Hub — Technical Due-Diligence Index

**Status:** Template for investor, design-partner and independent technical review.

| Area | Evidence | Location/status |
|---|---|---|
| Product boundary | Intended use, exclusions, claims policy | `docs/PRODUCT_BOUNDARY.md` |
| Architecture | Edge/Hub/console/HIS/evidence boundaries | `architecture.md`, `EDGE_HUB_ARCHITECTURE.md` |
| API contracts | Endpoint, scope, idempotency and error inventory | `docs/API_DATA_FLOW_INVENTORY.md` + schemas |
| Threat model | Trust boundaries and abuse cases | `docs/THREAT_MODEL.md` |
| Quality gates | CI, compile, pip check, dependency audit, regression | `.github/workflows/ci.yml` |
| Test evidence | Unit/integration/readiness/negative gates | `run_all_tests.py` and `test_*.py` |
| Dependency/SBOM | Locked requirements, audit output, license list | `requirements.txt`, CI artifact — pending release run |
| Release integrity | Source/file hash freeze and drift monitor | `freeze_release_candidate.py`, `freeze_integrity_monitor.py` |
| Operations | Deployment, monitoring, backup/restore, incident and rollback | `docs/OPERATIONS_RUNBOOK.md` |
| Pilot gates | Site, clinical, security, HIS, hardware and privacy approvals | `docs/PILOT_READINESS_CHECKLIST.md` |
| Hardware | BOM, protocol and bench test matrix | `docs/HARDWARE_BOM_AND_TEST_MATRIX.md` |
| Privacy | Data-flow, retention, access and redaction evidence | `docs/API_DATA_FLOW_INVENTORY.md` + site DPA/privacy review — pending |
| Clinical | Clinical owner, protocol and outcome plan | External/site evidence — pending |
| Regulatory | Intended-use classification and jurisdiction decision | Regulatory review — pending |
| Reliability | Software simulation and recovery tests | Existing reports; hardware/field evidence — pending |
| Commercial | Buyer, pricing, deployment/support economics | `docs/BUSINESS_MODEL_HYPOTHESES.md` |
| IP/open source | Ownership, contributor and license inventory | Founder/legal review — pending |
| Known limitations | Residual risk and blocked gates | `RISK_REGISTER.md`, `CONTROLLED_PILOT_BLOCKER_ANALYSIS.md` |

## Review protocol

The reviewer should first reproduce the branch from a clean clone, verify the commit and environment, run CI, inspect the data-flow and threat model, then sample critical controls against tests. Reviewers must distinguish source-code claims, software simulation, bench evidence, controlled pilot evidence and clinical evidence. Any missing evidence remains `PENDING` rather than being inferred from documentation.

## Release package checklist

A review package should include the commit SHA, dependency lock/SBOM, CI result, test report, redacted configuration fingerprint, architecture/data-flow diagrams, threat model, risk register, backup/restore result, rollback result, hardware matrix, pilot protocol, training plan, incident form, privacy/legal approvals, regulatory assessment, customer acceptance criteria and a signed decision record.
