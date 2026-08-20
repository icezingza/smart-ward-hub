from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "evals/micro_rag/evidence/wave-e-evidence-schema-validation-20260820.json"
TESTS = [
    "test_wave_e_evidence.py",
    "test_external_authorization_api_simulator.py",
    "test_external_validation_gate_matrix.py",
    "test_gv10_evidence.py",
    "test_wave0_governance.py",
    "test_production_readiness_audit.py",
]
HASHED_FILES = [
    "external_authorization_api_wave_e_evidence.py",
    "test_wave_e_evidence.py",
    "evals/micro_rag/evidence/wave-e-evidence-schema-v1.json",
    "EXTERNAL_AUTHORIZATION_API_WAVE_E_EXTERNAL_VALIDATION_DOSSIER.md",
    "EXTERNAL_AUTHORIZATION_API_SIMULATION_CONTRACT.md",
    "EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    results: list[dict[str, object]] = []
    overall_exit = 0
    for test in TESTS:
        completed = subprocess.run(
            [sys.executable, test],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        result = {
            "test": test,
            "exit_code": completed.returncode,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
        results.append(result)
        overall_exit = overall_exit or completed.returncode

    git_status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    payload = {
        "schema_version": "wave-e-validation-run-v1",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "prepared_by_role": "integration_owner",
        "independent_verification_required": True,
        "environment": "LOCAL_SOFTWARE_SIMULATION",
        "repository": "icezingza/smart-ward-hub",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip(),
        "working_tree_clean": not bool(git_status.strip()),
        "working_tree_status_sha256": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
        "dossier_state": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT",
        "external_execution": "NOT_STARTED",
        "evidence_class": "SOFTWARE_VERIFIED/SIMULATION_ONLY",
        "test_results": results,
        "hashed_files": {path: sha256(ROOT / path) for path in HASHED_FILES},
        "redaction": "PASS",
        "raw_identity_present": False,
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "claim_boundary": "EXTERNAL_UNVERIFIED_PENDING_REVIEW",
        "external_endpoint_contacted": False,
        "patient_data_used": False,
        "production_traffic_used": False,
        "overall_status": "PASS" if overall_exit == 0 else "FAIL",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WAVE_E_VALIDATION_EVIDENCE_WRITTEN {OUTPUT}")
    print(f"WAVE_E_VALIDATION_OVERALL_STATUS {payload['overall_status']}")
    return overall_exit


if __name__ == "__main__":
    raise SystemExit(main())
