import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ward_hub.db"
AUDIT_PATH = Path("/tmp/smart-ward-hub-device-trust-observe-audit.jsonl")
for path in (DB_PATH, AUDIT_PATH):
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()

os.environ["SW_AUTH_TOKENS_JSON"] = '{"test-token":["admin"]}'
os.environ["SW_DEVICE_TRUST_MODE"] = "observe"
os.environ["SW_AUDIT_LOG_PATH"] = str(AUDIT_PATH)
os.environ["SW_AUTO_CREATE_DB"] = "true"
os.environ["SW_SEED_DATA"] = "true"
os.environ["SW_RATE_LIMIT_PER_MINUTE"] = "10000"

from fastapi.testclient import TestClient

from main import ACTIVE_PAIRINGS_CACHE, RATE_LIMITER, TELEMETRY_STORE, app


DEVICE_ID = "MAC-A1:B2:C3:D4:E5:F6"


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    RATE_LIMITER.clear()
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
        response = client.post(
            "/api/v1/telemetry",
            json={
                "schema_version": "1.0",
                "device_id": DEVICE_ID,
                "sequence": 1,
                "ppg": 74,
                "accel_x": 0,
                "accel_y": 0,
                "accel_z": 1,
                "skin_temp": 36.7,
                "battery_pct": 87,
                "heart_rate": 75,
                "spo2": 98,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["device_trust"] == "UNVERIFIED"
    assert "device_trust.verify" in AUDIT_PATH.read_text(encoding="utf-8")
    print("[Device Trust] Observe mode preserves telemetry continuity and records unverified state (PASSED)")
    print("\nDEVICE TRUST OBSERVE-MODE TEST PASSED")


if __name__ == "__main__":
    run()
