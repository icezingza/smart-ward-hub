import hashlib
import json
import os
import sys
from pathlib import Path

# Setup test environment variables
os.environ.setdefault("SW_AUTH_TOKENS_JSON", '{"test-token":["admin", "pairing:write"]}')
os.environ.setdefault("SW_AUTH_TOKEN_HASHES_JSON", json.dumps({
    hashlib.sha256(b"hashed-secret-token").hexdigest(): ["admin", "pairing:write"]
}))

from fastapi.testclient import TestClient
from database import SessionLocal, engine
from main import app, MAX_REQUEST_BODY_BYTES, ACTIVE_PAIRINGS_CACHE
from config import settings


def test_body_size_limit() -> None:
    client = TestClient(app)
    # 1. Normal payload within limit
    res = client.get("/health")
    assert res.status_code == 200

    # 2. Oversized payload header
    headers = {"Content-Length": str(MAX_REQUEST_BODY_BYTES + 5000)}
    res_oversized = client.post("/api/v1/pairing", headers=headers, content=b"x" * 100)
    assert res_oversized.status_code == 413
    assert res_oversized.json()["detail"] == "Request body too large."
    print("[Hardening Test] BodySizeLimitMiddleware blocks oversized payload: PASSED")


def test_hashed_token_auth() -> None:
    with TestClient(app) as client:
        # Invalid bearer token
        res_invalid = client.get("/api/v1/kiosk/bootstrap", headers={"Authorization": "Bearer bad-token"})
        assert res_invalid.status_code == 401
        
        # Valid hashed bearer token
        res_valid = client.get("/api/v1/kiosk/bootstrap", headers={"Authorization": "Bearer hashed-secret-token"})
        assert res_valid.status_code == 200
        print("[Hardening Test] Static token SHA-256 hash authentication: PASSED")


def test_patient_token_error_sanitization() -> None:
    db = SessionLocal()
    try:
        import models
        db.query(models.Pairing).filter(models.Pairing.patient_token == "ptok-secret-unknown-value-9999").delete()
        db.query(models.WardSession).filter(models.WardSession.patient_token == "ptok-secret-unknown-value-9999").delete()
        db.query(models.Patient).filter(models.Patient.patient_token == "ptok-secret-unknown-value-9999").delete()
        db.commit()
    finally:
        db.close()

    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        res = client.post("/api/v1/pairing", json={
            "patient_token": "ptok-secret-unknown-value-9999",
            "bed_no": "W04-B12",
            "device_id": "MAC-A1:B2:C3:D4:E5:F6",
        })
        assert res.status_code == 404
        detail = res.json()["detail"]
        assert "ptok-secret-unknown-value-9999" not in detail
        assert detail == "Patient not found for the given token."
        print("[Hardening Test] Patient token 404 error sanitization: PASSED")


def test_kiosk_bootstrap_token_enforcement() -> None:
    from fastapi import Request
    from main import require_local_kiosk
    
    # In dev environment, local client passes without bootstrap token
    mock_request_dev = Request({
        "type": "http",
        "client": ("127.0.0.1", 12345),
        "headers": [],
    })
    res_dev = require_local_kiosk(mock_request_dev)
    assert res_dev["token_subject"] == "local-tablet-kiosk"

    # In pilot environment, mock settings
    original_env = settings.environment
    original_token = settings.local_bootstrap_token
    try:
        object.__setattr__(settings, "environment", "pilot")
        object.__setattr__(settings, "local_bootstrap_token", "secret-bootstrap-token-123")
        
        # Missing token in pilot -> 403
        try:
            require_local_kiosk(mock_request_dev)
            assert False, "Should have raised HTTPException 403"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403
            assert exc.detail == "Local bootstrap token required."

        # Correct token in pilot -> allowed
        mock_request_valid = Request({
            "type": "http",
            "client": ("127.0.0.1", 12345),
            "headers": [(b"x-local-bootstrap-token", b"secret-bootstrap-token-123")],
        })
        res_pilot = require_local_kiosk(mock_request_valid)
        assert res_pilot["token_subject"] == "local-tablet-kiosk"
        print("[Hardening Test] Kiosk bootstrap token enforcement in pilot/production: PASSED")
    finally:
        object.__setattr__(settings, "environment", original_env)
        object.__setattr__(settings, "local_bootstrap_token", original_token)


def test_loopback_proxy_header_rejection() -> None:
    from fastapi import Request
    from main import require_local_kiosk

    # Loopback IP with external X-Forwarded-For -> 403 rejected
    mock_request_proxied = Request({
        "type": "http",
        "client": ("127.0.0.1", 12345),
        "headers": [(b"x-forwarded-for", b"203.0.113.195")],
    })
    try:
        require_local_kiosk(mock_request_proxied)
        assert False, "Should have rejected external proxy header"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
        assert exc.detail == "Kiosk bootstrap is local-only."

    # Loopback IP with internal 127.0.0.1 X-Forwarded-For -> accepted
    mock_request_internal = Request({
        "type": "http",
        "client": ("127.0.0.1", 12345),
        "headers": [(b"x-forwarded-for", b"127.0.0.1")],
    })
    res = require_local_kiosk(mock_request_internal)
    assert res["token_subject"] == "local-tablet-kiosk"
    print("[Hardening Test] Loopback proxy header injection guard: PASSED")


def run_all() -> None:
    test_body_size_limit()
    test_hashed_token_auth()
    test_patient_token_error_sanitization()
    test_kiosk_bootstrap_token_enforcement()
    test_loopback_proxy_header_rejection()
    print("\nALL AUDIT HARDENING TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_all()
