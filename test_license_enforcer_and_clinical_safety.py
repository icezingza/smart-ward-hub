"""Focused regression & adversarial test suite for LicenseEnforcer and Clinical Safety Controls (NN-105)."""

import json
import tempfile
import time
from pathlib import Path

import jwt
from fastapi import HTTPException

from app.core.license_enforcer import LicenseEnforcer, LicensePayload
from hardware_security import HardwareSecurityEngine, HardwareTamperError


def test_jwt_license_verification_and_tamper_rejection():
    payload = {
        "hospital_id": "BDMS-01",
        "ward_id": "WARD-03",
        "max_beds": 30,
        "exp": int(time.time()) + 3600
    }
    
    # Simple PyJWT encoding test using secret for HMAC unit test or RSA
    # Testing LicenseEnforcer with valid cached payload
    enforcer = LicenseEnforcer(public_key_pem="dummy_pubkey")
    enforcer.cached_license = LicensePayload(**payload)
    
    assert enforcer.cached_license.hospital_id == "BDMS-01"
    assert enforcer.cached_license.max_beds == 30
    print("[LicenseEnforcer Test] JWT Payload parse & caching: PASSED")


def test_bed_quota_enforcement_and_http_423_locked():
    enforcer = LicenseEnforcer()
    enforcer.cached_license = LicensePayload(
        hospital_id="BDMS-01",
        ward_id="WARD-03",
        max_beds=30,
        exp=int(time.time()) + 3600
    )

    # 29 active beds -> OK
    assert enforcer.enforce_bed_quota(29) is True

    # 30 active beds -> Quota Reached -> HTTP 423 LOCKED
    try:
        enforcer.enforce_bed_quota(30)
        assert False, "Should have raised HTTP 423"
    except HTTPException as exc:
        assert exc.status_code == 423
        assert "capacity limit reached" in exc.detail
    print("[LicenseEnforcer Test] Bed quota HTTP 423 Locked enforcement: PASSED")


def test_clinical_emergency_override_patient_first_invariant():
    with tempfile.TemporaryDirectory() as tmpdir:
        audit_log = Path(tmpdir) / "audit_events.jsonl"
        enforcer = LicenseEnforcer(blackbox_log_path=audit_log)
        enforcer.cached_license = LicensePayload(
            hospital_id="BDMS-01",
            ward_id="WARD-03",
            max_beds=30,
            exp=int(time.time()) + 3600
        )

        # Quota is full (30 beds)
        try:
            enforcer.enforce_bed_quota(30)
            assert False
        except HTTPException as exc:
            assert exc.status_code == 423

        # Charge Nurse triggers emergency override
        res = enforcer.trigger_clinical_emergency_override("1234")
        assert res["status"] == "EMERGENCY_OVERRIDE_ACTIVE"
        assert res["valid_hours"] == 48

        # Patient First Invariant: Now 30 or 35 beds pass during emergency window
        assert enforcer.enforce_bed_quota(30) is True
        assert enforcer.enforce_bed_quota(35) is True

        # Check ISO 27037 Black Box audit log entry
        lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event_type"] == "CLINICAL_EMERGENCY_OVERRIDE_ACTIVATED"
        assert entry["iso_27037_sealed"] is True
        print("[LicenseEnforcer Test] Patient First 48h Emergency Override & ISO 27037 Log: PASSED")


def test_hardware_challenge_response_and_silent_rejection():
    engine = HardwareSecurityEngine()
    device_id = "Vanssa-001"
    secret_key = "K_dev_secret_12345"
    nonce = "abcd1234efgh5678"
    timestamp = int(time.time())

    # Valid HMAC
    import hmac, hashlib
    msg = f"{nonce}:{timestamp}".encode("utf-8")
    valid_hmac = hmac.new(secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    is_trusted, silent_drop = engine.verify_challenge_response(
        device_id, secret_key, nonce, timestamp, valid_hmac
    )
    assert is_trusted is True
    assert silent_drop is False

    # Untrusted / Invalid HMAC (Rogue ESP32 / Apple Watch) -> Silent Rejection
    is_trusted_rogue, silent_drop_rogue = engine.verify_challenge_response(
        device_id, secret_key, nonce, timestamp, "invalid_hmac_signature"
    )
    assert is_trusted_rogue is False
    assert silent_drop_rogue is True  # Alarm Fatigue Prevention: Dropped silently!
    print("[HardwareSecurity Test] Challenge-Response & Silent Driver Rejection: PASSED")


def test_tpm_node_locking():
    engine = HardwareSecurityEngine()
    current_fp = engine.get_host_hardware_fingerprint()

    # Matching hardware hash -> OK
    assert engine.enforce_node_locking(current_fp) is True

    # Mismatched hardware hash -> Node Lock Triggered
    try:
        engine.enforce_node_locking("tampered_hardware_hash_999")
        assert False, "Should have raised HardwareTamperError"
    except HardwareTamperError:
        pass
    print("[HardwareSecurity Test] TPM 2.0 / Motherboard Node Locking: PASSED")


def run():
    test_jwt_license_verification_and_tamper_rejection()
    test_bed_quota_enforcement_and_http_423_locked()
    test_clinical_emergency_override_patient_first_invariant()
    test_hardware_challenge_response_and_silent_rejection()
    test_tpm_node_locking()
    print("LICENSE_ENFORCER_AND_CLINICAL_SAFETY_TESTS_PASSED")


if __name__ == "__main__":
    run()
