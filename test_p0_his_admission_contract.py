from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ward_hub.db"
AUDIT_PATH = Path("/tmp/smart-ward-hub-p0-his-admission-audit.jsonl")
for path in (DB_PATH, AUDIT_PATH):
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()

os.environ["SW_AUTH_TOKENS_JSON"] = '{"test-token":["admin"]}'
os.environ["SW_DEVICE_TRUST_MODE"] = "disabled"
os.environ["SW_AUDIT_LOG_PATH"] = str(AUDIT_PATH)
os.environ["SW_AUTO_CREATE_DB"] = "true"
os.environ["SW_SEED_DATA"] = "true"
os.environ["SW_RATE_LIMIT_PER_MINUTE"] = "10000"

from fastapi.testclient import TestClient

from database import SessionLocal
from his_admission_gateway_contract import GatewayTokenError, SandboxAdmissionGateway
from main import ACTIVE_PAIRINGS_CACHE, RATE_LIMITER, TELEMETRY_STORE, app
import models


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


DEVICE_ID = "MAC-A1:B2:C3:D4:E5:F6"
RAW_HN = "HN-REAL-LOOKING-SYNTHETIC-0001"
OPAQUE_TOKEN_B = "ptok-sandbox-secondary-0002"


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = MutableClock(now)
    gateway = SandboxAdmissionGateway(clock=clock)

    token = gateway.issue(RAW_HN, ttl_seconds=2)
    assert token.startswith("ptok-")
    assert RAW_HN not in token
    payload = gateway.hub_admission_payload(
        token,
        bed_no="W04-B12",
        idempotency_key="p0-his-admission-001",
    )
    assert RAW_HN not in json.dumps(payload)
    print("[P0-001] HIS raw reference is converted to an opaque Hub token: PASSED")

    clock.value = now + timedelta(seconds=3)
    try:
        gateway.validate(token)
    except GatewayTokenError as exc:
        assert str(exc) == "expired_token"
    else:
        raise AssertionError("expired token was accepted")
    print("[P0-001] Gateway token TTL expiry blocks stale admission handoff: PASSED")

    live_token = gateway.issue("AN-REAL-LOOKING-SYNTHETIC-0002", ttl_seconds=300)
    gateway.revoke(live_token)
    try:
        gateway.validate(live_token)
    except GatewayTokenError as exc:
        assert str(exc) == "revoked_token"
    else:
        raise AssertionError("revoked token was accepted")
    print("[P0-001] Gateway token revocation blocks admission handoff: PASSED")

    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        prepared = client.post(
            "/api/v1/outside/admission-preparations",
            json=payload,
        )
        assert prepared.status_code == 200, prepared.text
        prepared_data = prepared.json()["data"]
        admission_id = prepared_data["admission_id"]
        assert RAW_HN not in prepared.text
        assert prepared_data["status"] == "PREPARED"
        print("[P0-001] Hub accepts only the opaque gateway payload and reserves the bed: PASSED")

        replay = client.post(
            "/api/v1/outside/admission-preparations",
            json=payload,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"]["admission_id"] == admission_id
        print("[P0-001] Admission preparation idempotency returns one authoritative result: PASSED")

        pairing = client.post(
            "/api/v1/pairing",
            json={
                "patient_token": token,
                "bed_no": "W04-B12",
                "device_id": DEVICE_ID,
            },
        )
        assert pairing.status_code == 200, pairing.text

        for sequence, timestamp, heart_rate in (
            (1, "2026-01-01T00:00:10Z", 70),
            (2, "2026-01-01T00:01:10Z", 84),
        ):
            telemetry = client.post(
                "/api/v1/telemetry",
                json={
                    "device_id": DEVICE_ID,
                    "sequence": sequence,
                    "timestamp": timestamp,
                    "ppg": heart_rate,
                    "accel_x": 0,
                    "accel_y": 0,
                    "accel_z": 1,
                    "skin_temp": 36.8,
                    "battery_pct": 88,
                    "heart_rate": heart_rate,
                    "spo2": 97,
                },
            )
            assert telemetry.status_code == 200, telemetry.text

        aggregate = client.post(f"/api/v1/telemetry/aggregate/{DEVICE_ID}")
        assert aggregate.status_code == 200, aggregate.text
        handover = client.post(
            f"/api/v1/handover/{DEVICE_ID}",
            json={
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-01T00:02:00Z",
            },
        )
        assert handover.status_code == 200, handover.text
        bundle_id = handover.json()["bundle_id"]

        failed = client.post(
            f"/api/v1/handover/{DEVICE_ID}/sync/{bundle_id}",
            json={"acknowledged": False, "status_code": 503, "error_message": "sandbox HIS unavailable"},
        )
        assert failed.status_code == 200 and failed.json()["success"] is False
        assert "HN-REAL" not in failed.text
        with SessionLocal() as db:
            assert db.query(models.TelemetryAggregate).count() == 1
        print("[P0-001] HIS transport failure retains local aggregate: PASSED")

        mismatch = client.post(
            f"/api/v1/handover/{DEVICE_ID}/sync/{bundle_id}",
            json={
                "acknowledged": True,
                "status_code": 200,
                "acknowledged_bundle_id": "wrong-bundle",
                "acknowledgment_id": "sandbox-ack-001",
                "receiving_system": "hospital-his-sandbox",
                "server_time": "2026-01-01T00:05:00Z",
                "accepted_version": "R4",
                "accepted_profile": "hospital-observation-v1",
            },
        )
        assert mismatch.status_code == 409
        with SessionLocal() as db:
            assert db.query(models.TelemetryAggregate).count() == 1
        print("[P0-001] Mismatched HIS bundle acknowledgment blocks purge: PASSED")

        acknowledged = client.post(
            f"/api/v1/handover/{DEVICE_ID}/sync/{bundle_id}",
            json={
                "acknowledged": True,
                "status_code": 200,
                "acknowledged_bundle_id": bundle_id,
                "acknowledgment_id": "sandbox-ack-001",
                "receiving_system": "hospital-his-sandbox",
                "server_time": "2026-01-01T00:05:00Z",
                "accepted_version": "R4",
                "accepted_profile": "hospital-observation-v1",
            },
        )
        assert acknowledged.status_code == 200, acknowledged.text
        assert acknowledged.json()["data"]["purged_aggregate_count"] == 1
        with SessionLocal() as db:
            assert db.query(models.TelemetryAggregate).count() == 0
            record = db.query(models.HandoverRecord).filter(models.HandoverRecord.bundle_id == bundle_id).one()
            assert record.synced is True
        print("[P0-001] Structured matching HIS acknowledgment permits exact-scope purge: PASSED")

    audit = AUDIT_PATH.read_text(encoding="utf-8") if AUDIT_PATH.exists() else ""
    assert RAW_HN not in audit
    print("[P0-001] Audit output contains no raw HN/AN reference: PASSED")
    print("P0_HIS_ADMISSION_CONTRACT_TESTS_PASSED")


if __name__ == "__main__":
    run()
