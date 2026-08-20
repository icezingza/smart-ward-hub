from __future__ import annotations

import json
from pathlib import Path

from key_custody_contract import CustodyAttestation, KeyCustodyError, KeyCustodyRegistry
from p1_003_key_custody_readiness import KeyCustodyReadinessError, template, validate_key_custody_manifest

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "evals/micro_rag/evidence/p1-003-key-custody-readiness-template-20260820.json"
SCHEMA_PATH = ROOT / "evals/micro_rag/evidence/p1-003-key-custody-readiness-schema-v1.json"
FP = "a" * 64
ATTESTATION = CustodyAttestation("att-hardening-001", False, False, False)


def expect_manifest_rejection(payload: dict, fragment: str) -> None:
    try:
        validate_key_custody_manifest(payload, template_only=True)
    except KeyCustodyReadinessError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError("manifest mutation was accepted")


def expect_registry_error(action, expected: str) -> None:
    try:
        action()
    except KeyCustodyError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def test_readiness_template_and_mutations() -> None:
    assert validate_key_custody_manifest(template(), template_only=True)["valid"] is True
    payload = template()
    payload["unexpected"] = True
    expect_manifest_rejection(payload, "unknown fields")

    payload = template()
    payload["authorization_boundary"]["production_authorized"] = True
    expect_manifest_rejection(payload, "authorization boundary must remain locked")

    payload = template()
    payload["tracks"].pop("KT-004")
    expect_manifest_rejection(payload, "tracks must contain exactly")

    payload = template()
    payload["common_controls"]["private_key_storage"] = "LOCAL_DATABASE"
    expect_manifest_rejection(payload, "private_key_storage must remain external custody only")

    payload = template()
    payload["common_controls"]["stop_rule"] = "Send seed to custody@example.invalid"
    expect_manifest_rejection(payload, "must not contain raw identity/contact")

    assert json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["status"] == "KEY_CUSTODY_SOFTWARE_PREPARATION_READY"
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"].endswith("p1-003-key-custody-readiness-v1")
    print("[P1-003] Readiness template and adversarial manifest mutations: PASSED")


def test_registry_hardening_matrix() -> None:
    registry = KeyCustodyRegistry(require_hardware_attestation=True, allow_software_fixture=False)
    record = registry.register_public_key(
        device_id="device-hardening-1", key_id="key-hardening-1", algorithm="Ed25519", public_key_fingerprint=FP
    )
    record.status = "ACTIVE"
    assert registry.snapshot()[0]["status"] == "PROVISIONING"
    print("[P1-003] Returned registry record cannot mutate internal state: PASSED")

    expect_registry_error(
        lambda: registry.activate(record.key_id, approver_ids=None, attestation=ATTESTATION),
        "dual_control_approval_required",
    )
    expect_registry_error(
        lambda: registry.revoke(record.key_id, reason=None),
        "revocation_reason_required",
    )
    expect_registry_error(
        lambda: registry.mark_lost(record.key_id, incident_id=None),
        "lost_device_incident_required",
    )
    print("[P1-003] None/type confusion inputs fail closed: PASSED")

    expect_registry_error(
        lambda: registry.activate(record.key_id, approver_ids=["one", "one"], attestation=ATTESTATION),
        "dual_control_approval_required",
    )
    expect_registry_error(
        lambda: registry.activate(record.key_id, approver_ids=["one", "two"], attestation=ATTESTATION),
        "hardware_attestation_required",
    )
    print("[P1-003] Duplicate approvers and missing hardware attestation fail closed: PASSED")

    fixture = KeyCustodyRegistry(require_hardware_attestation=True, allow_software_fixture=True)
    old = fixture.register_public_key(device_id="device-hardening-2", key_id="old", algorithm="Ed25519", public_key_fingerprint="b" * 64)
    fixture.activate(old.key_id, approver_ids=["one", "two"], attestation=ATTESTATION)
    new = fixture.register_public_key(device_id="device-hardening-2", key_id="new", algorithm="Ed25519", public_key_fingerprint="c" * 64, previous_key_id="old")
    fixture.activate(new.key_id, approver_ids=["one", "two"], attestation=ATTESTATION)
    fixture.complete_rotation(new_key_id="new", old_key_id="old")
    expect_registry_error(lambda: fixture.complete_rotation(new_key_id="new", old_key_id="old"), "old_key_not_rotatable")
    fixture.revoke("new", reason="hardening test")
    expect_registry_error(lambda: fixture.suspend("new"), "terminal_credential_cannot_suspend")
    print("[P1-003] Rotation replay and terminal credential transitions fail closed: PASSED")

    serialized = json.dumps(fixture.snapshot(), ensure_ascii=True)
    assert "private_key_material" not in serialized.lower()
    assert "private_key_value" not in serialized.lower()
    assert "seed_material" not in serialized.lower()
    print("[P1-003] Snapshot excludes private-key and seed material: PASSED")


if __name__ == "__main__":
    test_readiness_template_and_mutations()
    test_registry_hardening_matrix()
    print("P1_003_KEY_CUSTODY_HARDENING_TESTS_PASSED")
