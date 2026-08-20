from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from controlled_pilot_operations import EvidenceManifest, EvidenceManifestItem, BlockerRecord
from external_validation_package import default_pilot_package


ROOT = Path(__file__).resolve().parent
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9][A-Z0-9-]{1,}|\s+[0-9][A-Z0-9-]{1,})\b", re.IGNORECASE)
EXPECTED_BLOCKERS = ("GV-01", "GV-03", "GV-04", "GV-06", "GV-07", "GV-08", "GV-09")
EXPECTED_GATE_STATUSES = {
    "GV-01": "BLOCKED", "GV-02": "OPEN", "GV-03": "BLOCKED", "GV-04": "BLOCKED",
    "GV-05": "OPEN", "GV-06": "BLOCKED", "GV-07": "BLOCKED", "GV-08": "BLOCKED",
    "GV-09": "BLOCKED", "GV-10": "OPEN",
}

BLOCKER_PROFILE = {
    "GV-01": {
        "severity": "CRITICAL", "owner_role": "clinical_owner", "priority": 1,
        "software_refs": ["P1_006_CLINICAL_VALIDATION_READINESS_PLAN.md", "clinical_validation_readiness.py"],
        "external_action": "Appoint clinical owner/committee and approve protocol, scope and consent/waiver decision.",
        "stop_condition": "Do not begin interventional or clinical validation activity without signed governance scope.",
    },
    "GV-03": {
        "severity": "HIGH", "owner_role": "integration_owner", "priority": 2,
        "software_refs": ["test_p0_his_admission_contract.py", "P0_HIS_ADMISSION_CONTRACT.md"],
        "external_action": "Run a sandboxed real-HIS/Admission contract session with structured acknowledgement, reconciliation and failure recovery evidence.",
        "stop_condition": "Do not connect to a real HIS or transmit admission data until integration owner approves boundary and rollback.",
    },
    "GV-04": {
        "severity": "CRITICAL", "owner_role": "security_owner", "priority": 1,
        "software_refs": ["test_security.py", "mtls_launcher.py", "config.py"],
        "external_action": "Validate real IdP OIDC discovery/token claims, mTLS handshake, certificate lifecycle and key rotation transcript.",
        "stop_condition": "Do not enable production identity transport or accept real credentials from software simulation alone.",
    },
    "GV-06": {
        "severity": "HIGH", "owner_role": "reliability_owner", "priority": 1,
        "software_refs": ["SERIAL_BENCH_VALIDATION_PLAN.md", "ACER_BENCH_READONLY_INVENTORY.md", "serial_bench_runner.py"],
        "external_action": "Provision a non-production serial loopback fixture, enumerate a real COM port on Acer, then execute serial, power-loss and disk-full drills.",
        "stop_condition": "Do not run physical test without fixture isolation, COM-port evidence and operator confirmation `I_HAVE_A_NONPRODUCTION_LOOPBACK`.",
    },
    "GV-07": {
        "severity": "HIGH", "owner_role": "forensic_owner", "priority": 2,
        "software_refs": ["P1_004_EXTERNAL_ANCHOR_CONTRACT.md", "external_anchor.py", "test_external_anchor_contract.py"],
        "external_action": "Connect an independently managed append-only/WORM anchor and capture receipt identity, trusted timestamp and cross-boundary readback.",
        "stop_condition": "Do not describe local FileAnchorStore or simulated receipt as external immutability or tamper-proof evidence.",
    },
    "GV-08": {
        "severity": "CRITICAL", "owner_role": "security_owner", "priority": 1,
        "software_refs": ["KEY_CUSTODY_PROVISIONING_CONTRACT.md", "key_custody_contract.py", "test_key_custody_contract.py"],
        "external_action": "Obtain manufacturer provenance, hardware key custody, dual-control issuance, rotation, revocation and lost-device evidence.",
        "stop_condition": "Do not bind real devices or treat software key lifecycle tests as hardware root-of-trust evidence.",
    },
    "GV-09": {
        "severity": "HIGH", "owner_role": "ward_manager", "priority": 2,
        "software_refs": ["OPERATIONS_RUNBOOK.md", "P1_005_CLINICAL_SHADOW_REVIEW.md", "P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md"],
        "external_action": "Approve staff training, manual fallback SOP, alarm-fatigue review and ward escalation/stop procedures.",
        "stop_condition": "Do not start controlled pilot without trained staff, manual fallback and incident escalation owner.",
    },
}


def load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("operations report must be a JSON object")
    return payload


def validate_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    manifest_payload = payload["manifest"]
    items = tuple(EvidenceManifestItem(**item) for item in manifest_payload["items"])
    manifest = EvidenceManifest(
        manifest_version=manifest_payload["manifest_version"],
        manifest_id=manifest_payload["manifest_id"],
        generated_at_utc=manifest_payload["generated_at_utc"],
        previous_manifest_hash=manifest_payload.get("previous_manifest_hash"),
        items=items,
        claim_boundary=manifest_payload["claim_boundary"],
    ).validate()
    computed_hash = manifest.manifest_hash()
    receipt = payload.get("simulated_detached_receipt", {})
    checks = {
        "manifest_schema": True,
        "manifest_hash_matches_report": computed_hash == payload.get("manifest_hash"),
        "receipt_manifest_hash_matches": receipt.get("manifest_hash") == computed_hash,
        "receipt_is_non_cryptographic_simulation": receipt.get("receipt_type") == "SIGNED_STYLE_SIMULATION_NOT_CRYPTOGRAPHIC_SIGNATURE",
        "receipt_external_authority_none": receipt.get("external_authority") == "NONE",
        "all_artifact_refs_are_non_pii": all(not RAW_ID.search(item.artifact_ref) for item in items),
    }
    return {"manifest_hash": computed_hash, "checks": checks, "items": len(items)}


def artifact_status(ref: str) -> dict[str, Any]:
    path = ROOT / ref
    return {"ref": ref, "exists": path.exists(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None}


def analyze_blocker(gate_id: str, blocker: dict[str, Any], gate: Any) -> dict[str, Any]:
    profile = BLOCKER_PROFILE[gate_id]
    software = [artifact_status(ref) for ref in profile["software_refs"]]
    required_external = list(gate.required_evidence)
    return {
        "gate_id": gate_id,
        "blocker_id": blocker["blocker_id"],
        "status": blocker["status"],
        "severity": profile["severity"],
        "priority": profile["priority"],
        "owner_role": profile["owner_role"],
        "blocker_reason": blocker["reason"],
        "software_evidence": software,
        "software_evidence_available": all(item["exists"] for item in software),
        "required_external_evidence": required_external,
        "external_evidence_status": "NOT_VERIFIED",
        "external_action": profile["external_action"],
        "stop_condition": profile["stop_condition"],
        "reopen_required_before_new_submission": blocker["status"] == "BLOCKED",
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Controlled-Pilot Operations — Blocker Analysis",
        "",
        f"**Generated:** `{report['generated_at_utc']}`",
        f"**Operations state:** `{report['operations_state']}`",
        f"**Manifest hash:** `{report['manifest']['manifest_hash']}`",
        "",
        "> ผลการตรวจนี้เป็น software/evidence coordination analysis เท่านั้น ไม่ใช่ External Authorization, clinical validation หรือ production approval",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Total gates | {report['gate_summary']['total']} |",
        f"| Blocked gates analyzed | {report['gate_summary']['blocked']} |",
        f"| Open gates | {report['gate_summary']['open']} |",
        f"| Evidence-submitted gates | {report['gate_summary']['evidence_submitted']} |",
        f"| Manifest integrity checks passed | {sum(report['manifest']['checks'].values())}/{len(report['manifest']['checks'])} |",
        "",
        "## Blocker matrix",
        "",
        "| Gate | Severity | Owner | Current evidence | Missing external evidence | Next action |",
        "|---|---|---|---|---|---|",
    ]
    for item in sorted(report["blockers"], key=lambda row: (row["priority"], row["gate_id"])):
        available = "software refs available" if item["software_evidence_available"] else "software refs incomplete"
        missing = ", ".join(item["required_external_evidence"])
        lines.append(f"| {item['gate_id']} | {item['severity']} | `{item['owner_role']}` | {available} | {missing} | {item['external_action']} |")
    lines += [
        "",
        "## Cross-cutting stop conditions",
        "",
        "1. Do not promote the operations state while any blocker remains `BLOCKED` or external evidence remains `NOT_VERIFIED`.",
        "2. Do not start physical, HIS, IdP, WORM, hardware-key or clinical activity without the named owner, isolated scope, rollback/stop condition and recorded approval.",
        "3. A blocked gate must be explicitly reopened with a reason before new evidence is submitted.",
        "4. Local manifest SHA-256 and signed-style receipt are tamper-evident simulation controls only; they do not prove external custody or cryptographic signing.",
        "5. Clinical and production authorization remain false; runtime authority remains `NONE`.",
        "",
        "## References",
        "",
        "- `CONTROLLED_PILOT_OPERATIONS_GATE.md`",
        "- `CONTROLLED_PILOT_OPERATIONS_REVIEW_CHECKLIST.md`",
        "- `P2_004_EXTERNAL_REVIEW_COORDINATION_PACKAGE.md`",
        "- `RISK_REGISTER.md`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: analyze_controlled_pilot_blockers.py OPERATIONS_REPORT OUTPUT_JSON OUTPUT_MD")
    source = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    output_md = Path(sys.argv[3])
    payload = load_payload(source)
    gate_statuses = payload.get("gate_statuses", {})
    if gate_statuses != EXPECTED_GATE_STATUSES:
        raise ValueError("gate_statuses_do_not_match_current_registry")
    blockers = payload["decision"]["blockers"]
    blocker_by_gate = {item["gate_id"]: item for item in blockers}
    if tuple(sorted(blocker_by_gate)) != tuple(sorted(EXPECTED_BLOCKERS)):
        raise ValueError("seven_blocker_set_mismatch")
    package = default_pilot_package()
    manifest = validate_manifest(payload)
    blocker_analysis = [analyze_blocker(gate_id, blocker_by_gate[gate_id], package.gates[gate_id]) for gate_id in EXPECTED_BLOCKERS]
    report = {
        "suite": "controlled-pilot-blocker-analysis-v1",
        "generated_at_utc": payload["generated_at_utc"],
        "source_report": source.as_posix(),
        "operations_state": payload["decision"]["state"],
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "manifest": manifest,
        "gate_summary": {
            "total": len(gate_statuses),
            "blocked": sum(status == "BLOCKED" for status in gate_statuses.values()),
            "open": sum(status == "OPEN" for status in gate_statuses.values()),
            "evidence_submitted": sum(status == "EVIDENCE_SUBMITTED" for status in gate_statuses.values()),
        },
        "blockers": blocker_analysis,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps({"output_json": output_json.as_posix(), "output_md": output_md.as_posix(), "blocked": report["gate_summary"]["blocked"], "manifest_checks": report["manifest"]["checks"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
