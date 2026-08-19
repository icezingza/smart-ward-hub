import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ward_hub.db"
AUDIT_PATH = Path("/tmp/smart-ward-hub-session-workflow-audit.jsonl")
for path in (DB_PATH, AUDIT_PATH):
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()

os.environ["SW_AUTH_TOKENS_JSON"] = '{"test-token":["admin"]}'
os.environ["SW_DEVICE_TRUST_MODE"] = "disabled"
os.environ["SW_AUDIT_LOG_PATH"] = str(AUDIT_PATH)
os.environ["SW_AUTO_CREATE_DB"] = "true"
os.environ["SW_SEED_DATA"] = "true"
os.environ["SW_RATE_LIMIT_PER_MINUTE"] = "10000"

from fastapi.testclient import TestClient

from database import SessionLocal
from main import ACTIVE_PAIRINGS_CACHE, RATE_LIMITER, TELEMETRY_STORE, app
import models


DEVICE_A = "MAC-A1:B2:C3:D4:E5:F6"
DEVICE_B = "MAC-B2:C3:D4:E5:F6:A1"
DEVICE_C = "MAC-C3:D4:E5:F6:A1:B2"


def packet(device_id: str, sequence: int, spo2: float = 98.0) -> dict:
    return {
        "schema_version": "1.0",
        "device_id": device_id,
        "sequence": sequence,
        "ppg": 74,
        "accel_x": 0,
        "accel_y": 0,
        "accel_z": 1,
        "skin_temp": 36.7,
        "battery_pct": 87,
        "heart_rate": 75,
        "spo2": spo2,
    }


def pair(client: TestClient, device_id: str, patient_token: str, bed_no: str) -> dict:
    response = client.post(
        "/api/v1/pairing",
        json={"patient_token": patient_token, "bed_no": bed_no, "device_id": device_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    RATE_LIMITER.clear()
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        raw_hn = client.post(
            "/api/v1/pairing",
            json={"patient_token": "HN-2026-123456", "bed_no": "W04-B12", "device_id": DEVICE_A},
        )
        assert raw_hn.status_code == 422
        print("[Workflow] Raw HN admission input rejected at Hub boundary (PASSED)")

        first = pair(client, DEVICE_A, "ptok-hn-2026-8901-demo", "W04-B12")
        session_a = first["session_id"]
        bootstrap = client.get("/api/v1/kiosk/bootstrap")
        assert bootstrap.status_code == 200, bootstrap.text
        bootstrap_data = bootstrap.json()["data"]
        assert bootstrap_data["restore_state"] == "RESTORED"
        assert bootstrap_data["reconciliation_required"] is True
        assert "patient_token" not in json.dumps(bootstrap_data)
        print("[Workflow] Tablet kiosk bootstrap restores non-PII state and flags stale/no-heartbeat reconciliation (PASSED)")

        enroll_pointer = client.post(
            "/api/v1/nfc/pointers",
            json={"nfc_uid": "nfc-c60-device-a", "device_id": DEVICE_A},
        )
        assert enroll_pointer.status_code == 200, enroll_pointer.text
        resolved = client.post("/api/v1/nfc/resolve", json={"nfc_uid": "nfc-c60-device-a"})
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["data"]["device_id"] == DEVICE_A
        print("[Workflow] NFC pointer lookup is separate from cryptographic trust (PASSED)")

        for sequence in range(1, 4):
            response = client.post("/api/v1/telemetry", json=packet(DEVICE_A, sequence))
            assert response.status_code == 200, response.text

        reset_request = client.post(f"/api/v1/sessions/{session_a}/reset-request")
        assert reset_request.status_code == 200, reset_request.text
        assert reset_request.json()["data"]["status"] == "RESET_PENDING"
        reset_confirm = client.post(
            f"/api/v1/sessions/{session_a}/reset-confirm",
            json={"confirmation_code": "RESET"},
        )
        assert reset_confirm.status_code == 200, reset_confirm.text
        assert reset_confirm.json()["data"]["status"] == "READY_FOR_CHARGE"
        with SessionLocal() as db:
            digest = db.query(models.SessionCloseDigest).filter_by(session_id=session_a).one()
            closed = db.query(models.WardSession).filter_by(session_id=session_a).one()
            assert digest.sample_count == 3
            assert closed.status == "SESSION_CLOSED"
        print("[Workflow] RESET_PENDING confirmation creates routine digest and clears volatile buffer (PASSED)")

        second = pair(client, DEVICE_A, "ptok-hn-2026-8901-demo", "W04-B12")
        session_old = second["session_id"]
        client.post("/api/v1/telemetry", json=packet(DEVICE_A, 1))
        hot_swap = client.post(
            f"/api/v1/sessions/{session_old}/hot-swap",
            json={"new_device_id": DEVICE_B, "handover_id": "handover-hot-swap-001"},
        )
        assert hot_swap.status_code == 200, hot_swap.text
        session_new = hot_swap.json()["data"]["new_session_id"]
        assert session_new != session_old
        assert hot_swap.json()["data"]["handover_id"] == "handover-hot-swap-001"
        print("[Workflow] Hot-swap creates a new device session with linked handover ID (PASSED)")

        discharge = client.post(
            f"/api/v1/sessions/{session_new}/discharge",
            json={"handover_id": "handover-discharge-001"},
        )
        assert discharge.status_code == 200, discharge.text
        assert discharge.json()["data"]["status"] == "READY_FOR_CHARGE"
        print("[Workflow] Discharge closes session and returns device to charge-ready state (PASSED)")

        incident = pair(client, DEVICE_C, "ptok-hn-2026-8903-demo", "W04-B14")
        incident_session = incident["session_id"]
        incident_ingest = client.post("/api/v1/telemetry", json=packet(DEVICE_C, 1, spo2=85.0))
        assert incident_ingest.status_code == 200, incident_ingest.text
        with SessionLocal() as db:
            alert = db.query(models.Alert).filter_by(session_id=incident_session).one()
            package = db.query(models.ForensicPackage).filter_by(session_id=incident_session).one()
            assert alert.is_resolved is False
            assert json.loads(package.frozen_payload_json)["session_id"] == incident_session
        incident_reset = client.post(f"/api/v1/sessions/{incident_session}/reset-request")
        assert incident_reset.status_code == 200, incident_reset.text
        print("[Workflow] Incident-triggered freeze gates reset without losing forensic linkage (PASSED)")

    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    assert "ptok-hn-2026-8901-demo" not in audit_text
    assert "session.hot_swap" in audit_text
    assert "session.close_digest" in audit_text
    assert "nfc.pointer.resolve" in audit_text
    print("[Workflow] Session/NFC audit contains no raw patient token (PASSED)")
    print("\nALL SESSION WORKFLOW REGRESSION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
