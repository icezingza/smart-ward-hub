import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ward_hub.db"
AUDIT_PATH = Path("/tmp/smart-ward-hub-device-trust-audit.jsonl")
for path in (DB_PATH, AUDIT_PATH):
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()

os.environ["SW_AUTH_TOKENS_JSON"] = '{"test-token":["admin"]}'
os.environ["SW_DEVICE_TRUST_MODE"] = "enforce"
os.environ["SW_AUDIT_LOG_PATH"] = str(AUDIT_PATH)
os.environ["SW_AUTO_CREATE_DB"] = "true"
os.environ["SW_SEED_DATA"] = "true"
os.environ["SW_RATE_LIMIT_PER_MINUTE"] = "10000"

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from database import SessionLocal
from device_trust import canonicalize_telemetry
from main import ACTIVE_PAIRINGS_CACHE, RATE_LIMITER, TELEMETRY_STORE, app
import models
import schemas


DEVICE_ID = "MAC-A1:B2:C3:D4:E5:F6"
PATIENT_TOKEN = "ptok-hn-2026-8901-demo"


def make_packet(sequence: int, *, spo2: float = 98.0) -> dict:
    return {
        "schema_version": "1.0",
        "device_id": DEVICE_ID,
        "sequence": sequence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ppg": 74,
        "accel_x": 0,
        "accel_y": 0,
        "accel_z": 1.0,
        "skin_temp": 36.7,
        "battery_pct": 87,
        "heart_rate": 75,
        "spo2": spo2,
    }


def encode_public_key(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def signed_headers(private_key: Ed25519PrivateKey, packet: dict, key_id: str = "key-device-a-v1") -> dict[str, str]:
    parsed_packet = schemas.TelemetryPacket.model_validate(packet).model_dump()
    signature = private_key.sign(canonicalize_telemetry(parsed_packet))
    encoded = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return {"X-Device-Key-ID": key_id, "X-Device-Signature": encoded}


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    RATE_LIMITER.clear()
    private_key = Ed25519PrivateKey.generate()
    public_key_b64 = encode_public_key(private_key)

    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["device_trust_mode"] == "enforce"

        enrollment = client.post(
            "/api/v1/device-trust/enroll",
            json={
                "device_id": DEVICE_ID,
                "key_id": "key-device-a-v1",
                "algorithm": "Ed25519",
                "public_key_b64": public_key_b64,
            },
        )
        assert enrollment.status_code == 200, enrollment.text
        assert enrollment.json()["data"]["algorithm"] == "Ed25519"
        print("[Device Trust] Public-key enrollment and fingerprinting (PASSED)")

        with SessionLocal() as db:
            credential = db.query(models.DeviceCredential).filter_by(key_id="key-device-a-v1").one()
            assert credential.public_key_b64 == public_key_b64
            assert credential.status == "ACTIVE"
        print("[Device Trust] Credential persistence across DB session boundary (PASSED)")

        pairing = client.post(
            "/api/v1/pairing",
            json={
                "patient_token": PATIENT_TOKEN,
                "bed_no": "W04-B12",
                "device_id": DEVICE_ID,
            },
        )
        assert pairing.status_code == 200, pairing.text

        packet = make_packet(1)
        accepted = client.post(
            "/api/v1/telemetry",
            json=packet,
            headers=signed_headers(private_key, packet),
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["data"]["device_trust"] == "VERIFIED"
        print("[Device Trust] Canonical signed TelemetryPacket v1 accepted (PASSED)")

        mutated = dict(packet)
        mutated["spo2"] = 90.0
        mutation = client.post(
            "/api/v1/telemetry",
            json=mutated,
            headers=signed_headers(private_key, packet),
        )
        assert mutation.status_code == 401, mutation.text
        print("[Device Trust] Signed-field mutation rejected (PASSED)")

        missing_signature = client.post("/api/v1/telemetry", json=make_packet(2))
        assert missing_signature.status_code == 401, missing_signature.text
        print("[Device Trust] Missing signature rejected in enforce mode (PASSED)")

        replay = client.post(
            "/api/v1/telemetry",
            json=packet,
            headers=signed_headers(private_key, packet),
        )
        assert replay.status_code == 409, replay.text
        print("[Device Trust] Validly signed replay still rejected by sequence guard (PASSED)")

        revoked = client.post(
            f"/api/v1/device-trust/{DEVICE_ID}/lifecycle",
            json={"key_id": "key-device-a-v1", "status": "REVOKED"},
        )
        assert revoked.status_code == 200, revoked.text
        revoked_packet = make_packet(2)
        revoked_ingest = client.post(
            "/api/v1/telemetry",
            json=revoked_packet,
            headers=signed_headers(private_key, revoked_packet),
        )
        assert revoked_ingest.status_code == 401, revoked_ingest.text
        print("[Device Trust] Revoked credential rejected (PASSED)")

        expired_key = Ed25519PrivateKey.generate()
        expired_public_key_b64 = encode_public_key(expired_key)
        expired_enrollment = client.post(
            "/api/v1/device-trust/enroll",
            json={
                "device_id": DEVICE_ID,
                "key_id": "key-device-a-expired",
                "algorithm": "Ed25519",
                "public_key_b64": expired_public_key_b64,
                "expires_at": "2020-01-01T00:00:00Z",
            },
        )
        assert expired_enrollment.status_code == 200, expired_enrollment.text
        expired_packet = make_packet(2)
        expired_ingest = client.post(
            "/api/v1/telemetry",
            json=expired_packet,
            headers=signed_headers(expired_key, expired_packet, key_id="key-device-a-expired"),
        )
        assert expired_ingest.status_code == 401, expired_ingest.text
        print("[Device Trust] Expired credential rejected (PASSED)")

    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    audit_events = [json.loads(line) for line in audit_text.splitlines() if line.strip()]
    event_types = {event["event_type"] for event in audit_events}
    assert {"device_trust.enroll", "device_trust.verify", "device_trust.lifecycle"}.issubset(event_types)
    assert PATIENT_TOKEN not in audit_text
    print("[Device Trust] Structured audit evidence contains no patient token (PASSED)")
    print("\nALL DEVICE TRUST REGRESSION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
