from __future__ import annotations

from pathlib import Path

from analyze_controlled_pilot_blockers import (
    EXPECTED_BLOCKERS,
    EXPECTED_GATE_STATUSES,
    analyze_blocker,
    default_pilot_package,
    load_payload,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "evals/micro_rag/evidence/controlled-pilot-operations-report-20260820.json"


def main() -> int:
    payload = load_payload(REPORT)
    assert payload["gate_statuses"] == EXPECTED_GATE_STATUSES
    assert payload["decision"]["clinical_validation_authorized"] is False
    assert payload["decision"]["production_authorized"] is False
    assert payload["decision"]["runtime_authority"] == "NONE"

    manifest = validate_manifest(payload)
    assert all(manifest["checks"].values())
    assert manifest["items"] == 4

    package = default_pilot_package()
    blocker_by_gate = {item["gate_id"]: item for item in payload["decision"]["blockers"]}
    assert tuple(sorted(blocker_by_gate)) == tuple(sorted(EXPECTED_BLOCKERS))
    rows = [analyze_blocker(gate_id, blocker_by_gate[gate_id], package.gates[gate_id]) for gate_id in EXPECTED_BLOCKERS]
    assert len(rows) == 7
    assert all(row["status"] == "BLOCKED" for row in rows)
    assert all(row["external_evidence_status"] == "NOT_VERIFIED" for row in rows)
    assert all(row["reopen_required_before_new_submission"] for row in rows)
    print("CONTROLLED_PILOT_BLOCKER_ANALYSIS_TESTS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
