from __future__ import annotations

from pathlib import Path
import tempfile

from serial_bench_evidence_contract import (
    BenchEvidenceValidationError,
    TEST_IDS,
    finalize_bench_evidence,
    validate_bench_evidence,
)
from serial_bench_runner import BenchConfig, PHYSICAL_CONFIRMATION, run as run_bench


def expect_error(callback) -> None:
    try:
        callback()
    except BenchEvidenceValidationError:
        return
    raise AssertionError("expected BenchEvidenceValidationError")


def test_runner_evidence_is_contract_valid():
    with tempfile.TemporaryDirectory() as temp_dir:
        evidence = run_bench(
            BenchConfig(
                port=None,
                baudrate=115200,
                timeout_seconds=1.0,
                max_payload=4096,
                output=Path(temp_dir) / "dry.json",
                dry_run=True,
                confirm_physical=None,
            )
        )
    result = validate_bench_evidence(evidence)
    assert result["valid"] is True
    assert evidence["evidence_contract"] == "serial-bench-evidence-v1"
    assert evidence["tests"]["S-004"] == "PASS"
    assert set(evidence["tests"]) == set(TEST_IDS)
    assert evidence["physical_hardware_validation"] == "PENDING"
    print("[Bench Evidence] Dry-run output binds contract/hash and remains non-physical: PASSED")


def test_rejects_pii_unknown_coverage_and_hash_tamper():
    base = {
        "run_id": "serial-bench-20260821T100000Z",
        "mode": "dry_run",
        "status": "DRY_RUN_ONLY",
        "tests": {test_id: "NOT_RUN" for test_id in TEST_IDS},
        "test_scope": [],
        "physical_hardware_validation": "PENDING",
        "production_network_validation": "PENDING",
        "patient_data_used": False,
        "private_key_used": False,
        "raw_frames_recorded": False,
        "physical_confirmation_verified": False,
    }
    valid = finalize_bench_evidence(base)
    validate_bench_evidence(valid)

    pii = dict(valid)
    pii["notes"] = "patient_token=should-not-enter"
    pii["evidence_payload_sha256"] = "0" * 64
    expect_error(lambda: validate_bench_evidence(pii))

    missing = dict(valid)
    missing["tests"] = dict(valid["tests"])
    missing["tests"].pop("S-015")
    missing["evidence_payload_sha256"] = "0" * 64
    expect_error(lambda: validate_bench_evidence(missing))

    tampered = dict(valid)
    tampered["status"] = "PASSED"
    expect_error(lambda: validate_bench_evidence(tampered))
    print("[Bench Evidence] PII, coverage, dry-run claim and hash tamper rejection: PASSED")


def test_physical_pass_requires_confirmation_and_hardware_state():
    base = {
        "run_id": "serial-bench-20260821T100001Z",
        "mode": "physical_loopback",
        "status": "PASSED",
        "tests": {test_id: "NOT_RUN" for test_id in TEST_IDS},
        "test_scope": ["S-003"],
        "physical_hardware_validation": "VERIFIED",
        "production_network_validation": "PENDING",
        "patient_data_used": False,
        "private_key_used": False,
        "raw_frames_recorded": False,
        "physical_confirmation_verified": False,
    }
    expect_error(lambda: validate_bench_evidence(finalize_bench_evidence(base)))
    base["physical_confirmation_verified"] = True
    base["tests"]["S-003"] = "PASS"
    valid = finalize_bench_evidence(base)
    assert validate_bench_evidence(valid)["status"] == "PASSED"
    assert PHYSICAL_CONFIRMATION == "I_HAVE_A_NONPRODUCTION_LOOPBACK"
    print("[Bench Evidence] Physical PASS requires explicit confirmation and S-003 binding: PASSED")


def run() -> None:
    test_runner_evidence_is_contract_valid()
    test_rejects_pii_unknown_coverage_and_hash_tamper()
    test_physical_pass_requires_confirmation_and_hardware_state()
    print("SERIAL_BENCH_EVIDENCE_CONTRACT_TESTS_PASSED")


if __name__ == "__main__":
    run()
