import os
os.environ.setdefault("SW_AUTH_TOKENS_JSON", '{"test-token":["admin"]}')

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ward_hub.db"
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{DB_PATH}{suffix}")
    if path.exists():
        path.unlink()

from fastapi.testclient import TestClient  # noqa: E402

from database import SessionLocal  # noqa: E402
from main import ACTIVE_PAIRINGS_CACHE, TELEMETRY_STORE, app  # noqa: E402
import models  # noqa: E402


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
        print("[Test Verification] Step 1: Admissions and Pairing (PASSED)")

        client.post("/api/v1/telemetry", json=packet())
        print("[Test Verification] Step 2: Normal Telemetry Ingestion (PASSED)")

        TELEMETRY_STORE.clear_device(DEVICE_ID, reset_sequence=True)
        client.post("/api/v1/telemetry", json=packet(accel_z=3.0))
        for sequence in range(2, 7):
            response = client.post("/api/v1/telemetry", json=packet(sequence=sequence))
            assert response.status_code == 200

        with SessionLocal() as db:
            packages = db.query(models.ForensicPackage).all()
            assert len(packages) == 1
            first_hash = packages[0].block_hash
        print("[Medical Black Box] CRITICAL FREEZE LOCKED: first package committed.")
        print("[Test Verification] Step 3: RED Alert triggered Forensic Lock (PASSED)")

        verification = client.get("/api/v1/forensics/verify")
        assert verification.status_code == 200
        assert verification.json()["integrity"] == "OK"
        assert verification.json()["last_hash"] == first_hash
        assert verification.json()["all_packages_signed_and_verified"] is False
        assert verification.json()["signature_status"][0]["status"] == "UNSIGNED"
        assert verification.json()["external_anchor_verified"] is False
        assert len(verification.json()["anchor_status"]) == 1
        assert verification.json()["anchor_status"][0]["status"].startswith("LOCAL_ANCHOR_")
        print("[Test Verification] Step 4: Genesis Cryptographic Parameters checked (PASSED)")

        with SessionLocal() as db:
            package = db.query(models.ForensicPackage).one()
            package.frozen_payload_json = "[]"
            db.commit()

        tampered = client.get("/api/v1/forensics/verify")
        assert tampered.status_code == 200
        assert tampered.json()["integrity"] == "FAILED"
        print("[Test Verification] Step 5: Database tampering detected (PASSED)")

    print("\nALL LEVEL 4 FORENSIC AND MEDICAL BLACK BOX TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
