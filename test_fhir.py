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
START = "2026-01-01T00:00:00Z"
END = "2026-01-01T00:02:00Z"


def send_packet(client: TestClient, timestamp: str, heart_rate: float, spo2: float, temp: float):
    response = client.post(
        "/api/v1/telemetry",
        json={
            "device_id": DEVICE_ID,
            "sequence": 1 if timestamp.endswith("00:00:10Z") else 2,
            "timestamp": timestamp,
            "ppg": heart_rate,
            "accel_x": 0,
            "accel_y": 0,
            "accel_z": 1,
            "skin_temp": temp,
            "battery_pct": 88,
            "heart_rate": heart_rate,
            "spo2": spo2,
        },
    )
    assert response.status_code == 200, response.text


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
                "risk_level": "Medium",
            },
        )
        assert pairing.status_code == 200, pairing.text

        send_packet(client, "2026-01-01T00:00:10Z", 70, 97, 36.5)
        send_packet(client, "2026-01-01T00:01:10Z", 84, 98, 37.0)
        aggregate = client.post(f"/api/v1/telemetry/aggregate/{DEVICE_ID}")
        assert aggregate.status_code == 200, aggregate.text
        assert aggregate.json()["heart_rate_avg"] == 77.0
        assert aggregate.json()["spo2_avg"] == 97.5

        handover = client.post(
            f"/api/v1/handover/{DEVICE_ID}",
            json={"start_time": START, "end_time": END},
        )
        assert handover.status_code == 200, handover.text
        handover_data = handover.json()
        assert handover_data["sync_status"] == "NOT_SYNCED"
        assert handover_data["clinical_metrics"]["heart_rate"]["min"] == 70.0
        assert handover_data["clinical_metrics"]["heart_rate"]["max"] == 84.0
        bundle = handover_data["fhir_bundle"]
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        codes = {
            entry["resource"]["code"]["coding"][0]["code"]
            for entry in bundle["entry"]
            if "coding" in entry["resource"].get("code", {})
        }
        assert {"8867-4", "2708-6", "8310-5"}.issubset(codes)
        bundle_id = handover_data["bundle_id"]
        print("[Test Verification] Step 1: Shift Handover Digest and FHIR Bundle (PASSED)")

        failed_sync = client.post(
            f"/api/v1/handover/{DEVICE_ID}/sync/{bundle_id}",
            json={"acknowledged": False, "status_code": 503, "error_message": "remote unavailable"},
        )
        assert failed_sync.status_code == 200
        assert failed_sync.json()["success"] is False
        with SessionLocal() as db:
            assert db.query(models.TelemetryAggregate).count() == 1
        print("[Test Verification] Step 2: Failed sync retained local aggregates (PASSED)")

        incomplete_ack = client.post(
            f"/api/v1/handover/{DEVICE_ID}/sync/{bundle_id}",
            json={"acknowledged": True, "status_code": 200},
        )
        assert incomplete_ack.status_code == 422
        with SessionLocal() as db:
            assert db.query(models.TelemetryAggregate).count() == 1
        print("[FHIR] Bare 200 acknowledgment rejected before purge (PASSED)")

        mismatched_ack = client.post(
            f"/api/v1/handover/{DEVICE_ID}/sync/{bundle_id}",
            json={
                "acknowledged": True,
                "status_code": 200,
                "acknowledged_bundle_id": "wrong-bundle",
                "acknowledgment_id": "ack-001",
                "receiving_system": "hospital-his-sandbox",
                "server_time": "2026-01-01T00:05:00Z",
                "accepted_version": "R4",
                "accepted_profile": "hospital-observation-v1",
            },
        )
        assert mismatched_ack.status_code == 409
        with SessionLocal() as db:
            assert db.query(models.TelemetryAggregate).count() == 1
        print("[FHIR] Mismatched acknowledgment bundle rejected before purge (PASSED)")

        successful_sync = client.post(
            f"/api/v1/handover/{DEVICE_ID}/sync/{bundle_id}",
            json={
                "acknowledged": True,
                "status_code": 200,
                "acknowledged_bundle_id": bundle_id,
                "acknowledgment_id": "ack-001",
                "receiving_system": "hospital-his-sandbox",
                "server_time": "2026-01-01T00:05:00Z",
                "accepted_version": "R4",
                "accepted_profile": "hospital-observation-v1",
            },
        )
        assert successful_sync.status_code == 200
        assert successful_sync.json()["success"] is True
        assert successful_sync.json()["data"]["purged_aggregate_count"] == 1
        with SessionLocal() as db:
            assert db.query(models.TelemetryAggregate).count() == 0
            record = db.query(models.HandoverRecord).filter(
                models.HandoverRecord.bundle_id == bundle_id
            ).one()
            assert record.synced is True
        print("[Test Verification] Step 3: 200 ACK triggered safe Auto-Purge (PASSED)")

    print("\nALL LEVEL 5 FHIR AND SHIFT HANDOVER TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
