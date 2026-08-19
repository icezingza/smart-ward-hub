from __future__ import annotations

import json

from key_custody_contract import CustodyAttestation, KeyCustodyError, KeyCustodyRegistry


FP_OLD = "a" * 64
FP_NEW = "b" * 64


def run() -> None:
    registry = KeyCustodyRegistry(require_hardware_attestation=True, allow_software_fixture=True)
    old = registry.register_public_key(
        device_id="MAC-A1:B2:C3:D4:E5:F6",
        key_id="key-custody-v1",
        algorithm="Ed25519",
        public_key_fingerprint=FP_OLD,
    )
    assert old.status == "PROVISIONING"
    try:
        registry.activate(
            old.key_id,
            approver_ids=["one"],
            attestation=CustodyAttestation("att-1", False, False, False),
        )
    except KeyCustodyError as exc:
        assert str(exc) == "dual_control_approval_required"
    else:
        raise AssertionError("single approver activated a credential")
    print("[P1-003] Dual-control activation gate: PASSED")

    activated_old = registry.activate(
        old.key_id,
        approver_ids=["operator-a", "operator-b"],
        attestation=CustodyAttestation("att-software-1", False, False, False),
    )
    assert activated_old.status == "ACTIVE"
    assert activated_old.evidence_status == "UNVERIFIED"
    print("[P1-003] Software fixture activation remains explicitly UNVERIFIED: PASSED")

    new = registry.register_public_key(
        device_id=old.device_id,
        key_id="key-custody-v2",
        algorithm="Ed25519",
        public_key_fingerprint=FP_NEW,
        previous_key_id=old.key_id,
    )
    activated_new = registry.activate(
        new.key_id,
        approver_ids=["operator-a", "operator-b"],
        attestation=CustodyAttestation("att-hardware-1", True, True, True),
    )
    assert activated_new.evidence_status == "VERIFIED"
    _, suspended_old = registry.complete_rotation(new_key_id=new.key_id, old_key_id=old.key_id)
    assert suspended_old.status == "SUSPENDED"
    print("[P1-003] Key rotation links new key and suspends old key: PASSED")

    revoked = registry.revoke(new.key_id, reason="device replacement")
    assert revoked.status == "REVOKED"
    try:
        registry.activate(new.key_id, approver_ids=["operator-a", "operator-b"], attestation=CustodyAttestation("att-2", True, True, True))
    except KeyCustodyError as exc:
        assert str(exc) == "activation_not_allowed_from_REVOKED"
    else:
        raise AssertionError("revoked credential was reactivated")
    print("[P1-003] Revoked credential is terminal and cannot reactivate: PASSED")

    lost = registry.register_public_key(
        device_id="MAC-LOST-DEVICE",
        key_id="key-lost-v1",
        algorithm="Ed25519",
        public_key_fingerprint="c" * 64,
    )
    registry.activate(lost.key_id, approver_ids=["operator-a", "operator-b"], attestation=CustodyAttestation("att-3", False, False, False))
    marked_lost = registry.mark_lost(lost.key_id, incident_id="INC-LOST-001")
    assert marked_lost.status == "LOST"
    assert marked_lost.revoked_at_utc is not None
    print("[P1-003] Lost-device incident transitions credential to terminal LOST/revoked state: PASSED")

    snapshot = registry.snapshot()
    serialized = json.dumps(snapshot, ensure_ascii=True)
    assert "private_key_material" not in serialized
    assert all("private_key_value" not in record for record in snapshot)
    print("[P1-003] Registry snapshot contains no private-key material: PASSED")
    print("KEY_CUSTODY_CONTRACT_TESTS_PASSED")


if __name__ == "__main__":
    run()
