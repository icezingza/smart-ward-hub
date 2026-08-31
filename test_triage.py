import os
os.environ.setdefault("SW_AUTH_TOKENS_JSON", '{"test-token":["admin"]}')

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ward_hub.db"
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{DB_PATH}{suffix}")
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass

from fastapi.testclient import TestClient

from database import SessionLocal
from main import ACTIVE_PAIRINGS_CACHE, TELEMETRY_STORE, app
import models


DEVICE_ID = "MAC-A1:B2:C3:D4:E5:F6"


def packet(**overrides):
    value = {
        "device_id": DEVICE_ID,
        "sequence": 1,
        "ppg": 74,
        "accel_x": 0,
        "accel_y": 0,
        "accel_z": 1.0,
        "skin_temp": 36.7,
        "battery_pct": 87,
        "heart_rate": 75,
        "spo2": 98,
    }
    value.update(overrides)
    return value


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        health = client.get("/health")
        assert health.status_code == 200
        print("[Test Verification] System Health: OK (PASSED)")

        pairing = client.post(
            "/api/v1/pairing",
            json={
                "patient_token": "ptok-hn-2026-8901-demo",
                "bed_no": "W04-B12",
                "device_id": DEVICE_ID,
                "risk_level": "Medium",
            },
        )
        assert pairing.status_code == 200, pairing.text
        print("[Test Verification] Step 1: Admissions, Pairing & Risk tagging: OK (PASSED)")

        normal = client.post("/api/v1/telemetry", json=packet())
        assert normal.status_code == 200, normal.text
        with SessionLocal() as db:
            assert db.query(models.Alert).count() == 0
        print("[Test Verification] Step 2: Normal Telemetry & Base Triage: OK (PASSED)")

        TELEMETRY_STORE.clear_device(DEVICE_ID, reset_sequence=True)
        impact = client.post("/api/v1/telemetry", json=packet(accel_z=3.0))
        assert impact.status_code == 200
        for sequence in range(2, 7):
            follow_up = client.post("/api/v1/telemetry", json=packet(sequence=sequence))
            assert follow_up.status_code == 200
        with SessionLocal() as db:
            fall_alert = db.query(models.Alert).filter(
                models.Alert.device_id == DEVICE_ID,
                models.Alert.alert_type == "FALL",
            ).one_or_none()
            assert fall_alert is not None
            assert fall_alert.alert_level == "RED"
        print("[Test Verification] Step 3: Silent Fall Detection: OK (PASSED)")

        TELEMETRY_STORE.clear_device(DEVICE_ID, reset_sequence=True)
        anomaly = client.post(
            "/api/v1/telemetry",
            json=packet(spo2=88, heart_rate=130),
        )
        assert anomaly.status_code == 200, anomaly.text
        with SessionLocal() as db:
            vital_alert = db.query(models.Alert).filter(
                models.Alert.device_id == DEVICE_ID,
                models.Alert.alert_type == "VITAL_ANOMALY",
            ).one_or_none()
            assert vital_alert is not None
            assert vital_alert.alert_level == "RED"
        print("[Test Verification] Step 4: Golden Ratio Vital Triage: OK (PASSED)")

    print("\nALL LEVEL 3 AI TRIAGE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
