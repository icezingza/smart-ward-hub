import json
import os
from pathlib import Path

os.environ["SW_AUTH_TOKENS_JSON"] = json.dumps(
    {
        "admin-token": ["admin"],
        "read-token": ["telemetry:read"],
        "write-token": ["pairing:write", "telemetry:write"],
    }
)

DB_PATH = Path(__file__).resolve().parent / "ward_hub.db"
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{DB_PATH}{suffix}")
    if path.exists():
        path.unlink()

from fastapi.testclient import TestClient

from database import SessionLocal
from main import TELEMETRY_STORE, app
import models


PAIRING = {
    "patient_token": "ptok-hn-2026-8901-demo",
    "bed_no": "W04-B12",
    "device_id": "MAC-A1:B2:C3:D4:E5:F6",
}
WRITE_HEADERS = {"Authorization": "Bearer write-token"}
ADMIN_HEADERS = {"Authorization": "Bearer admin-token"}


def run() -> None:
    TELEMETRY_STORE.clear()
    with TestClient(app) as public_client:
        health = public_client.get("/health")
        assert health.status_code == 200
        assert health.headers.get("x-request-id")
        assert health.headers.get("x-content-type-options") == "nosniff"
        assert health.headers.get("x-frame-options") == "DENY"
        unauthenticated = public_client.post("/api/v1/pairing", json=PAIRING)
        assert unauthenticated.status_code == 401
        print("[Security] Unauthenticated pairing rejected: PASSED")

        wrong_scope = public_client.post(
            "/api/v1/pairing",
            json=PAIRING,
            headers={"Authorization": "Bearer read-token"},
        )
        assert wrong_scope.status_code == 403
        print("[Security] Missing scope rejected: PASSED")

        response = public_client.post("/api/v1/pairing", json=PAIRING, headers=WRITE_HEADERS)
        assert response.status_code == 200, response.text
        assert "patient_name" not in response.json().get("data", {})
        print("[Security] Authorized pairing contains no patient name: PASSED")

        legacy_payload = {
            "device_id": PAIRING["device_id"],
            "ppg": 70,
            "imu_x": 0,
            "imu_y": 0,
            "imu_z": 1,
            "skin_temp": 36.5,
            "battery": 90,
        }
        legacy = public_client.post(
            "/api/v1/telemetry",
            json=legacy_payload,
            headers={"Authorization": "Bearer admin-token"},
        )
        assert legacy.status_code == 422
        print("[Security] Legacy telemetry field names rejected: PASSED")

        valid = public_client.post(
            "/api/v1/telemetry",
            json={
                "schema_version": "1.0",
                "device_id": PAIRING["device_id"],
                "sequence": 1,
                "ppg": 70,
                "accel_x": 0,
                "accel_y": 0,
                "accel_z": 1,
                "skin_temp": 36.5,
                "battery_pct": 90,
            },
            headers={"Authorization": "Bearer admin-token"},
        )
        assert valid.status_code == 200, valid.text
        print("[Security] TelemetryPacket v1 accepted: PASSED")

    db = SessionLocal()
    try:
        patients = db.query(models.Patient).all()
        assert patients
        assert all(not hasattr(patient, "name") for patient in patients)
    finally:
        db.close()
    print("[Security] Edge Patient model has no name column: PASSED")

    print("\nSECURITY BASELINE TESTS PASSED")


if __name__ == "__main__":
    run()
