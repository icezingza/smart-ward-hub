from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric import rsa

from edge_runtime import EdgeTelemetryStore
from forensic_vault import GENESIS_HASH, RSAPSSForensicSigner, canonical_payload, compute_block_hash


def run() -> None:
    store = EdgeTelemetryStore(max_samples=20, state_path=None)
    now = datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc)
    for sequence, age_seconds in enumerate((601, 600, 300, 0), start=1):
        received_at = (now - timedelta(seconds=age_seconds)).replace(tzinfo=None)
        result = store.append(
            "forensic-test-device",
            {"sequence": sequence, "received_at": received_at, "heart_rate": 72.0},
            sequence,
        )
        assert result.accepted is True
    window = store.snapshot_window("forensic-test-device", window_seconds=600, now=now)
    assert [sample["sequence"] for sample in window] == [2, 3, 4]
    print("[Forensic Vault] Exact 600-second RAM window: PASSED")

    payload = canonical_payload({"device_id": "forensic-test-device", "samples": window})
    first_hash = compute_block_hash(GENESIS_HASH, payload)
    second_hash = compute_block_hash(first_hash, canonical_payload({"event": "second"}))
    assert first_hash != second_hash
    assert len(first_hash) == 64 and len(second_hash) == 64
    print("[Forensic Vault] SHA-256 previous-block chaining: PASSED")

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer = RSAPSSForensicSigner(private_key)
    signature = signer.sign_block_hash(second_hash)
    assert signature.algorithm == "RSA-PSS-SHA256"
    assert signer.verify_block_hash(second_hash, signature.signature_b64) is True
    tampered_hash = "f" * 64 if second_hash != "f" * 64 else "e" * 64
    assert signer.verify_block_hash(tampered_hash, signature.signature_b64) is False
    print("[Forensic Vault] RSA-2048 PSS signature and tamper rejection: PASSED")
    print("FORENSIC_VAULT_TESTS_PASSED")


if __name__ == "__main__":
    run()
