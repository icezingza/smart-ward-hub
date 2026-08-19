from __future__ import annotations

from persistence_contract import PersistencePolicy, PersistencePolicyError, default_software_policy


def expect_error(label: str, builder) -> None:
    try:
        builder()
    except PersistencePolicyError:
        print(f"[Persistence] {label}: PASSED")
    else:
        raise AssertionError(f"expected PersistencePolicyError: {label}")


def run() -> None:
    registry_policy = default_software_policy("registry_snapshot")
    index_policy = default_software_policy("index_snapshot")
    assert registry_policy.validate() == registry_policy
    assert index_policy.policy_hash() == default_software_policy("index_snapshot").policy_hash()
    assert registry_policy.software_verify().approval_state == "SOFTWARE_VERIFIED"
    print("[Persistence] Default synthetic policies validate and hash deterministically: PASSED")

    expect_error(
        "owner and custodian must be distinct",
        lambda: PersistencePolicy(
            **{**registry_policy.canonical_payload(), "custodian_role": registry_policy.owner_role}
        ).validate(),
    )
    expect_error(
        "raw identity is rejected",
        lambda: PersistencePolicy(
            **{**registry_policy.canonical_payload(), "raw_identity_allowed": True}
        ).validate(),
    )
    expect_error(
        "clinical data is rejected",
        lambda: PersistencePolicy(
            **{**registry_policy.canonical_payload(), "clinical_data_allowed": True}
        ).validate(),
    )
    expect_error(
        "external approval cannot be self-declared",
        lambda: PersistencePolicy(
            **{**registry_policy.canonical_payload(), "approval_state": "EXTERNALLY_APPROVED"}
        ).validate(),
    )
    expect_error(
        "durable storage requires encryption",
        lambda: PersistencePolicy(
            **{
                **registry_policy.canonical_payload(),
                "storage_class": "local_encrypted",
                "retention_days": 30,
                "backup_required": True,
            }
        ).validate(),
    )
    expect_error(
        "ephemeral storage cannot claim retention",
        lambda: PersistencePolicy(
            **{**registry_policy.canonical_payload(), "retention_days": 30}
        ).validate(),
    )
    expect_error(
        "naive expiry timestamp is rejected",
        lambda: PersistencePolicy(
            **{**registry_policy.canonical_payload(), "expires_at": "2026-08-20T12:00:00"}
        ).validate(),
    )
    print("PERSISTENCE_CONTRACT_TESTS_PASSED")


if __name__ == "__main__":
    run()
