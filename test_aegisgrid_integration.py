"""
Integration Test Suite for AegisGrid Security Primitives inside Smart Ward Hub.
Tests:
1. Ed25519 TokenManager JWT verification & Multi-Key Ring Rotation (Zero-Downtime key exchange).
2. Tamper-Evident SHA-256 Audit Ledger with WORM Head-Hash Checkpoint validation.
3. CircuitBreaker Fault Tolerance and Fail-Safe Tripping.
4. Multi-Key DataEncryption Ring for At-Rest Storage.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption

import aegisgrid
from aegisgrid import (
    TokenManager,
    AuthLevel,
    TamperEvidentAuditLog,
    AuditAction,
    AuditOutcome,
    AuditLogIntegrityError,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    DataEncryption,
)
from aegisgrid.onprem import LocalWormCheckpointStore
import security


def test_token_manager_key_rotation() -> None:
    print("\n[AegisGrid Test 1] Testing Ed25519 TokenManager with Multi-Key Rotation...")
    
    # 1. Generate Key Pair 1 (Old Active Key)
    priv_key_1 = Ed25519PrivateKey.generate()
    pub_key_1 = priv_key_1.public_key()
    pub_pem_1 = pub_key_1.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    priv_pem_1 = priv_key_1.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode("ascii")

    # 2. Generate Key Pair 2 (New Active Key)
    priv_key_2 = Ed25519PrivateKey.generate()
    pub_key_2 = priv_key_2.public_key()
    pub_pem_2 = pub_key_2.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    priv_pem_2 = priv_key_2.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode("ascii")

    # Create Verifier with Multi-Key Ring retaining both kid-2025 and kid-2026
    verification_ring = {
        "kid-2025": pub_pem_1,
        "kid-2026": pub_pem_2,
    }

    verifier = TokenManager(
        key_id="kid-2026",
        public_key=pub_pem_2,
        verification_keys=verification_ring,
        issuer="smart-ward-hub",
        audience="smart-ward-pda",
    )

    # Issuer 1 issuing token with kid-2025
    issuer_1 = TokenManager(
        key_id="kid-2025",
        private_key=priv_pem_1,
        issuer="smart-ward-hub",
        audience="smart-ward-pda",
    )
    token_old = issuer_1.create_token(user_id="nurse-station-01", auth_level=AuthLevel.USER, expires_in=3600)

    # Issuer 2 issuing token with kid-2026
    issuer_2 = TokenManager(
        key_id="kid-2026",
        private_key=priv_pem_2,
        issuer="smart-ward-hub",
        audience="smart-ward-pda",
    )
    token_new = issuer_2.create_token(user_id="charge-nurse-02", auth_level=AuthLevel.ADMIN, expires_in=3600)

    # Verify both tokens pass verifier without downtime
    claims_old = verifier.verify_token(token_old)
    assert claims_old is not None
    assert claims_old["user_id"] == "nurse-station-01"

    claims_new = verifier.verify_token(token_new)
    assert claims_new is not None
    assert claims_new["user_id"] == "charge-nurse-02"

    # Inject verifier into security module
    security.AEGIS_TOKEN_MANAGER = verifier
    assert security.verify_raw_token(token_old, "telemetry:read") is True
    assert security.verify_raw_token(token_new, "admin") is True
    assert security.verify_raw_token("tampered.token.here", "telemetry:read") is False

    print("  --> Ed25519 TokenManager Key Rotation: PASSED")


def test_tamper_evident_audit_and_worm_checkpoint() -> None:
    print("\n[AegisGrid Test 2] Testing Tamper-Evident SHA-256 Audit Log & WORM Checkpoint...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        audit_path = Path(tmpdir) / "audit_chain.jsonl"
        checkpoint_dir = Path(tmpdir) / "checkpoints"

        audit_log = TamperEvidentAuditLog(path=audit_path)
        checkpoint_store = LocalWormCheckpointStore(checkpoint_dir)

        # Append 3 critical clinical events
        e1 = audit_log.append(
            actor_id="nurse-01",
            actor_role="Nurse",
            action=AuditAction.CREATE,
            outcome=AuditOutcome.SUCCESS,
            resource_type="BedPairing",
            resource_id="BED-01",
            request_id="req-001",
        )
        e2 = audit_log.append(
            actor_id="triage-engine",
            actor_role="AI",
            action=AuditAction.UPDATE,
            outcome=AuditOutcome.SUCCESS,
            resource_type="FallAlert",
            resource_id="BED-01",
            request_id="req-002",
        )
        e3 = audit_log.append(
            actor_id="charge-nurse",
            actor_role="Supervisor",
            action=AuditAction.READ,
            outcome=AuditOutcome.SUCCESS,
            resource_type="ForensicFreeze",
            resource_id="BED-01",
            request_id="req-003",
        )

        head_hash = audit_log.head_hash
        assert head_hash != TamperEvidentAuditLog.GENESIS_HASH

        # Save WORM checkpoint
        from aegisgrid.onprem import AuditCheckpoint
        cp = AuditCheckpoint(
            log_id="smart-ward-hub",
            head_hash=head_hash,
            created_at="2026-08-31T11:00:00Z",
        )
        checkpoint_store.publish(cp)

        # Verify integrity
        audit_log.verify_integrity(expected_head_hash=head_hash)
        expected_file = checkpoint_dir / f"smart-ward-hub-{head_hash}.json"
        assert expected_file.exists()

        # Test Tamper Detection: Modify an entry in the file
        with open(audit_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Tamper line 1
        tampered_entry = json.loads(lines[0])
        tampered_entry["actor_id"] = "malicious-hacker"
        lines[0] = json.dumps(tampered_entry) + "\n"
        
        with open(audit_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Reopen and verify failure
        try:
            TamperEvidentAuditLog(path=audit_path)
            assert False, "Should have detected audit tampering!"
        except AuditLogIntegrityError:
            pass  # Expected fail-closed behavior

    # Also test edge_controls.AuditSink SHA-256 hash chaining
    with tempfile.TemporaryDirectory() as tmpdir:
        sink_path = Path(tmpdir) / "audit_sink.jsonl"
        from edge_controls import AuditSink
        sink = AuditSink(sink_path)
        sink.record("user.login", "success", actor={"role": "nurse", "subject": "nurse-01"})
        sink.record("bed.pairing", "success", resource_type="bed", resource_id="BED-01")
        assert sink.verify_integrity() is True

        # Tamper sink file
        with open(sink_path, "r", encoding="utf-8") as f:
            sink_lines = f.readlines()
        entry = json.loads(sink_lines[0])
        entry["outcome"] = "tampered"
        sink_lines[0] = json.dumps(entry) + "\n"
        with open(sink_path, "w", encoding="utf-8") as f:
            f.writelines(sink_lines)
        
        tampered_sink = AuditSink(sink_path)
        assert tampered_sink.verify_integrity() is False

    print("  --> Tamper-Evident Audit & WORM Checkpoint: PASSED")


def test_circuit_breaker_resilience() -> None:
    print("\n[AegisGrid Test 3] Testing Circuit Breaker for External HIS Gateway...")
    
    cb = CircuitBreaker(
        name="his_sync",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1,
            success_threshold=1,
        )
    )

    # 1. Normal state
    assert cb.allow_request() is True
    cb.record_success()
    assert cb.state == CircuitState.CLOSED

    # 2. Trip the breaker with 3 failures
    for _ in range(3):
        cb.record_failure()

    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    # 3. Wait for recovery timeout to transition to HALF_OPEN
    time.sleep(1.1)
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN

    # 4. Success restores to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED

    print("  --> Circuit Breaker Resilience: PASSED")


def test_data_encryption_key_ring() -> None:
    print("\n[AegisGrid Test 4] Testing Multi-Key DataEncryption Ring...")
    from cryptography.fernet import Fernet

    key_old = Fernet.generate_key()
    key_new = Fernet.generate_key()

    # Encrypt with old single-key
    enc_old = DataEncryption(key=key_old)
    ciphertext = enc_old.encrypt_dict({"patient_risk": "HIGH", "score": 9.5})

    # Decrypt and Rotate with Key Ring [new_key, old_key]
    enc_ring = DataEncryption(keys=[key_new, key_old])
    decrypted = enc_ring.decrypt_dict(ciphertext)
    assert decrypted["patient_risk"] == "HIGH"
    assert decrypted["score"] == 9.5

    # Re-encrypt with new key
    rotated_ciphertext = enc_ring.rotate(ciphertext)
    assert rotated_ciphertext != ciphertext
    assert enc_ring.decrypt_dict(rotated_ciphertext)["patient_risk"] == "HIGH"

    print("  --> Multi-Key DataEncryption Ring: PASSED")


def run_all():
    print("=" * 70)
    print("  AEGISGRID & SMART WARD HUB INTEGRATION TEST SUITE")
    print("=" * 70)
    test_token_manager_key_rotation()
    test_tamper_evident_audit_and_worm_checkpoint()
    test_circuit_breaker_resilience()
    test_data_encryption_key_ring()
    print("\n" + "=" * 70)
    print("  ALL AEGISGRID INTEGRATION TESTS PASSED SUCCESSFULLY! (100% GREEN)")
    print("=" * 70)


if __name__ == "__main__":
    run_all()
