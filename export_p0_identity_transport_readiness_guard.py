"""Export local-only P0 OIDC/mTLS readiness evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from p0_identity_transport_readiness_guard import evaluate_identity_transport_readiness


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "evals/micro_rag/evidence/p0-identity-transport-readiness-local.json"
EXPORT_SCHEMA_VERSION = "p0-identity-transport-readiness-evidence-v1"


def export_evidence(output: Path = DEFAULT_OUTPUT) -> dict:
    report = evaluate_identity_transport_readiness()
    if not report["all_passed"]:
        raise RuntimeError("cannot export failed identity/transport readiness")
    evidence = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "evidence_type": "P0_IDENTITY_TRANSPORT_READINESS",
        "decision": report["decision"],
        "evidence_scope": report["mode"],
        "source_module": "p0_identity_transport_readiness_guard.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "checks": report["checks"],
        "all_passed": report["all_passed"],
        "oidc_result": report["oidc_result"],
        "mtls_result": report["mtls_result"],
        "live_evidence": report["live_evidence"],
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "authorization_boundary": report["authorization_boundary"],
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "external_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "external_gate_snapshot": {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0},
        "patient_data_used": False,
        "raw_frames_recorded": False,
        "hardware_evidence": "UNVERIFIED",
        "redaction_verified": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    evidence = export_evidence()
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    print(f"P0_IDENTITY_TRANSPORT_READINESS_EVIDENCE_EXPORTED={DEFAULT_OUTPUT}")
