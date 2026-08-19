import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ward_hub.db"
AUDIT_PATH = Path("/tmp/smart-ward-hub-audit-events.jsonl")
ANCHOR_PATH = Path("/tmp/smart-ward-hub-forensic-anchors.jsonl")
for path in (DB_PATH, AUDIT_PATH, ANCHOR_PATH):
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()

os.environ.setdefault("SW_AUTH_TOKENS_JSON", '{"test-token":["admin"]}')
os.environ["SW_AUDIT_LOG_PATH"] = str(AUDIT_PATH)
os.environ["SW_FORENSIC_ANCHOR_PATH"] = str(ANCHOR_PATH)
os.environ["SW_RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["SW_SEED_DATA"] = "true"
os.environ["SW_AUTO_CREATE_DB"] = "true"

from fastapi.testclient import TestClient

from edge_controls import SlidingWindowRateLimiter
from main import ACTIVE_PAIRINGS_CACHE, RATE_LIMITER, TELEMETRY_STORE, app
from database import SessionLocal
import models


DEVICE_ID = "MAC-A1:B2:C3:D4:E5:F6"


def packet(sequence: int, device_id: str = DEVICE_ID, accel_z: float = 1.0) -> dict:
    return {
        "schema_version": "1.0",
        "device_id": device_id,
        "sequence": sequence,
        "timestamp": "2026-01-01T00:00:00Z",
        "ppg": 74,
        "accel_x": 0,
        "accel_y": 0,
        "accel_z": accel_z,
        "skin_temp": 36.7,
        "battery_pct": 87,
        "heart_rate": 75,
        "spo2": 98,
    }


def run() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("test-client", now=100.0)[0] is True
    assert limiter.allow("test-client", now=100.1)[0] is True
    allowed, retry_after = limiter.allow("test-client", now=100.2)
    assert allowed is False and retry_after > 0
    assert limiter.allow("test-client", now=161.0)[0] is True
    print("[Residual Controls] Sliding-window rate limiter enforcement (PASSED)")

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
                "risk_level": "Medium",
            },
        )
        assert pairing.status_code == 200, pairing.text

        accepted = client.post("/api/v1/telemetry", json=packet(1))
        assert accepted.status_code == 200, accepted.text
        replay = client.post("/api/v1/telemetry", json=packet(1))
        assert replay.status_code == 409, replay.text
        print("[Residual Controls] Monotonic sequence replay rejection (PASSED)")

        device_two = "MAC-B2:C3:D4:E5:F6:A1"
        pairing_two = client.post(
            "/api/v1/pairing",
            json={
                "patient_token": "ptok-hn-2026-8902-demo",
                "bed_no": "W04-B13",
                "device_id": device_two,
                "risk_level": "Medium",
            },
        )
        assert pairing_two.status_code == 200, pairing_two.text
        for sequence in range(1, 7):
            response = client.post(
                "/api/v1/telemetry",
                json=packet(sequence, device_id=device_two, accel_z=3.0 if sequence == 1 else 1.0),
            )
            assert response.status_code == 200, response.text

        aggregate = client.post(f"/api/v1/telemetry/aggregate/{device_two}")
        assert aggregate.status_code == 200, aggregate.text
        handover = client.post(
            f"/api/v1/handover/{device_two}",
            json={"start_time": "2025-01-01T00:00:00Z", "end_time": "2027-01-01T00:00:00Z"},
        )
        assert handover.status_code == 200, handover.text
        bundle_id = handover.json()["bundle_id"]
        acknowledgment = {
            "acknowledged": True,
            "status_code": 200,
            "acknowledged_bundle_id": bundle_id,
            "acknowledgment_id": "ack-residual-001",
            "receiving_system": "hospital-his-sandbox",
            "server_time": "2026-01-01T00:05:00Z",
            "accepted_version": "R4",
            "accepted_profile": "hospital-observation-v1",
        }
        first_sync = client.post(
            f"/api/v1/handover/{device_two}/sync/{bundle_id}",
            json=acknowledgment,
        )
        second_sync = client.post(
            f"/api/v1/handover/{device_two}/sync/{bundle_id}",
            json=acknowledgment,
        )
        assert first_sync.status_code == 200, first_sync.text
        assert second_sync.status_code == 200, second_sync.text
        assert second_sync.json()["data"]["sync_status"] == "ACKNOWLEDGED_IDEMPOTENT"
        assert second_sync.json()["data"]["purged_aggregate_count"] == first_sync.json()["data"]["purged_aggregate_count"]
        with SessionLocal() as db:
            record = db.query(models.HandoverRecord).filter_by(bundle_id=bundle_id).one()
            attempts = db.query(models.SyncAttempt).filter_by(bundle_id=bundle_id).all()
            remaining = db.query(models.TelemetryAggregate).filter_by(device_id=device_two).count()
            assert record.synced is True
            assert len(attempts) == 2
            assert remaining == 0
        print("[Residual Controls] Handover sync idempotency and single purge (PASSED)")

        verification = client.get("/api/v1/forensics/verify")
        assert verification.status_code == 200
        assert verification.json()["integrity"] == "OK"
        print("[Residual Controls] Forensic chain verification and anchor integration (PASSED)")

        RATE_LIMITER.limit = 1
        RATE_LIMITER.clear()
        first = client.get("/health")
        second = client.get("/health")
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.headers.get("Retry-After")
        print("[Residual Controls] HTTP middleware rate-limit response (PASSED)")

    audit_lines = [json.loads(line) for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = {event["event_type"] for event in audit_lines}
    assert {"pairing.create", "telemetry.ingest", "handover.sync", "forensics.freeze", "forensics.verify"}.issubset(event_types)
    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    assert "ptok-hn-2026-8901-demo" not in audit_text
    assert "ptok-hn-2026-8902-demo" not in audit_text
    assert ANCHOR_PATH.exists()
    anchor_records = [json.loads(line) for line in ANCHOR_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert anchor_records and anchor_records[0]["anchor_type"] == "local_append_only_adapter"
    print("[Residual Controls] Structured JSONL audit and zero-PII redaction (PASSED)")

    print("\nALL RESIDUAL RISK CONTROL TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
