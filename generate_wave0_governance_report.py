from __future__ import annotations

import json
from pathlib import Path

from wave0_governance import build_synthetic_wave0_package


ROOT = Path(__file__).resolve().parent
NOW = __import__("datetime").datetime(2026, 8, 20, 8, 0, tzinfo=__import__("datetime").timezone.utc)


def manifest_entries():
    return [
        {
            "evidence_id": "wave0-software-001",
            "artifact_ref": "repo://run_all_tests.py",
            "evidence_class": "SOFTWARE_VERIFIED",
            "claim_boundary": "software regression only; no external authorization",
        },
        {
            "evidence_id": "wave0-blocker-001",
            "artifact_ref": "repo://CONTROLLED_PILOT_BLOCKER_ANALYSIS.md",
            "evidence_class": "BLOCKER_RECORD",
            "claim_boundary": "external evidence remains unverified",
        },
    ]


def build_report():
    package = build_synthetic_wave0_package(NOW)
    prefreeze = package.validate(NOW)
    package.freeze_local(manifest_entries(), NOW)
    validation = package.validate(NOW)
    exported = package.export()
    return {
        "report_type": "WAVE_0_GOVERNANCE_HANDOFF",
        "generated_at": NOW.isoformat(),
        "source_boundary": "repository software baseline and deterministic local simulation",
        "governance_state": validation["state"],
        "prefreeze_state": prefreeze["state"],
        "validation": validation,
        "freeze": exported["freeze"],
        "role_count": len(exported["appointments"]),
        "required_roles": ["clinical_owner", "independent_reviewer", "stop_authority", "evidence_custodian"],
        "external_verification_status": "PENDING_EXTERNAL_VERIFICATION",
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "next_external_actions": [
            "appoint named external clinical owner and independent reviewer",
            "approve and sign scope with expiry and rollback",
            "approve isolated test window and stop authority",
            "verify evidence custodian and freeze record outside this baseline",
        ],
    }


def markdown(report: dict) -> str:
    checks = report["validation"]["checks"]
    rows = "\n".join(f"| `{key}` | {'PASS' if value else 'FAIL'} |" for key, value in checks.items())
    return f"""# Wave 0 Governance Handoff Report

**Generated at:** `{report['generated_at']}`
**Source boundary:** `{report['source_boundary']}`
**Governance state:** `{report['governance_state']}`
**External verification:** `{report['external_verification_status']}`

> รายงานนี้เป็น local software/evidence contract และ deterministic freeze simulation เท่านั้น ไม่ใช่ signed appointment, clinical approval, external authorization หรือ production authorization

## Current decision

| Field | Value |
|---|---|
| `pilot_gate_status` | `{report['pilot_gate_status']}` |
| `external_authority` | `{report['external_authority']}` |
| `clinical_validation_authorized` | `{str(report['clinical_validation_authorized']).lower()}` |
| `production_authorized` | `{str(report['production_authorized']).lower()}` |
| `runtime_authority` | `{report['runtime_authority']}` |
| `prefreeze_state` | `{report['prefreeze_state']}` |
| `postfreeze_state` | `{report['governance_state']}` |
| `role_count` | `{report['role_count']}` |

## Local validation checks

| Check | Result |
|---|---|
{rows}

## Freeze record

| Field | Value |
|---|---|
| `freeze_id` | `{report['freeze']['freeze_id']}` |
| `manifest_version` | `{report['freeze']['manifest_version']}` |
| `manifest_sha256` | `{report['freeze']['manifest_sha256']}` |
| `frozen_at` | `{report['freeze']['frozen_at']}` |
| `frozen_by_role` | `{report['freeze']['frozen_by_role']}` |
| `change_policy` | `{report['freeze']['change_policy']}` |
| `custody_ref` | `{report['freeze']['custody_ref']}` |
| `external_verification_required` | `{str(report['freeze']['external_verification_required']).lower()}` |
| `external_authority` | `{report['freeze']['external_authority']}` |

## Required external actions

The package can be sent to an external reviewer only as a governance preparation artifact. Before any real test window, external owners must appoint the clinical owner, independent reviewer, stop authority and evidence custodian; sign the bounded scope with expiry and rollback; approve the isolated window; and verify custody outside this repository.

1. Appoint external roles and record conflict declarations.
2. Sign scope and analysis plan with explicit in-scope and out-of-scope boundaries.
3. Approve the isolated test window, stop authority and rollback channel.
4. Verify the manifest freeze and custody record outside the local software baseline.
5. Keep clinical and production authorization false until the external decision is signed.

## Claim boundary

This report may state **software contract verified**, **local freeze simulated** and **ready for external governance review**. It must not state **clinical-ready**, **production-ready**, **tamper-proof**, **external WORM verified**, **clinical validation complete** or **controlled pilot authorized**.
"""


if __name__ == "__main__":
    report = build_report()
    json_path = ROOT / "evals/micro_rag/evidence/wave0-governance-handoff-20260820.json"
    md_path = ROOT / "WAVE_0_GOVERNANCE_HANDOFF_REPORT.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"state": report["governance_state"], "manifest_sha256": report["freeze"]["manifest_sha256"], "json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))
