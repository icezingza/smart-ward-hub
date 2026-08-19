import json
import os
from pathlib import Path
from datetime import timedelta

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ward_hub.db"
AUDIT_PATH = Path("/tmp/smart-ward-hub-outside-admission-audit.jsonl")
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
from starlette.requests import Request

from database import SessionLocal
from main import ACTIVE_PAIRINGS_CACHE, RATE_LIMITER, TELEMETRY_STORE, app, outside_admission_page, require_local_kiosk, utc_now
import models

DEVICE_A = "MAC-A1:B2:C3:D4:E5:F6"
TOKEN_A = "ptok-hn-2026-8901-demo"
TOKEN_B = "ptok-hn-2026-8902-demo"


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    RATE_LIMITER.clear()
    headers = {"Authorization": "Bearer test-token"}
    local_request = Request({
        "type": "http",
        "method": "GET",
        "path": "/admission",
        "raw_path": b"/admission",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 54321),
        "server": ("127.0.0.1", 8080),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
    })
    assert require_local_kiosk(local_request)["token_subject"] == "local-tablet-kiosk"
    assert outside_admission_page(local_request).status_code == 200
    with TestClient(app) as kiosk_client:
        assert kiosk_client.get("/admission").status_code == 403
    print("[Outside] Loopback-only Admission Console and bed snapshot are reachable (PASSED)")

    with TestClient(app, headers=headers) as client:
        snapshot = client.get("/api/v1/outside/bed-availability")
        assert snapshot.status_code == 200, snapshot.text
        beds = {row["bed_no"]: row for row in snapshot.json()["data"]["beds"]}
        assert beds["W04-B12"]["availability_state"] == "AVAILABLE"
        assert "patient_token" not in json.dumps(snapshot.json())
        print("[Outside] Non-PII authoritative bed availability snapshot (PASSED)")

        raw_hn = client.post(
            "/api/v1/outside/admission-preparations",
            json={
                "patient_token": "HN-2026-123456",
                "bed_no": "W04-B12",
                "idempotency_key": "outside-raw-hn-1",
                "source_console_id": "outside-console-01",
            },
        )
        assert raw_hn.status_code == 422
        print("[Outside] Raw HN admission preparation rejected at boundary (PASSED)")

        prepared = client.post(
            "/api/v1/outside/admission-preparations",
            json={
                "patient_token": TOKEN_A,
                "bed_no": "W04-B12",
                "idempotency_key": "outside-admission-001",
                "source_console_id": "outside-console-01",
                "expires_in_seconds": 60,
            },
        )
        assert prepared.status_code == 200, prepared.text
        prepared_data = prepared.json()["data"]
        assert prepared_data["status"] == "PREPARED"
        assert prepared_data["availability_state"] == "RESERVED"
        admission_id = prepared_data["admission_id"]
        print("[Outside] Admission preparation reserves a bed without exposing patient token (PASSED)")

        duplicate = client.post(
            "/api/v1/outside/admission-preparations",
            json={
                "patient_token": TOKEN_A,
                "bed_no": "W04-B12",
                "idempotency_key": "outside-admission-001",
                "source_console_id": "outside-console-01",
            },
        )
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["data"]["admission_id"] == admission_id
        print("[Outside] Admission handoff idempotency returns the original authoritative result (PASSED)")

        conflict = client.post(
            "/api/v1/outside/admission-preparations",
            json={
                "patient_token": TOKEN_B,
                "bed_no": "W04-B12",
                "idempotency_key": "outside-admission-002",
                "source_console_id": "outside-console-01",
            },
        )
        assert conflict.status_code == 409
        print("[Outside] Double reservation of one bed rejected (PASSED)")

        paired = client.post(
            "/api/v1/pairing",
            json={"patient_token": TOKEN_A, "bed_no": "W04-B12", "device_id": DEVICE_A},
        )
        assert paired.status_code == 200, paired.text
        assert paired.json()["data"]["admission_status"] == "COMMITTED"
        occupied = client.get("/api/v1/outside/bed-availability")
        occupied_beds = {row["bed_no"]: row for row in occupied.json()["data"]["beds"]}
        assert occupied_beds["W04-B12"]["availability_state"] == "OCCUPIED"
        print("[Outside] Physical pairing commits the prepared admission and marks bed occupied (PASSED)")

        unpair = client.post("/api/v1/unpair", json={"device_id": DEVICE_A})
        assert unpair.status_code == 200, unpair.text
        released = client.get("/api/v1/outside/bed-availability")
        released_beds = {row["bed_no"]: row for row in released.json()["data"]["beds"]}
        assert released_beds["W04-B12"]["availability_state"] == "AVAILABLE"
        print("[Outside] Session close releases bed availability without double registration (PASSED)")

        cleaning = client.post(
            "/api/v1/outside/beds/W04-B13/state",
            json={"state": "CLEANING", "reason": "turnover"},
        )
        assert cleaning.status_code == 200, cleaning.text
        blocked_prepare = client.post(
            "/api/v1/outside/admission-preparations",
            json={
                "patient_token": TOKEN_B,
                "bed_no": "W04-B13",
                "idempotency_key": "outside-admission-cleaning",
                "source_console_id": "outside-console-01",
            },
        )
        assert blocked_prepare.status_code == 409
        print("[Outside] Cleaning state blocks outside admission preparation (PASSED)")

        release_cleaning = client.post(
            "/api/v1/outside/beds/W04-B13/state",
            json={"state": "AVAILABLE", "reason": "cleaning-complete"},
        )
        assert release_cleaning.status_code == 200, release_cleaning.text
        expiring = client.post(
            "/api/v1/outside/admission-preparations",
            json={
                "patient_token": TOKEN_B,
                "bed_no": "W04-B13",
                "idempotency_key": "outside-admission-expiry",
                "source_console_id": "outside-console-01",
            },
        )
        assert expiring.status_code == 200, expiring.text
        with SessionLocal() as db:
            row = db.query(models.AdmissionPreparation).filter(
                models.AdmissionPreparation.admission_id == expiring.json()["data"]["admission_id"],
            ).first()
            row.expires_at = utc_now() - timedelta(seconds=1)
            db.commit()
        after_expiry = client.get("/api/v1/outside/bed-availability")
        after_expiry_beds = {row["bed_no"]: row for row in after_expiry.json()["data"]["beds"]}
        assert after_expiry_beds["W04-B13"]["availability_state"] == "AVAILABLE"
        with SessionLocal() as db:
            status = db.query(models.AdmissionPreparation.status).filter(
                models.AdmissionPreparation.idempotency_key == "outside-admission-expiry",
            ).scalar()
            assert status == "EXPIRED"
        print("[Outside] Expired reservation returns bed to AVAILABLE (PASSED)")

    audit = AUDIT_PATH.read_text(encoding="utf-8") if AUDIT_PATH.exists() else ""
    assert TOKEN_A not in audit
    assert TOKEN_B not in audit
    print("[Outside] Admission audit contains no raw patient token (PASSED)")
    print("ALL OUTSIDE-IN BED AVAILABILITY AND ADMISSION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
