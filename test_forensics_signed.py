import os
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


RUNTIME = tempfile.TemporaryDirectory(prefix="smart-ward-forensic-test-")
ROOT = Path(RUNTIME.name)
PRIVATE_KEY_PATH = ROOT / "forensic-signing-key.pem"
PRIVATE_KEY_PATH.write_bytes(
    rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
)
try:
    PRIVATE_KEY_PATH.chmod(0o400)
except OSError:
    pass
os.environ.update(
    {
        "SW_AUTH_TOKENS_JSON": '{"signed-forensic-test-token":["admin"]}',
        "SW_DATABASE_PATH": str(ROOT / "signed-forensic.db"),
        "SW_TELEMETRY_STATE_PATH": str(ROOT / "telemetry-state.json"),
        "SW_AUDIT_LOG_PATH": str(ROOT / "audit.jsonl"),
        "SW_FORENSIC_ANCHOR_PATH": str(ROOT / "anchors.jsonl"),
        "SW_FORENSIC_SIGNING_PRIVATE_KEY_PATH": str(PRIVATE_KEY_PATH),
        "SW_FORENSIC_SIGNING_REQUIRED": "true",
        "SW_AUTO_CREATE_DB": "true",
        "SW_SEED_DATA": "true",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from database import SessionLocal, engine  # noqa: E402
from main import ACTIVE_PAIRINGS_CACHE, TELEMETRY_STORE, app  # noqa: E402
import models  # noqa: E402


DEVICE_ID = "signed-forensic-device"


def packet(sequence: int, *, accel_z: float = 1.0) -> dict[str, object]:
    return {
        "device_id": DEVICE_ID,
        "sequence": sequence,
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
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    headers = {"Authorization": "Bearer signed-forensic-test-token"}
    with TestClient(app, headers=headers) as client:
        with SessionLocal() as db:
            db.add_all(
                [
                    models.Patient(patient_token="ptok-signed-forensic-demo"),
                    models.Bed(bed_no="SIM-SIGNED-01", ward_id="SIM"),
                    models.Device(device_id=DEVICE_ID),
                ]
            )
            db.commit()
        pairing = client.post(
            "/api/v1/pairing",
            json={
                "patient_token": "ptok-signed-forensic-demo",
                "bed_no": "SIM-SIGNED-01",
                "device_id": DEVICE_ID,
                "risk_level": "High",
            },
        )
        assert pairing.status_code == 200, pairing.text
        assert client.post("/api/v1/telemetry", json=packet(1, accel_z=3.2)).status_code == 200
        for sequence in range(2, 7):
            assert client.post("/api/v1/telemetry", json=packet(sequence)).status_code == 200

        verified = client.get("/api/v1/forensics/verify")
        assert verified.status_code == 200
        body = verified.json()
        assert body["integrity"] == "OK"
        assert body["all_packages_signed_and_verified"] is True
        assert body["signature_status"][0]["status"] == "SIGNED_VERIFIED"

        with SessionLocal() as db:
            package = db.query(models.ForensicPackage).one()
            assert package.signature_algorithm == "RSA-PSS-SHA256"
            assert package.signature_status == "SIGNED"
            assert package.signed_at is not None
            package.signature_b64 = "AAAA"
            db.commit()
        tampered = client.get("/api/v1/forensics/verify")
        assert tampered.json()["integrity"] == "FAILED"
        assert "signature" in tampered.json()["detail"].lower()
    engine.dispose()
    RUNTIME.cleanup()
    print("[Medical Black Box] Signed alert freeze and signature tamper detection: PASSED")
    print("SIGNED_FORENSICS_TESTS_PASSED")


if __name__ == "__main__":
    run()
