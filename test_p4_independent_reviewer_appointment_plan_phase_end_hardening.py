"""Phase-end hardening gate for the P4 independent-reviewer appointment plan."""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

from export_p4_independent_reviewer_appointment_plan import export_appointment_plan
from p4_independent_reviewer_appointment_plan import evaluate_appointment_plan


ROOT = Path(__file__).resolve().parent
FOCUSED = ROOT / "test_p4_independent_reviewer_appointment_plan.py"
TARGETS = (
    ROOT / "p4_independent_reviewer_appointment_plan.py",
    ROOT / "export_p4_independent_reviewer_appointment_plan.py",
)
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "socket",
    "urllib",
    "serial",
    "bleak",
    "paho",
    "websockets",
    "google",
    "azure",
    "boto3",
    "celery",
    "apscheduler",
    "schedule",
    "subprocess",
}
PRIVATE_KEY_MARKERS = tuple(
    "-----BEGIN " + label + "-----"
    for label in (
        "PRIVATE" + " " + "KEY",
        "RSA" + " " + "PRIVATE" + " " + "KEY",
        "EC" + " " + "PRIVATE" + " " + "KEY",
        "OPENSSH" + " " + "PRIVATE" + " " + "KEY",
    )
)


def run() -> None:
    env = os.environ.copy()
    env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
    completed = subprocess.run(
        [sys.executable, str(FOCUSED)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, f"focused appointment plan suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[P4 Appointment Gate] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[P4 Appointment Gate] no network/provider/transport/scheduler imports: PASSED")

    report = evaluate_appointment_plan()
    assert report["decision"] == "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_READY"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    plan = report["plan"]
    assert plan["plan_status"] == "APPOINTMENT_PLAN_TEMPLATE"
    assert plan["appointment_packet_id"] == "PENDING_EXTERNAL_APPOINTMENT"
    assert plan["reviewer_appointment"] == "PENDING_EXTERNAL_APPOINTMENT"
    assert plan["reviewer_organization"] == "PENDING_EXTERNAL_APPOINTMENT"
    assert plan["conflict_declaration"] == "PENDING_EXTERNAL_APPOINTMENT"
    assert plan["appointment_decision"] == "NOT_ISSUED"
    assert len(plan["required_appointment_records"]) == 9
    assert len(plan["required_external_inputs"]) == 8
    assert len(plan["review_scope_gate_ids"]) == 10
    assert len(plan["review_scope_test_ids"]) == 12
    assert plan["role_separation"]["stop_and_rollback_must_differ"] is True
    assert plan["authorization_boundary"]["external_authority"] == "NONE"
    assert plan["authorization_boundary"]["clinical_validation_authorized"] is False
    assert plan["authorization_boundary"]["production_authorized"] is False
    assert plan["authorization_boundary"]["runtime_authority"] == "NONE"
    assert plan["independent_review_started"] is False
    assert plan["submission_allowed"] is False
    assert report["ready_for_external_appointment"] is True
    assert report["ready_for_external_review"] is False
    assert report["appointment_confirmed"] is False
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["production_ready"] is False
    print("[P4 Appointment Gate] template, scope, role separation and boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "appointment-plan.json"
        exported = export_appointment_plan(output=output)
        assert exported["decision"] == "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_READY"
        assert exported["redaction_verified"] is True
        assert exported["submission_allowed"] is False
        assert exported["appointment_confirmed"] is False
        assert json.loads(output.read_text(encoding="utf-8")) == exported
    print("[P4 Appointment Gate] exporter round-trip and redaction: PASSED")

    serialized = json.dumps(report, ensure_ascii=True, sort_keys=True)
    assert re.search(r"\b(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", serialized, re.IGNORECASE) is None
    for marker in ("patient_id", "patient_token", "private key", "bearer ", "password", "api_key", "@"):
        assert marker.lower() not in serialized.lower()
    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"appointment_decision": "NOT_ISSUED"' in source
    assert '"ready_for_external_review": False' in source
    assert '"submission_allowed": False' in source
    assert '"appointment_confirmed": False' in source
    assert '"production_ready": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[P4 Appointment Gate] redaction, no-self-appointment and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P4 Appointment Gate] git diff --check: PASSED")
    print("P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
