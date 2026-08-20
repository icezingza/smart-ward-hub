from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from deployment_readiness import validate_environment


ROOT = Path(__file__).resolve().parent
NOW = datetime(2026, 8, 20, 8, 30, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Finding:
    area: str
    control: str
    status: str
    evidence: str
    gap: str
    next_action: str
    severity: str


REQUIRED_FILES = {
    "software_core": [
        "main.py",
        "config.py",
        "run_all_tests.py",
        "test_security.py",
        "test_deployment_readiness.py",
        "external_authorization_api_simulator.py",
        "test_external_authorization_api_simulator.py",
    ],
    "continuity": [
        "backup_restore.py",
        "test_backup_restore.py",
        "BACKUP_RESTORE_CONTRACT.md",
    ],
    "governance": [
        "WAVE_0_GOVERNANCE_CONTRACT.md",
        "WAVE_0_GOVERNANCE_HANDOFF_REPORT.md",
        "WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md",
        "EXTERNAL_AUTHORIZATION_API_FAIL_CLOSED_GAP_REGISTER.md",
        "EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md",
        "ZERO_TRUST_TRUST_BOUNDARIES.md",
        "P1_HOST_HARDENING_CHECKLIST.md",
    ],
}


def _software_findings() -> list[Finding]:
    findings: list[Finding] = []
    for area, files in REQUIRED_FILES.items():
        missing = [name for name in files if not (ROOT / name).is_file()]
        findings.append(
            Finding(
                area=area,
                control="required source/test/document inventory",
                status="Implemented" if not missing else "Not Found",
                evidence="; ".join(files) if not missing else f"missing: {', '.join(missing)}",
                gap="none detected in repository inventory" if not missing else "required artifact is absent",
                next_action="keep in master regression" if not missing else "create or restore missing artifact",
                severity="INFO" if not missing else "HIGH",
            )
        )
    findings.append(
        Finding(
            area="simulated_external_api",
            control="offline handoff/status/finding/audit lifecycle",
            status="Experimental",
            evidence="external_authorization_api_simulator.py; test_external_authorization_api_simulator.py; v2 simulation JSON",
            gap="no real endpoint, OIDC/mTLS, ACL, signed response, external custody or network-failure transcript",
            next_action="run a separately approved non-production API test against the real external service before any production claim",
            severity="CRITICAL",
        )
    )
    return findings


def _deployment_findings() -> list[Finding]:
    pilot_env = {
        "SW_ENVIRONMENT": "pilot",
        "SW_AUTO_CREATE_DB": "false",
        "SW_SEED_DATA": "false",
        "SW_ENABLE_DOCS": "false",
        "SW_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "SW_AUTH_MODE": "oidc",
        "SW_OIDC_ISSUER": "https://idp.example.invalid/issuer",
        "SW_OIDC_AUDIENCE": "smart-ward-hub",
        "SW_OIDC_JWKS_URL": "https://idp.example.invalid/.well-known/jwks.json",
        "SW_DATABASE_PATH": "/var/lib/smart-ward-hub/ward_hub.db",
        "SW_TELEMETRY_STATE_PATH": "/var/lib/smart-ward-hub/edge_telemetry_state.json",
        "SW_AUDIT_LOG_PATH": "/var/log/smart-ward-hub/audit_events.jsonl",
        "SW_DEVICE_TRUST_MODE": "observe",
    }
    result = validate_environment(pilot_env, project_root=ROOT, bind_host="127.0.0.1", port=8080)
    findings = [
        Finding(
            area="deployment_config",
            control="pilot configuration preflight",
            status="Implemented" if result.status in {"PASS", "ADVISORY"} else "Experimental",
            evidence=f"deployment_readiness.validate_environment status={result.status}; physical_validation={result.physical_validation}; clinical_validation={result.clinical_validation}",
            gap="synthetic environment only; issuer, host, network and physical checks are not real evidence",
            next_action="run redacted preflight on the approved Acer host and external IdP environment",
            severity="HIGH" if result.status == "FAIL" else "MEDIUM",
        )
    ]
    findings.extend(
        [
            Finding(
                area="host_hardening",
                control="Acer Spin N17H2 host controls",
                status="Unverified",
                evidence="P1_HOST_HARDENING_CHECKLIST.md states physical host execution pending",
                gap="disk encryption, firewall, patch state, service identity, time, recovery and physical power tests are not verified",
                next_action="complete Acer bench evidence and retain redacted OS/ACL/firewall/service transcripts",
                severity="CRITICAL",
            ),
            Finding(
                area="hardware",
                control="Serial/power-loss/disk-full/hardware recovery",
                status="Unverified",
                evidence="SERIAL_BENCH_VALIDATION_PLAN.md and ACER_BENCH_READONLY_INVENTORY.md; physical COM port not enumerated",
                gap="no real serial loopback, power interruption, disk-full or sensor bench transcript",
                next_action="run the approved non-production physical bench procedure with the required confirmation phrase",
                severity="CRITICAL",
            ),
            Finding(
                area="identity_transport",
                control="OIDC/mTLS with real IdP/HIS",
                status="Unverified",
                evidence="config.py and deployment readiness validator only validate shape/selection",
                gap="issuer, claims, certificate chain, rotation, revocation, handshake and network segmentation are not verified",
                next_action="obtain external IdP/HIS owner, non-production credentials and handshake/rotation/revocation evidence",
                severity="CRITICAL",
            ),
        ]
    )
    return findings


def _continuity_findings() -> list[Finding]:
    return [
        Finding(
            area="backup_restore",
            control="SQLite backup API, manifest and isolated restore",
            status="Implemented",
            evidence="backup_restore.py and test_backup_restore.py; software restore status is verified",
            gap="physical destination encryption, retention owner, off-host custody and real recovery drill remain unverified",
            next_action="perform approved isolated restore on the target host and record RPO/RTO, retention and destination evidence",
            severity="HIGH",
        ),
        Finding(
            area="forensic_anchor",
            control="independent append-only/WORM evidence anchor",
            status="Unverified",
            evidence="external_anchor.py/FileAnchorStore software baseline and controlled-pilot manifest simulation",
            gap="no independent external receipt, trusted timestamp, key custody or read-back evidence",
            next_action="obtain an external anchor owner and run non-production append/read-back/rotation test",
            severity="CRITICAL",
        ),
    ]


def _clinical_and_governance_findings() -> list[Finding]:
    return [
        Finding(
            area="clinical_governance",
            control="clinical protocol, owner, consent/waiver and validation",
            status="Unverified",
            evidence="P1-006 readiness contract and Wave 0 checklist; clinical authorization remains false",
            gap="no clinical committee decision, protocol sign-off, shadow-mode outcome or human factors evidence",
            next_action="obtain named clinical owner/committee decision before any clinical workflow or accuracy claim",
            severity="CRITICAL",
        ),
        Finding(
            area="external_gates",
            control="10 External Gates",
            status="Unverified",
            evidence="current registry/operations package reports 7 BLOCKED, 3 OPEN, 0 PASSED",
            gap="GV-01, GV-03, GV-04, GV-06, GV-07, GV-08 and GV-09 require evidence outside the repository",
            next_action="follow EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md and reopen blocked gates before new evidence submission",
            severity="CRITICAL",
        ),
        Finding(
            area="production_claim",
            control="production authorization boundary",
            status="Planned",
            evidence="controlled_pilot_handoff.py and Wave 0 contracts force authorization flags false/NONE",
            gap="there is no evidence basis to call the product production-ready",
            next_action="do not promote claim; complete all external, host, hardware, clinical, backup and operational gates first",
            severity="CRITICAL",
        ),
    ]


def build_report() -> dict:
    findings = _software_findings() + _deployment_findings() + _continuity_findings() + _clinical_and_governance_findings()
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.status] = counts.get(finding.status, 0) + 1
    return {
        "report_type": "PRODUCTION_READINESS_EVIDENCE_AUDIT",
        "generated_at": NOW.isoformat(),
        "source_boundary": "repository code, tests, contracts and deterministic simulation only",
        "findings": [asdict(item) for item in findings],
        "status_counts": counts,
        "authorization": {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
        "overall_decision": "NOT_PRODUCTION_READY",
        "claim_boundary": [
            "controlled production prototype",
            "P0-hardened software baseline",
            "functional verification passed",
            "pilot-ready foundation",
            "clinical validation pending",
            "pilot deployment configuration pending",
        ],
        "forbidden_claims": ["clinical-ready", "production-ready", "tamper-proof", "HIPAA/PDPA compliant 100%"],
    }


def markdown(report: dict) -> str:
    rows = "\n".join(
        f"| {item['area']} | {item['control']} | **{item['status']}** | {item['evidence']} | {item['gap']} | {item['next_action']} | {item['severity']} |"
        for item in report["findings"]
    )
    count_rows = "\n".join(f"| `{key}` | {value} |" for key, value in sorted(report["status_counts"].items()))
    return f"""# Production-Readiness Evidence Audit — Smart Ward Hub

**Generated at:** `{report['generated_at']}`
**Source boundary:** `{report['source_boundary']}`
**Overall decision:** **`{report['overall_decision']}`**

> ผล audit นี้แยก software evidence ออกจาก external, hardware และ clinical evidence อย่างเคร่งครัด การที่มี source/test/contract ไม่ได้ทำให้ระบบได้รับ production authorization

## Decision summary

| Field | Value |
|---|---|
| `external_authority` | `{report['authorization']['external_authority']}` |
| `clinical_validation_authorized` | `{str(report['authorization']['clinical_validation_authorized']).lower()}` |
| `production_authorized` | `{str(report['authorization']['production_authorized']).lower()}` |
| `runtime_authority` | `{report['authorization']['runtime_authority']}` |
| `pilot_gate_status` | `{report['authorization']['pilot_gate_status']}` |

## Classification counts

| Classification | Count |
|---|---:|
{count_rows}

## Evidence audit matrix

| Area | Control | Status | Evidence | Gap | Next action | Severity |
|---|---|---|---|---|---|---|
{rows}

## Production blockers that cannot be closed by local software tests

The following controls require evidence outside this repository: real OIDC and mTLS with an approved IdP/HIS environment; Acer host hardening and physical serial/power-loss/disk-full tests; independent forensic anchoring and key custody; encrypted backup destination and real isolated restore; clinical protocol/owner/committee decision; and all remaining External Gates. The current registry remains at seven `BLOCKED`, three `OPEN`, zero `PASSED`.

## Current valid product statement

Use: **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation**, **clinical validation pending** and **pilot deployment configuration pending**.

Do not use: **clinical-ready**, **production-ready**, **tamper-proof** or **HIPAA/PDPA compliant 100%** based only on functional tests or local simulation.
"""


if __name__ == "__main__":
    report = build_report()
    json_path = ROOT / "production_readiness_audit-20260820.json"
    md_path = ROOT / "PRODUCTION_READINESS_EVIDENCE_AUDIT.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"decision": report["overall_decision"], "status_counts": report["status_counts"], "markdown": str(md_path), "json": str(json_path)}, ensure_ascii=False))
