from __future__ import annotations

import tempfile
from pathlib import Path

from controlled_pilot_operations import (
    BlockerRecord,
    ControlledPilotOperationsError,
    EvidenceManifest,
    EvidenceManifestItem,
    build_manifest_item,
    evaluate_operational_gate,
)


def gates(status: str = "OPEN"):
    return {f"GV-{index:02d}": status for index in range(1, 11)}


def build_manifest(directory: Path) -> EvidenceManifest:
    artifact = directory / "artifact.md"
    artifact.write_text("synthetic software evidence\n", encoding="utf-8")
    item = build_manifest_item(
        evidence_id="evidence-p2004-001",
        gate_id="GV-10",
        artifact_path=artifact,
        evidence_class="SOFTWARE_VERIFIED",
        collected_at_utc="2026-08-20T00:00:00Z",
        prepared_by_role="evidence-preparer",
        chain_of_custody_ref="chain-p2004-001",
    )
    return EvidenceManifest(
        manifest_version="controlled-pilot-manifest-v1",
        manifest_id="manifest-p2004-001",
        generated_at_utc="2026-08-20T00:00:00Z",
        previous_manifest_hash=None,
        items=(item,),
        claim_boundary="CONTROLLED_PROTOTYPE_SOFTWARE_EVIDENCE_ONLY",
    ).validate()


def run() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        manifest = build_manifest(Path(temporary))
        first_hash = manifest.manifest_hash()
        assert first_hash == manifest.manifest_hash()
        receipt = manifest.simulated_detached_receipt("review-key-simulation")
        assert receipt["receipt_type"] == "SIGNED_STYLE_SIMULATION_NOT_CRYPTOGRAPHIC_SIGNATURE"
        assert receipt["external_authority"] == "NONE"
        assert receipt["manifest_hash"] == first_hash
        print("[Operations] Deterministic manifest and non-cryptographic receipt simulation: PASSED")

        blocker = BlockerRecord(
            blocker_id="BLK-GV06",
            gate_id="GV-06",
            reason="physical Acer serial fixture is not available",
            recorded_at_utc="2026-08-20T00:00:00Z",
        ).validate()
        reopened = blocker.reopen("fixture request opened for non-production bench", "2026-08-20T01:00:00Z")
        assert reopened.status == "OPEN"
        assert reopened.reopened_at_utc == "2026-08-20T01:00:00Z"
        print("[Operations] Blocked gate requires explicit reopen reason and timestamp: PASSED")

        blocked = evaluate_operational_gate(
            gate_statuses={**gates("OPEN"), "GV-06": "BLOCKED"},
            readiness_status="NOT_READY",
            review_decision_status="BLOCKED_INCOMPLETE_EVIDENCE",
            manifest=manifest,
            blockers=(blocker,),
        )
        assert blocked.state == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
        assert blocked.clinical_validation_authorized is False
        assert blocked.production_authorized is False
        assert blocked.runtime_authority == "NONE"
        print("[Operations] Blocked readiness cannot enter pilot: PASSED")

        review_ready = evaluate_operational_gate(
            gate_statuses=gates("OPEN"),
            readiness_status="READY_FOR_EXTERNAL_GOVERNANCE_REVIEW",
            review_decision_status="ACCEPTED_FOR_EXTERNAL_REVIEW",
            manifest=manifest,
            blockers=(),
        )
        assert review_ready.state == "READY_FOR_EXTERNAL_REVIEW"
        assert review_ready.clinical_validation_authorized is False
        assert review_ready.production_authorized is False
        print("[Operations] Local readiness stops at external review boundary: PASSED")

        try:
            bad_item = EvidenceManifestItem(
                evidence_id="evidence-p2004-002",
                gate_id="GV-10",
                artifact_ref="patient-HN-2026-01.txt",
                artifact_sha256="0" * 64,
                evidence_class="SOFTWARE_VERIFIED",
                collected_at_utc="2026-08-20T00:00:00Z",
                prepared_by_role="evidence-preparer",
                redaction_status="PASS",
                chain_of_custody_ref="chain-p2004-002",
            )
            bad_item.validate()
        except ControlledPilotOperationsError:
            print("[Operations] Raw identity artifact reference is rejected: PASSED")
        else:
            raise AssertionError("raw identity artifact reference was accepted")

        try:
            manifest.simulated_detached_receipt("bad key id with spaces")
        except ControlledPilotOperationsError:
            print("[Operations] Invalid receipt key ID is rejected: PASSED")
        else:
            raise AssertionError("invalid receipt key ID was accepted")

    print("CONTROLLED_PILOT_OPERATIONS_TESTS_PASSED")


if __name__ == "__main__":
    run()
