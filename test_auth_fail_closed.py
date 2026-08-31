import os
from pathlib import Path

os.environ["SW_AUTH_TOKENS_JSON"] = "{}"
os.environ["SW_AUTH_TOKEN_HASHES_JSON"] = "{}"

DB_PATH = Path(__file__).resolve().parent / "ward_hub.db"
for suffix in ("", "-wal", "-shm"):
    path = Path(f"{DB_PATH}{suffix}")
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass

from fastapi.testclient import TestClient

from main import app


def run() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/pairing",
            json={
                "patient_token": "ptok-hn-2026-8901-demo",
                "bed_no": "W04-B12",
                "device_id": "MAC-A1:B2:C3:D4:E5:F6",
            },
        )
        assert response.status_code == 503
        print("[Security] Unconfigured authentication fails closed: PASSED")


if __name__ == "__main__":
    run()
