from __future__ import annotations

from key_custody_contract import CustodyAttestation, KeyCustodyError, KeyCustodyRegistry


ATTESTATION = CustodyAttestation("att-negative-matrix-001", False, False, False)


def expect_error(action, expected: str) -> None:
    try:
        action()
    except KeyCustodyError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def run() -> None:
    registry = KeyCustodyRegistry(require_hardware_attestation=True, allow_software_fixture=False)
    expect_error(
        lambda: registry.register_public_key(
            device_id="   ", key_id="key-blank-device", algorithm="Ed25519", public_key_fingerprint="a" * 64
        ),
        "invalid_public_key_registration",
    )
    expect_error(
        lambda: registry.register_public_key(
            device_id="device-1", key_id="key-bad-fingerprint", algorithm="Ed25519", public_key_fingerprint="not-a-fingerprint"
        ),
        "invalid_public_key_registration",
    )
    print("[P1-003] Blank identifier and malformed fingerprint rejection: PASSED")

    first = registry.register_public_key(
        device_id="device-1", key_id="key-duplicate", algorithm="Ed25519", public_key_fingerprint="a" * 64
    )
    expect_error(
        lambda: registry.register_public_key(
            device_id="device-2", key_id=first.key_id, algorithm="Ed25519", public_key_fingerprint="b" * 64
        ),
        "duplicate_key_id",
    )
    expect_error(
        lambda: registry.register_public_key(
            device_id="device-1",
            key_id="key-private-material",
            algorithm="Ed25519",
            public_key_fingerprint="b" * 64,
            private_key_material="never-store-this",
        ),
        "private_key_material_must_never_enter_registry",
    )
    print("[P1-003] Duplicate key and private-key material rejection: PASSED")

    expect_error(
        lambda: registry.activate(first.key_id, approver_ids=["a", "b"], attestation=CustodyAttestation("", False, False, False)),
        "attestation_evidence_id_required",
    )
    expect_error(
        lambda: registry.activate(first.key_id, approver_ids=["a", "b"], attestation={}),
        "attestation_evidence_id_required",
    )
    expect_error(
        lambda: registry.activate(first.key_id, approver_ids=["a", "b"], attestation=ATTESTATION),
        "hardware_attestation_required",
    )
    print("[P1-003] Evidence-ID validation and hardware-attestation fail-closed mode: PASSED")

    fixture = KeyCustodyRegistry(require_hardware_attestation=True, allow_software_fixture=True)
    old = fixture.register_public_key(
        device_id="device-rotation-a", key_id="old", algorithm="Ed25519", public_key_fingerprint="c" * 64
    )
    fixture.activate(old.key_id, approver_ids=["a", "a", "b"], attestation=ATTESTATION)
    assert fixture.snapshot()[0]["attestation_evidence_id"] == ATTESTATION.evidence_id
    new = fixture.register_public_key(
        device_id="device-rotation-b", key_id="new", algorithm="Ed25519", public_key_fingerprint="d" * 64, previous_key_id="old"
    )
    fixture.activate(new.key_id, approver_ids=["a", "b"], attestation=ATTESTATION)
    expect_error(
        lambda: fixture.complete_rotation(new_key_id="new", old_key_id="old"),
        "rotation_requires_active_same_device_key",
    )
    print("[P1-003] Duplicate-approver collapse, evidence persistence and cross-device rotation rejection: PASSED")

    expect_error(lambda: fixture.revoke("new", reason="   "), "revocation_reason_required")
    expect_error(lambda: fixture.mark_lost("new", incident_id="   "), "lost_device_incident_required")
    print("[P1-003] Blank revocation reason and lost-device incident rejection: PASSED")
    print("KEY_CUSTODY_NEGATIVE_TESTS_PASSED")


if __name__ == "__main__":
    run()
