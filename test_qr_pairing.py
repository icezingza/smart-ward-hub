import json
import pytest
from fastapi.testclient import TestClient

import main
import models
from utils_qr import get_hmac_secret
from scripts.generate_patient_qr import generate_patient_payload
from security import require_scope

client = TestClient(main.app)

# Override auth for tests
def mock_auth():
    return {"sub": "test-user", "scopes": ["admin"]}

main.app.dependency_overrides[require_scope("pairing:write")] = mock_auth

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def setup_db():
    db = main.SessionLocal()
    
    # Ensure test bed exists
    bed = db.query(models.Bed).filter_by(bed_no="B-TEST-QR").first()
    if not bed:
        bed = models.Bed(bed_no="B-TEST-QR", ward_id="W-1")
        db.add(bed)
        
    # Ensure test device exists
    device = db.query(models.Device).filter_by(device_id="DEV-QR-123").first()
    if not device:
        device = models.Device(device_id="DEV-QR-123", is_active=True)
        db.add(device)
        
    db.commit()
    yield db
    
    # Cleanup
    try:
        db.query(models.Pairing).filter(models.Pairing.device_id == "DEV-QR-123").delete()
        db.query(models.SessionWorkflow).filter(models.SessionWorkflow.device_id == "DEV-QR-123").delete()
        db.query(models.Patient).filter(models.Patient.patient_token.like("%-%-%-%-%")).delete() # delete uuids
        db.query(models.Device).filter_by(device_id="DEV-QR-123").delete()
        db.query(models.Bed).filter_by(bed_no="B-TEST-QR").delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_qr_pairing_success(setup_db, auth_headers):
    # 1. Generate valid QR Payload
    secret = get_hmac_secret()
    payload_dict = generate_patient_payload("B-TEST-QR", secret)
    qr_payload_str = json.dumps(payload_dict)

    # 2. Call API
    req_data = {
        "qr_payload": qr_payload_str,
        "device_id": "DEV-QR-123"
    }
    
    response = client.post("/api/v1/qr-pairing", json=req_data, headers=auth_headers)
    assert response.status_code == 200, response.text
    
    data = response.json()["data"]
    assert data["status"] == "paired"
    assert data["bed_no"] == "B-TEST-QR"
    assert data["device_id"] == "DEV-QR-123"
    assert data["patient_token"] == payload_dict["anonymous_id"]
    
    # Verify DB
    patient = setup_db.query(models.Patient).filter_by(patient_token=payload_dict["anonymous_id"]).first()
    assert patient is not None


def test_qr_pairing_invalid_signature(setup_db, auth_headers):
    # 1. Generate valid QR Payload but tamper it
    secret = get_hmac_secret()
    payload_dict = generate_patient_payload("B-TEST-QR", secret)
    payload_dict["hmac_sig"] = "tampered_signature"
    qr_payload_str = json.dumps(payload_dict)

    req_data = {
        "qr_payload": qr_payload_str,
        "device_id": "DEV-QR-123"
    }
    
    response = client.post("/api/v1/qr-pairing", json=req_data, headers=auth_headers)
    assert response.status_code == 400
    assert "Invalid cryptographic signature" in response.text
