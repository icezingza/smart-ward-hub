from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from controlled_pilot_handoff import EXTERNAL_GATE_IDS, build_controlled_pilot_handoff
from external_validation_package import default_pilot_package
from p2_004_review_decision import RepeatedSampleProtocol, decide_review_status


BLOCKERS = {
    "GV-01": "clinical governance protocol and signed scope are not externally verified",
    "GV-03": "real HIS/Admission transcript and reconciliation are not externally verified",
    "GV-04": "real OIDC/mTLS handshake and key-rotation transcript are not externally verified",
    "GV-06": "Acer physical serial/power-loss/disk-full evidence is blocked; no COM port is enumerated",
    "GV-07": "independent external WORM receipt and trusted timestamp are not verified",
    "GV-08": "manufacturer provenance and hardware key-custody evidence are not verified",
    "GV-09": "staff training, manual fallback SOP and alarm-fatigue review are not externally verified",
}


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"object required: {path}")
    return payload


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: generate_p2_004_external_review_handoff.py OUTPUT_JSON PRIMARY_AGGREGATE_JSON READINESS_JSON")
    output_path = Path(sys.argv[1])
    aggregate_path = Path(sys.argv[2])
    readiness_path = Path(sys.argv[3])
    aggregate = load_json(aggregate_path)
    readiness = load_json(readiness_path)
    decision = decide_review_status(aggregate, RepeatedSampleProtocol())

    package = default_pilot_package()
    for gate_id, reason in BLOCKERS.items():
        package.block_gate(gate_id, reason)
    package_summary = package.readiness_summary()
    gate_statuses = {gate_id: gate.status for gate_id, gate in package.gates.items()}
    handoff = build_controlled_pilot_handoff(
        handoff_id="p2004-external-review-handoff-20260820",
        review_decision=decision,
        readiness_status=str(readiness.get("readiness", {}).get("status", "NOT_READY")),
        gate_statuses=gate_statuses,
        evidence_refs=[
            str(aggregate_path),
            str(readiness_path),
            "P2_004_REPEATED_SAMPLE_PROTOCOL.md",
            "P2_004_HARDENING_EVIDENCE.md",
        ],
        blockers=list(BLOCKERS.values()) + [
            "at least two compatible samples are required",
            "runtime semantic backend and access-control enforcement are not verified",
        ],
    )
    payload = {
        "suite": "p2-004-external-review-handoff-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "review_decision": decision,
        "readiness_report": readiness,
        "external_validation_summary": package_summary,
        "gate_statuses": gate_statuses,
        "handoff": handoff.as_dict(),
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "claim_boundary": "CONTROLLED_PROTOTYPE_SOFTWARE_EVIDENCE_ONLY",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "review_status": decision["status"], "pilot_gate_status": handoff.pilot_gate_status, "blocked_gates": sum(1 for status in gate_statuses.values() if status == "BLOCKED")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
