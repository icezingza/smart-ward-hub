from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import tempfile
import time

PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = PROJECT_DIR / "ward_hub.db"
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{DB_PATH}{suffix}")
    if path.exists():
        path.unlink()

STATE_DIR = Path(tempfile.mkdtemp(prefix="smart-ward-reliability-"))
os.environ["SW_AUTH_TOKENS_JSON"] = '{"test-token":["admin"]}'
os.environ["SW_TELEMETRY_STATE_PATH"] = str(STATE_DIR / "edge-state.json")
os.environ["SW_TELEMETRY_CHECKPOINT_EVERY"] = "1"
os.environ["SW_TELEMETRY_BUFFER_MAX_SAMPLES"] = "256"
os.environ["SW_ENABLE_DOCS"] = "false"

from fastapi.testclient import TestClient

from database import SessionLocal
from edge_runtime import EdgeTelemetryStore
from main import ACTIVE_PAIRINGS_CACHE, TELEMETRY_STORE, app
import models


AUTH_HEADERS = {"Authorization": "Bearer test-token"}
DEVICE_COUNT = 30
PACKETS_PER_DEVICE = 20


def seed_and_pair(client: TestClient) -> list[str]:
    db = SessionLocal()
    device_ids = []
    try:
        for index in range(1, DEVICE_COUNT + 1):
            token = f"ptok-reliability-{index:03d}"
            device_id = f"MAC-REL-{index:03d}"
            bed_no = f"W04-REL-B{index:02d}"
            db.add(models.Patient(patient_token=token))
            db.add(models.Bed(bed_no=bed_no, ward_id="W04"))
            db.add(models.Device(device_id=device_id, is_active=True))
            device_ids.append(device_id)
        db.commit()
    finally:
        db.close()
    for index, device_id in enumerate(device_ids, start=1):
        response = client.post(
            "/api/v1/pairing",
            json={
                "patient_token": f"ptok-reliability-{index:03d}",
                "bed_no": f"W04-REL-B{index:02d}",
                "device_id": device_id,
            },
        )
        assert response.status_code == 200, response.text
    return device_ids


def send_device_stream(device_id: str) -> list[tuple[int, float]]:
    client = TestClient(app, headers=AUTH_HEADERS)
    results = []
    for sequence in range(1, PACKETS_PER_DEVICE + 1):
        started = time.perf_counter()
        response = client.post(
            "/api/v1/telemetry",
            json={
                "schema_version": "1.0",
                "device_id": device_id,
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ppg": 0.82,
                "accel_x": 0.0,
                "accel_y": 0.0,
                "accel_z": 1.0,
                "skin_temp": 36.7,
                "battery_pct": 90.0,
                "heart_rate": 76.0,
                "spo2": 98.0,
            },
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        results.append((response.status_code, elapsed_ms))
    return results


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    with TestClient(app, headers=AUTH_HEADERS) as client:
        device_ids = seed_and_pair(client)
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=DEVICE_COUNT) as executor:
            futures = [executor.submit(send_device_stream, device_id) for device_id in device_ids]
            results = [item for future in as_completed(futures) for item in future.result()]
        wall_ms = (time.perf_counter() - started) * 1000
        statuses = [status for status, _ in results]
        latencies = [latency for _, latency in results]
        assert all(status == 200 for status in statuses), sorted(set(statuses))
        assert len(TELEMETRY_STORE.snapshot(device_ids[0])) == PACKETS_PER_DEVICE
        print(f"[Reliability] {len(results)} concurrent requests accepted in {wall_ms:.2f} ms")

        duplicate = client.post(
            "/api/v1/telemetry",
            json={
                "schema_version": "1.0",
                "device_id": device_ids[0],
                "sequence": PACKETS_PER_DEVICE,
                "ppg": 0.82,
                "accel_x": 0,
                "accel_y": 0,
                "accel_z": 1,
                "skin_temp": 36.7,
                "battery_pct": 90,
            },
        )
        assert duplicate.status_code == 409
        print("[Reliability] Duplicate packet rejected: PASSED")

        unauthorized = client.post(
            "/api/v1/telemetry",
            json={
                "schema_version": "1.0",
                "device_id": "MAC-NOT-PAIRED",
                "sequence": 1,
                "ppg": 0.82,
                "accel_x": 0,
                "accel_y": 0,
                "accel_z": 1,
                "skin_temp": 36.7,
                "battery_pct": 90,
            },
        )
        assert unauthorized.status_code == 403
        print("[Reliability] Unpaired device rejected: PASSED")

        bad_host = client.get("/health", headers={"Host": "untrusted.example"})
        assert bad_host.status_code == 400
        print("[Reliability] Untrusted Host header rejected: PASSED")

    recovered = EdgeTelemetryStore(
        max_samples=256,
        state_path=STATE_DIR / "edge-state.json",
        checkpoint_every=1,
    )
    assert len(recovered.snapshot(device_ids[0])) == PACKETS_PER_DEVICE
    print("[Reliability] Checkpoint recovery after simulated process boundary: PASSED")

    result = {
        "test_type": "software_reliability_validation",
        "device_count": DEVICE_COUNT,
        "packets_per_device": PACKETS_PER_DEVICE,
        "total_requests": len(results),
        "wall_clock_ms": round(wall_ms, 3),
        "latency_ms": {
            "p50": round(percentile(latencies, 0.50), 3),
            "p95": round(percentile(latencies, 0.95), 3),
            "p99": round(percentile(latencies, 0.99), 3),
            "max": round(max(latencies), 3),
            "mean": round(statistics.mean(latencies), 3),
        },
        "all_status_200": all(status == 200 for status in statuses),
        "fault_cases": {
            "duplicate_sequence": "passed",
            "unpaired_device": "passed",
            "untrusted_host": "passed",
            "checkpoint_recovery": "passed",
        },
        "hardware_validation": "not_performed",
        "clinical_validation": "not_performed",
    }
    output_path = PROJECT_DIR / "reliability_validation_result.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[Reliability] Results written to {output_path.name}")
    print("RELIABILITY VALIDATION COMPLETED")


if __name__ == "__main__":
    run()
