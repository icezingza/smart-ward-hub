from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from controlled_pilot_operations import BlockerRecord, EvidenceManifest, build_manifest_item, evaluate_operational_gate


GATE_STATUSES = {
    "GV-01": "BLOCKED",
    "GV-02": "OPEN",
    "GV-03": "BLOCKED",
    "GV-04": "BLOCKED",
    "GV-05": "OPEN",
    "GV-06": "BLOCKED",
    "GV-07": "BLOCKED",
    "GV-08": "BLOCKED",
    "GV-09": "BLOCKED",
    "GV-10": "OPEN",
}

BLOCKERS = (
    ("BLK-GV01", "GV-01", "clinical governance protocol and signed scope are not externally verified"),
    ("BLK-GV03", "GV-03", "real HIS/Admission transcript and reconciliation are not externally verified"),
    ("BLK-GV04", "GV-04", "real OIDC/mTLS handshake and key-rotation transcript are not externally verified"),
    ("BLK-GV06", "GV-06", "Acer physical serial fixture and COM-port evidence are not available"),
    ("BLK-GV07", "GV-07", "independent WORM receipt and trusted timestamp are not externally verified"),
    ("BLK-GV08", "GV-08", "manufacturer provenance and hardware key custody are not externally verified"),
    ("BLK-GV09", "GV-09", "staff training and manual fallback review are not externally verified"),
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate_controlled_pilot_operations_report.py OUTPUT_JSON")
    root = Path(__file__).resolve().parent
    output = Path(sys.argv[1])
    collected_at = "2026-08-20T00:00:00Z"
    manifest_items = (
        build_manifest_item(
            evidence_id="ops-p2004-001",
            gate_id="GV-10",
            artifact_path=root / "P2_004_HARDENING_EVIDENCE.md",
            evidence_class="SOFTWARE_VERIFIED",
            collected_at_utc=collected_at,
            prepared_by_role="evidence-preparer",
            chain_of_custody_ref="chain-p2004-ops-001",
        ),
        build_manifest_item(
            evidence_id="ops-p2004-002",
            gate_id="GV-10",
            artifact_path=root / "P2_004_REPEATED_SAMPLE_PROTOCOL.md",
            evidence_class="SOFTWARE_VERIFIED",
            collected_at_utc=collected_at,
            prepared_by_role="evidence-preparer",
            chain_of_custody_ref="chain-p2004-ops-002",
        ),
        build_manifest_item(
            evidence_id="ops-p2004-003",
            gate_id="GV-02",
            artifact_path=root / "P2_004_PERSISTENCE_OWNERSHIP_CONTRACT.md",
            evidence_class="SOFTWARE_VERIFIED",
            collected_at_utc=collected_at,
            prepared_by_role="evidence-preparer",
            chain_of_custody_ref="chain-p2004-ops-003",
        ),
        build_manifest_item(
            evidence_id="ops-p2004-004",
            gate_id="GV-06",
            artifact_path=root / "ACER_BENCH_READONLY_INVENTORY.md",
            evidence_class="BLOCKER_RECORD",
            collected_at_utc=collected_at,
            prepared_by_role="evidence-preparer",
            chain_of_custody_ref="chain-p2004-ops-004",
        ),
    )
    manifest = EvidenceManifest(
        manifest_version="controlled-pilot-manifest-v1",
        manifest_id="manifest-controlled-pilot-operations-20260820",
        generated_at_utc=collected_at,
        previous_manifest_hash=None,
        items=manifest_items,
        claim_boundary="CONTROLLED_PROTOTYPE_SOFTWARE_EVIDENCE_ONLY",
    ).validate()
    blockers = tuple(
        BlockerRecord(
            blocker_id=blocker_id,
            gate_id=gate_id,
            reason=reason,
            recorded_at_utc=collected_at,
        ).validate()
        for blocker_id, gate_id, reason in BLOCKERS
    )
    decision = evaluate_operational_gate(
        gate_statuses=GATE_STATUSES,
        readiness_status="NOT_READY",
        review_decision_status="BLOCKED_INCOMPLETE_EVIDENCE",
        manifest=manifest,
        blockers=blockers,
    )
    payload = {
        "suite": "controlled-pilot-operations-report-v1",
        "generated_at_utc": collected_at,
        "manifest": manifest.canonical_payload(),
        "manifest_hash": manifest.manifest_hash(),
        "simulated_detached_receipt": manifest.simulated_detached_receipt("review-key-simulation"),
        "gate_statuses": GATE_STATUSES,
        "decision": decision.as_dict(),
        "reviewer_boundary": {
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "external_authority": "NONE",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "manifest_hash": manifest.manifest_hash(), "decision": decision.state, "blockers": len(blockers)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
