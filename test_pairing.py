import os
os.environ.setdefault("SW_AUTH_TOKENS_JSON", '{"test-token":["admin"]}')

from pathlib import Path

# Ensure tests use a clean local database when run directly.
DB_PATH = Path(__file__).resolve().parent / "ward_hub.db"
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{DB_PATH}{suffix}")
    if path.exists():
        path.unlink()

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal, engine
from main import ACTIVE_PAIRINGS_CACHE, app
import models


DEVICE_ID = "MAC-A1:B2:C3:D4:E5:F6"
PAIRING_PAYLOAD = {
    "patient_token": "ptok-hn-2026-8901-demo",
    "bed_no": "W04-B12",
    "device_id": DEVICE_ID,
}


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"
        print("[Test Verification] System Health: OK (PASSED)")

        with engine.connect() as connection:
            journal_mode = connection.execute(text("PRAGMA journal_mode;")).scalar()
        assert str(journal_mode).lower() == "wal"
        print("[Test Verification] SQLite Journal Mode: WAL (PASSED)")

        response = client.post("/api/v1/pairing", json=PAIRING_PAYLOAD)
        assert response.status_code == 200, response.text
        pairing_id = response.json()["data"]["pairing_id"]
        assert DEVICE_ID in ACTIVE_PAIRINGS_CACHE
        print("[Test Verification] Ephemeral RAM Cache & DB Pairing: OK (PASSED)")

        invalid = client.post(
            "/api/v1/pairing",
            json={**PAIRING_PAYLOAD, "patient_token": "ptok-hn-not-found-demo"},
        )
        assert invalid.status_code == 404
        print("[Test Verification] Safe validation of non-existent resources: OK (PASSED)")

        unpair = client.post("/api/v1/unpair", json={"device_id": DEVICE_ID})
        assert unpair.status_code == 200, unpair.text
        assert DEVICE_ID not in ACTIVE_PAIRINGS_CACHE

        repaired = client.post("/api/v1/pairing", json=PAIRING_PAYLOAD)
        assert repaired.status_code == 200, repaired.text
        print("[Test Verification] Historical re-pairing under active-only index: PASSED")

    db = SessionLocal()
    try:
        pairing = db.query(models.Pairing).filter(models.Pairing.id == pairing_id).one()
        assert pairing.is_active is False
        assert pairing.unpaired_at is not None
    finally:
        db.close()
    print("[Test Verification] Central Dock Unbinding & Cache Purge: OK (PASSED)")
    print("\nALL LEVEL 1 BASELINE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
