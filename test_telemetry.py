import os
os.environ.setdefault("SW_AUTH_TOKENS_JSON", '{"test-token":["admin"]}')

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ward_hub.db"
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{DB_PATH}{suffix}")
    if path.exists():
        path.unlink()

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database import SessionLocal
from main import ACTIVE_PAIRINGS_CACHE, TELEMETRY_STORE, app
import models


DEVICE_ID = "MAC-A1:B2:C3:D4:E5:F6"
UNKNOWN_DEVICE = "MAC-UNKNOWN"


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        pairing = client.post(
            "/api/v1/pairing",
            json={
                "patient_token": "ptok-hn-2026-8901-demo",
                "bed_no": "W04-B12",
                "device_id": DEVICE_ID,
            },
        )
        assert pairing.status_code == 200, pairing.text
        print("[Test Verification] Step 1: Pairing Success (PASSED)")

        for sequence, (ppg, accel_z) in enumerate(zip([72, 75, 78, 74, 71], [1.0, 1.08, 0.98, 1.02, 1.01]), start=1):
            response = client.post(
                "/api/v1/telemetry",
                json={
                    "device_id": DEVICE_ID,
                    "sequence": sequence,
                    "ppg": ppg,
                    "accel_x": 0.0,
                    "accel_y": 0.0,
                    "accel_z": accel_z,
                    "skin_temp": 36.7,
                    "battery_pct": 87,
                },
            )
            assert response.status_code == 200, response.text
        assert len(TELEMETRY_STORE.snapshot(DEVICE_ID)) == 5
        print("[Test Verification] Step 2: Continuous Ingestion of 5 packets into RAM (PASSED)")

        blocked = client.post(
            "/api/v1/telemetry",
            json={
                    "device_id": UNKNOWN_DEVICE,
                    "sequence": 1,
                    "ppg": 80,
                "accel_x": 0,
                "accel_y": 0,
                "accel_z": 1,
                "skin_temp": 36.5,
                "battery_pct": 90,
            },
        )
        assert blocked.status_code == 403
        print("[Test Verification] Security Rule: Unpaired Device Telemetry Blocked (PASSED)")

        aggregate_response = client.post(f"/api/v1/telemetry/aggregate/{DEVICE_ID}")
        assert aggregate_response.status_code == 200, aggregate_response.text
        aggregate = aggregate_response.json()
        assert aggregate["sample_count"] == 5
        assert aggregate["ppg_avg"] == 74.0
        assert aggregate["ppg_min"] == 71.0
        assert aggregate["ppg_max"] == 78.0
        assert aggregate["max_accel_g"] == 1.08
        print("[Test Verification] Step 3: Math and Statistical Analytics accuracy (PASSED)")
        assert len(TELEMETRY_STORE.snapshot(DEVICE_ID)) == 0
        print("[Test Verification] Memory management: In-Memory cache successfully purged (PASSED)")

    db: Session = SessionLocal()
    try:
        record = db.query(models.TelemetryAggregate).filter(
            models.TelemetryAggregate.device_id == DEVICE_ID
        ).one()
        assert record.sample_count == 5
        assert record.ppg_avg == 74.0
    finally:
        db.close()

    print("\nALL LEVEL 2 INGESTION & AGGREGATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
