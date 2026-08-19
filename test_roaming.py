import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ward_hub.db"
AUDIT_PATH = Path("/tmp/smart-ward-hub-roaming-audit.jsonl")
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
from main import ACTIVE_PAIRINGS_CACHE, RATE_LIMITER, TELEMETRY_STORE, app
import models

DEVICE_A = "MAC-A1:B2:C3:D4:E5:F6"
TOKEN_A = "ptok-hn-2026-8901-demo"


def run() -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    TELEMETRY_STORE.clear()
    RATE_LIMITER.clear()
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(app, headers=headers) as client:
        paired = client.post(
            "/api/v1/pairing",
            json={"patient_token": TOKEN_A, "bed_no": "W04-B12", "device_id": DEVICE_A},
        )
        assert paired.status_code == 200, paired.text
        session_id = paired.json()["data"]["session_id"]

        initial = client.get("/api/v1/roaming/snapshot", params={"tablet_id": "bmax-roaming-01"})
        assert initial.status_code == 200, initial.text
        initial_data = initial.json()["data"]
        assert initial_data["source"] == "fixed-edge-hub"
        assert isinstance(initial_data["revision"], int)
        assert any(row["bed_no"] == "W04-B12" and row["availability_state"] == "OCCUPIED" for row in initial_data["beds"])
        assert TOKEN_A not in json.dumps(initial.json())
        revision = initial_data["revision"]
        print("[Roaming] Authenticated non-PII snapshot exposes authoritative bed/session state (PASSED)")

        unchanged = client.get(
            "/api/v1/roaming/snapshot",
            params={"tablet_id": "bmax-roaming-01", "since_revision": revision},
        )
        assert unchanged.status_code == 200, unchanged.text
        assert unchanged.json()["data"]["unchanged"] is True
        assert unchanged.json()["data"]["beds"] == []
        print("[Roaming] Cursor/revision snapshot returns no-change response (PASSED)")

        stale = client.post(
            "/api/v1/roaming/commands",
            json={
                "command_type": "RESET_REQUEST",
                "command_id": "roaming-cmd-stale-01",
                "idempotency_key": "roaming-idem-stale-01",
                "tablet_id": "bmax-roaming-01",
                "expected_revision": max(0, revision - 1),
                "session_id": session_id,
            },
        )
        assert stale.status_code == 409, stale.text
        assert stale.json()["detail"]["error_code"] == "STALE_REVISION"
        print("[Roaming] Stale tablet revision cannot mutate Fixed Hub state (PASSED)")

        with SessionLocal() as db:
            alert = models.Alert(
                device_id=DEVICE_A,
                session_id=session_id,
                bed_no="W04-B12",
                patient_token=TOKEN_A,
                alert_level="YELLOW",
                alert_type="test",
                description="synthetic test alert",
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            alert_id = alert.id

        alert_snapshot = client.get(
            "/api/v1/roaming/snapshot",
            params={"tablet_id": "bmax-roaming-01", "since_revision": revision},
        )
        assert alert_snapshot.status_code == 200, alert_snapshot.text
        alert_data = alert_snapshot.json()["data"]
        current_revision = alert_data["revision"]
        assert any(row["alert_id"] == alert_id and row["acknowledged"] is False for row in alert_data["alerts"])

        ack = client.post(
            "/api/v1/roaming/commands",
            json={
                "command_type": "ACK_ALERT",
                "command_id": "roaming-cmd-ack-01",
                "idempotency_key": "roaming-idem-ack-01",
                "tablet_id": "bmax-roaming-01",
                "expected_revision": current_revision,
                "session_id": session_id,
                "alert_id": alert_id,
            },
        )
        assert ack.status_code == 200, ack.text
        assert ack.json()["data"]["status"] == "COMMITTED"
        print("[Roaming] Alert acknowledgement commits through the Fixed Hub (PASSED)")

        ack_replay = client.post(
            "/api/v1/roaming/commands",
            json={
                "command_type": "ACK_ALERT",
                "command_id": "roaming-cmd-ack-different",
                "idempotency_key": "roaming-idem-ack-01",
                "tablet_id": "bmax-roaming-01",
                "expected_revision": current_revision,
                "session_id": session_id,
                "alert_id": alert_id,
            },
        )
        assert ack_replay.status_code == 200, ack_replay.text
        assert ack_replay.json()["data"]["idempotent_replay"] is True
        print("[Roaming] Duplicate command replay returns original authoritative result (PASSED)")

        post_ack = client.get(
            "/api/v1/roaming/snapshot",
            params={"tablet_id": "bmax-roaming-01", "since_revision": current_revision},
        )
        assert post_ack.status_code == 200, post_ack.text
        assert any(row["alert_id"] == alert_id and row["acknowledged"] is True for row in post_ack.json()["data"]["alerts"])
        post_ack_revision = post_ack.json()["data"]["revision"]
        guarded_reset = client.post(
            "/api/v1/roaming/commands",
            json={
                "command_type": "RESET_REQUEST",
                "command_id": "roaming-cmd-reset-guard-01",
                "idempotency_key": "roaming-idem-reset-guard-01",
                "tablet_id": "bmax-roaming-01",
                "expected_revision": post_ack_revision,
                "session_id": session_id,
            },
        )
        assert guarded_reset.status_code == 409, guarded_reset.text
        assert guarded_reset.json()["detail"]["error_code"] == "INCIDENT_FREEZE_REQUIRED"
        print("[Roaming] Acknowledgement does not bypass unresolved-incident reset gate (PASSED)")

        with SessionLocal() as db:
            db.query(models.Alert).filter(models.Alert.id == alert_id).update({"is_resolved": True})
            db.commit()
        resolved_snapshot = client.get(
            "/api/v1/roaming/snapshot",
            params={"tablet_id": "bmax-roaming-01", "since_revision": post_ack_revision},
        )
        assert resolved_snapshot.status_code == 200, resolved_snapshot.text
        new_revision = resolved_snapshot.json()["data"]["revision"]

        reset = client.post(
            "/api/v1/roaming/commands",
            json={
                "command_type": "RESET_REQUEST",
                "command_id": "roaming-cmd-reset-01",
                "idempotency_key": "roaming-idem-reset-01",
                "tablet_id": "bmax-roaming-01",
                "expected_revision": new_revision,
                "session_id": session_id,
            },
        )
        assert reset.status_code == 200, reset.text
        assert reset.json()["data"]["result"]["status"] == "RESET_PENDING"
        print("[Roaming] Safe RESET_REQUEST enters RESET_PENDING while keeping Hub authority (PASSED)")

        confirm = client.post(
            "/api/v1/roaming/commands",
            json={
                "command_type": "RESET_CONFIRM",
                "command_id": "roaming-cmd-reset-confirm-01",
                "idempotency_key": "roaming-idem-reset-confirm-01",
                "tablet_id": "bmax-roaming-01",
                "expected_revision": reset.json()["data"]["current_revision"],
                "session_id": session_id,
            },
        )
        assert confirm.status_code == 409, confirm.text
        assert confirm.json()["detail"]["error_code"] == "LIVE_FIXED_HUB_CONFIRMATION_REQUIRED"
        print("[Roaming] Destructive RESET_CONFIRM is blocked from roaming tablet in initial pilot (PASSED)")

    audit = AUDIT_PATH.read_text(encoding="utf-8") if AUDIT_PATH.exists() else ""
    assert TOKEN_A not in audit
    print("[Roaming] Roaming command audit contains no raw patient token (PASSED)")
    print("ALL ROAMING TABLET SYNCHRONIZATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run()
