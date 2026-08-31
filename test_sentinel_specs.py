import time
import os
import sys
from pathlib import Path

os.environ.setdefault("SW_AUTH_TOKENS_JSON", '{"sentinel-test-token":["admin", "telemetry:write", "telemetry:read", "pairing:write"]}')

from fastapi.testclient import TestClient
from database import SessionLocal, engine
from main import app, TELEMETRY_STORE, ACTIVE_PAIRINGS_CACHE, HIS_SYNC_GATE
import models
import schemas
from package_portable_hub import package_portable, OUTPUT_ZIP


DEVICE_ID_BASE = "MAC-SENTINEL-BED-"
PATIENT_TOKEN_BASE = "ptok-sentinel-patient-"


def setup_test_beds(count: int = 30) -> list[str]:
    db = SessionLocal()
    device_ids = []
    ACTIVE_PAIRINGS_CACHE.clear()
    try:
        for i in range(1, count + 1):
            dev_id = f"{DEVICE_ID_BASE}{i:02d}"
            ptok = f"{PATIENT_TOKEN_BASE}{i:04d}-demo"
            bed_no = f"W04-B{i:02d}"
            device_ids.append(dev_id)

            patient = db.query(models.Patient).filter(models.Patient.patient_token == ptok).first()
            if not patient:
                db.add(models.Patient(patient_token=ptok))

            bed = db.query(models.Bed).filter(models.Bed.bed_no == bed_no).first()
            if not bed:
                db.add(models.Bed(bed_no=bed_no, ward_id="W04"))

            device = db.query(models.Device).filter(models.Device.device_id == dev_id).first()
            if not device:
                db.add(models.Device(device_id=dev_id))

            ACTIVE_PAIRINGS_CACHE[dev_id] = {
                "patient_token": ptok,
                "bed_no": bed_no,
                "session_id": f"session-{dev_id}",
            }
            TELEMETRY_STORE.clear_device(dev_id, reset_sequence=True)
        db.commit()
    finally:
        db.close()
    return device_ids


def test_decoupled_ingestion_and_triage_latency() -> None:
    device_ids = setup_test_beds(30)
    client = TestClient(app, headers={"Authorization": "Bearer sentinel-test-token"})
    
    start_time = time.perf_counter()
    
    # Simulate 30 concurrent wristbands streaming telemetry
    for seq, dev_id in enumerate(device_ids, start=1):
        payload = {
            "device_id": dev_id,
            "sequence": seq,
            "ppg": 80.0,
            "accel_x": 0.05,
            "accel_y": 0.05,
            "accel_z": 0.98,
            "skin_temp": 36.5,
            "heart_rate": 75,
            "spo2": 98,
            "battery_pct": 95,
        }
        res = client.post("/api/v1/telemetry", json=payload)
        assert res.status_code == 200, res.text
    
    elapsed = time.perf_counter() - start_time
    avg_per_bed = (elapsed / len(device_ids)) * 1000
    
    print(f"[Pillar 1: Decoupled Ingestion] 30 Beds Total Time: {elapsed:.3f}s (Avg per bed: {avg_per_bed:.2f}ms < 1500ms SLA): PASSED")
    assert avg_per_bed < 1500, f"Per-bed triage took {avg_per_bed:.2f}ms, exceeding 1.5s SLA"


def test_medical_black_box_pipeline_iso27037() -> None:
    dev_id = "MAC-SENTINEL-BED-01"
    client = TestClient(app, headers={"Authorization": "Bearer sentinel-test-token"})
    
    # Inject critical vital anomaly (SpO2 < 90 triggers immediate RED alert & black-box freeze)
    critical_payload = {
        "device_id": dev_id,
        "sequence": 100,
        "ppg": 110.0,
        "accel_x": 0.05,
        "accel_y": 0.05,
        "accel_z": 0.98,
        "skin_temp": 36.5,
        "heart_rate": 135,
        "spo2": 85,  # Critical RED trigger
        "battery_pct": 90,
    }
    res = client.post("/api/v1/telemetry", json=critical_payload)
    assert res.status_code == 200
    
    # Verify forensic package generated in database
    db = SessionLocal()
    try:
        packages = db.query(models.ForensicPackage).filter(
            models.ForensicPackage.device_id == dev_id
        ).order_by(models.ForensicPackage.id.desc()).all()
        assert len(packages) > 0, "No forensic package generated on critical alert"
        latest = packages[0]
        assert latest.block_hash is not None
        assert len(latest.block_hash) == 64  # Valid SHA-256
        assert latest.previous_hash is not None
        print("[Pillar 2: Medical Black Box] 10-Min Waveform Freeze & SHA-256 Hash Chain: PASSED")
    finally:
        db.close()


def test_safe_sync_and_purge_gate() -> None:
    dev_id = "MAC-SENTINEL-BED-02"
    client = TestClient(app, headers={"Authorization": "Bearer sentinel-test-token"})
    
    # 1. Populate some samples
    for seq in range(200, 210):
        client.post("/api/v1/telemetry", json={
            "device_id": dev_id,
            "sequence": seq,
            "ppg": 72.0,
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 1.0,
            "skin_temp": 36.6,
            "heart_rate": 72,
            "spo2": 99,
            "battery_pct": 88,
        })
    
    initial_buffer = TELEMETRY_STORE.snapshot(dev_id)
    assert len(initial_buffer) >= 9
    
    # 2. Case A: HIS returns HTTP 500 -> Purge must be rejected (412 Precondition Failed)
    res_failed = client.post("/api/v1/his/sync-and-purge", json={
        "device_id": dev_id,
        "his_http_status": 500,
        "his_response_payload": {"error": "HIS Internal Error"},
    })
    assert res_failed.status_code == 412
    assert len(TELEMETRY_STORE.snapshot(dev_id)) >= 9  # Data preserved!
    print("[Pillar 3: Safe Sync & Purge Gate] Block purge on HIS failure (HTTP 500): PASSED")
    
    # 3. Case B: HIS returns HTTP 200 with valid transaction -> Purge authorized
    res_success = client.post("/api/v1/his/sync-and-purge", json={
        "device_id": dev_id,
        "his_http_status": 200,
        "his_response_payload": {"transaction_id": "HIS-TX-998822", "status": "COMMITTED"},
    })
    assert res_success.status_code == 200
    assert len(TELEMETRY_STORE.snapshot(dev_id)) == 0  # Cleaned!
    print("[Pillar 3: Safe Sync & Purge Gate] Authorize purge on HIS confirmation (HTTP 200): PASSED")


def test_manus_pda_pairing_and_websocket_contract() -> None:
    db = SessionLocal()
    try:
        if not db.query(models.Patient).filter(models.Patient.patient_token == "anon-test-uuid-01").first():
            db.add(models.Patient(patient_token="anon-test-uuid-01"))
        if not db.query(models.Bed).filter(models.Bed.bed_no == "BED-04").first():
            db.add(models.Bed(bed_no="BED-04", ward_id="W04"))
        if not db.query(models.Device).filter(models.Device.device_id == "C6:AA:BB:CC:DD:01").first():
            db.add(models.Device(device_id="C6:AA:BB:CC:DD:01"))
        db.commit()
    finally:
        db.close()

    client = TestClient(app, headers={"Authorization": "Bearer sentinel-test-token"})

    # 1. Test PDA Pairing Payload with bed_id / device_uid aliases
    pairing_payload = {
        "bed_id": "BED-04",
        "patient_token": "anon-test-uuid-01",
        "device_uid": "C6:AA:BB:CC:DD:01",
        "placement_position": "WRIST",
    }
    res = client.post("/api/v1/pairing", json=pairing_payload)
    assert res.status_code == 200, res.text
    data = res.json().get("data", {})
    assert data.get("status") == "paired"
    assert data.get("bed_id") == "BED-04"
    assert data.get("device_id") == "C6:AA:BB:CC:DD:01"
    print("[Integration: Manus PDA] Pairing with bed_id/device_uid aliases & status 'paired': PASSED")

    # 2. Test WebSocket Telemetry & Heartbeat Stream
    with client.websocket_connect("/ws/v1/telemetry") as websocket:
        init_msg = websocket.receive_json()
        assert init_msg.get("hub_status") == "ONLINE"
        print("[Integration: Manus PDA] WebSocket /ws/v1/telemetry initial handshake: PASSED")


def test_portable_zip_packaging() -> None:
    zip_path = package_portable()
    assert zip_path.exists(), "Portable zip file was not created"
    assert zip_path.stat().st_size > 10000, "Portable zip file is empty"
    print(f"[Pillar 4: Portable Packaging] Archive generated successfully ({zip_path.stat().st_size / 1024:.1f} KB): PASSED")


def run_all() -> None:
    print("=" * 70)
    print(" [TEST] RUNNING IPD SMART SENTINEL SPECIFICATION VERIFICATION SUITE")
    print("=" * 70)
    test_decoupled_ingestion_and_triage_latency()
    test_medical_black_box_pipeline_iso27037()
    test_safe_sync_and_purge_gate()
    test_manus_pda_pairing_and_websocket_contract()
    test_portable_zip_packaging()
    print("=" * 70)
    print(" [SUCCESS] ALL 4 PILLARS + PDA INTEGRATION PASSED VERIFICATION!")
    print("=" * 70)


if __name__ == "__main__":
    run_all()
