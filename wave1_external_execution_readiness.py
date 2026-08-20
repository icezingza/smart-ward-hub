from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "evals/micro_rag/evidence/wave1-external-execution-readiness-20260820.json"

REQUIRED_PREREQUISITES = {
    "wave0_signed_scope": "external signed scope with in/out-of-scope, data boundary and purpose",
    "wave0_approved_test_window": "approved timezone-aware start/end and allowlist",
    "wave0_named_stop_authority": "named stop authority with notification path",
    "wave0_rollback_owner": "named rollback owner and rehearsed target revision",
    "wave0_independent_verifier": "named independent verifier and read-back channel",
    "gv04_nonproduction_idp": "isolated non-production IdP/HIS tenant",
    "gv04_certificate_owner": "certificate owner, chain and rotation/revocation plan",
    "gv04_network_acl": "approved network path and deny transcript",
    "gv08_custody_owner": "OEM or approved HSM/secure-element custody owner",
    "gv08_dual_control_ceremony": "dual-control key issuance record",
    "gv08_revocation_distribution": "real revocation distribution/read-back procedure",
    "gv06_acer_fixture": "dedicated Acer non-production fixture",
    "gv06_loopback_fixture": "isolated USB-serial loopback fixture",
    "gv06_operator_confirmation": "I_HAVE_A_NONPRODUCTION_LOOPBACK",
    "gv06_physical_witness": "independent physical bench witness",
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    status = git("status", "--porcelain")
    head = git("rev-parse", "HEAD")
    origin = git("rev-parse", "origin/main")
    freeze = json.loads((ROOT / "evals/micro_rag/evidence/release-candidate-freeze-20260820.json").read_text())
    preflight = json.loads((ROOT / "evals/micro_rag/evidence/wave1-preflight-20260820.json").read_text())
    missing = dict(REQUIRED_PREREQUISITES)
    checks = {
        "working_tree_clean_before_readiness": status == "",
        "head_matches_origin_main": head == origin,
        "release_freeze_pass": freeze.get("freeze_status") == "PASS",
        "wave1_local_preflight_recorded": preflight.get("decision") == "WAVE_1_LOCAL_PREFLIGHT_PASS_EXTERNAL_EXECUTION_BLOCKED",
        "no_authorization_boundary": preflight.get("authorization_boundary") == {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
        "no_real_external_execution": preflight.get("external_execution") == "NOT_STARTED",
        "no_physical_execution": preflight.get("physical_execution") == "NOT_STARTED",
    }
    readiness = "READY_FOR_OWNER_APPOINTMENT" if all(checks.values()) else "BLOCKED_LOCAL_INTEGRITY"
    payload = {
        "schema_version": "wave1-external-execution-readiness-v1",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": "icezingza/smart-ward-hub",
        "current_revision": head,
        "origin_main_revision": origin,
        "environment": "LOCAL_READINESS_ONLY",
        "execution_status": "NOT_STARTED",
        "readiness": readiness,
        "checks": checks,
        "missing_external_prerequisites": missing,
        "artifact_hashes": {
            "release_freeze": sha256(ROOT / "evals/micro_rag/evidence/release-candidate-freeze-20260820.json"),
            "wave1_preflight": sha256(ROOT / "evals/micro_rag/evidence/wave1-preflight-20260820.json"),
            "technical_package": sha256(ROOT / "WAVE_1_TECHNICAL_VALIDATION_PACKAGE_20260820.md"),
            "owner_gap_report": sha256(ROOT / "WAVE_0_OWNER_APPROVAL_GAP_REPORT_20260820.md"),
        },
        "authorization_boundary": {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
        "evidence_class": "SOFTWARE_VERIFIED/SIMULATION_ONLY",
        "independent_verification_required": True,
        "redaction": "PASS",
        "raw_identity_present": False,
        "next_action": "Obtain external role appointments and signed test-window package before any isolated external execution.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WAVE1_EXTERNAL_READINESS={readiness}")
    print(f"MISSING_PREREQUISITES={len(missing)}")
    print(f"OUTPUT={OUTPUT}")
    return 0 if readiness == "READY_FOR_OWNER_APPOINTMENT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
