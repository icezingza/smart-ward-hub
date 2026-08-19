from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import os
os.environ.setdefault("SW_AUTH_TOKENS_JSON", '{"test-token":["admin"]}')

from pathlib import Path
import json
import time

DB_PATH = Path(__file__).resolve().parent / "ward_hub.db"
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{DB_PATH}{suffix}")
    if path.exists():
        path.unlink()

from fastapi.testclient import TestClient

from database import SessionLocal
from main import ACTIVE_PAIRINGS_CACHE, TELEMETRY_STORE, app
import models


DEVICE_COUNT = 30
PATIENT_TOKEN_PREFIX = "ptok-pilot-token-"
DEVICE_ID_PREFIX = "MAC-PILOT-"
BED_PREFIX = "W04-PILOT-B"


def seed_pilot_records() -> list[dict[str, str]]:
    db = SessionLocal()
    try:
        records = []
        for index in range(1, DEVICE_COUNT + 1):
            patient_token = f"{PATIENT_TOKEN_PREFIX}{index:03d}"
            device_id = f"{DEVICE_ID_PREFIX}{index:03d}"
            bed_no = f"{BED_PREFIX}{index:02d}"
            db.add(models.Patient(patient_token=patient_token))
            db.add(models.Bed(bed_no=bed_no, ward_id="W04"))
            db.add(models.Device(device_id=device_id, is_active=True))
            records.append({"patient_token": patient_token, "device_id": device_id, "bed_no": bed_no})
        db.commit()
        return records
    finally:
        db.close()


def pair_devices(client: TestClient, records: list[dict[str, str]]) -> None:
    for record in records:
        response = client.post(
            "/api/v1/pairing",
            json={**record, "risk_level": "Low"},
        )
        assert response.status_code == 200, response.text


def send_one_packet(record: dict[str, str], timestamp: str) -> tuple[str, int]:
    client = TestClient(app, headers={"Authorization": "Bearer test-token"})
    response = client.post(
            "/api/v1/telemetry",
            json={
                "device_id": record["device_id"],
                "sequence": 1,
                "timestamp": timestamp,
                "ppg": 76.0,
                "accel_x": 0.0,
                "accel_y": 0.0,
                "accel_z": 1.0,
                "skin_temp": 36.7,
                "battery_pct": 90.0,
                "heart_rate": 76.0,
                "spo2": 98.0,
            },
    )
    return record["device_id"], response.status_code


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    records = []
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        records = seed_pilot_records()
        pair_devices(client, records)
        assert len(ACTIVE_PAIRINGS_CACHE) == DEVICE_COUNT

        concurrency_start = time.perf_counter()
        statuses = []
        timestamp = datetime.now(timezone.utc).isoformat()
        with ThreadPoolExecutor(max_workers=DEVICE_COUNT) as executor:
            futures = [executor.submit(send_one_packet, record, timestamp) for record in records]
            for future in as_completed(futures):
                statuses.append(future.result())
        concurrency_ms = (time.perf_counter() - concurrency_start) * 1000
        assert len(statuses) == DEVICE_COUNT
        failed_statuses = [item for item in statuses if item[1] != 200]
        if failed_statuses:
            print(f"[Pilot] Failed concurrent requests: {failed_statuses}")
        assert all(status == 200 for _, status in statuses)
        print(f"[Pilot] 30-device concurrent ingestion: {concurrency_ms:.2f} ms, all requests accepted")

        # Run a short deterministic workload representing 30 simulated days.
        daily_packets = 0
        simulation_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for day in range(30):
            day_timestamp = (simulation_start + timedelta(days=day)).isoformat()
            for record in records:
                response = client.post(
                    "/api/v1/telemetry",
                    json={
                        "device_id": record["device_id"],
                        "sequence": day + 2,
                        "timestamp": day_timestamp,
                        "ppg": 75.0 + (day % 5),
                        "accel_x": 0.0,
                        "accel_y": 0.0,
                        "accel_z": 1.0,
                        "skin_temp": 36.6,
                        "battery_pct": max(20.0, 92.0 - (day % 10)),
                        "heart_rate": 75.0 + (day % 5),
                        "spo2": 97.0 + (day % 2),
                    },
                )
                assert response.status_code == 200, response.text
                daily_packets += 1
        print(f"[Pilot] Simulated 30 days: {daily_packets} daily telemetry packets accepted")

        # Confirm that an unpaired device is rejected while the service remains online.
        blocked = client.post(
            "/api/v1/telemetry",
            json={
                "device_id": "MAC-PILOT-UNPAIRED",
                "sequence": 1,
                "ppg": 70,
                "accel_x": 0,
                "accel_y": 0,
                "accel_z": 1,
                "skin_temp": 36.5,
                "battery_pct": 90,
                "heart_rate": 70,
                "spo2": 98,
            },
        )
        assert blocked.status_code == 403
        health = client.get("/health")
        assert health.status_code == 200
        print("[Pilot] Offline authorization and health checks: PASSED")

    result = {
        "simulation_type": "software_functional_simulation",
        "simulated_days": 30,
        "device_count": DEVICE_COUNT,
        "concurrent_ingestion_ms": round(concurrency_ms, 3),
        "concurrent_requests_accepted": len(statuses),
        "daily_packets_accepted": daily_packets,
        "unpaired_device_status": blocked.status_code,
        "clinical_validation": "not_performed",
        "hardware_battery_validation": "not_performed",
        "external_network_sync_validation": "not_performed",
    }
    output_path = Path(__file__).resolve().parent / "pilot_simulation_result.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[Pilot] Results written to {output_path.name}")
    print("PILOT SOFTWARE SIMULATION COMPLETED")


if __name__ == "__main__":
    run()
