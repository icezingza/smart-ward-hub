from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from edge_runtime import EdgeTelemetryStore


def sample(sequence: int) -> dict:
    return {
        "sequence": sequence,
        "ppg": 70.0,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 1.0,
        "battery_pct": 90.0,
    }


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        state_path = root / "edge-state.json"
        store = EdgeTelemetryStore(max_samples=4, state_path=state_path, checkpoint_every=1)
        assert store.append("device-recovery", sample(1), 1).accepted
        assert store.append("device-recovery", sample(2), 2).accepted
        store.persist()

        recovered = EdgeTelemetryStore(max_samples=4, state_path=state_path, checkpoint_every=1)
        assert recovered.last_sequence("device-recovery") == 2
        assert [item["sequence"] for item in recovered.snapshot("device-recovery")] == [1, 2]
        print("[P0-004] Atomic checkpoint restart recovery: PASSED")

        state_path.write_text("{corrupt-checkpoint", encoding="utf-8")
        safe_after_corruption = EdgeTelemetryStore(max_samples=4, state_path=state_path, checkpoint_every=1)
        assert safe_after_corruption.snapshot("device-recovery") == []
        assert safe_after_corruption.last_sequence("device-recovery") is None
        print("[P0-004] Corrupt checkpoint fails safe without restoring stale state: PASSED")

        database_path = root / "recovery.db"
        connection = sqlite3.connect(database_path)
        try:
            journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("CREATE TABLE recovery_probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO recovery_probe(value) VALUES (?)", ("durable-fixture",))
            connection.commit()
        finally:
            connection.close()
        assert str(journal_mode).lower() == "wal"
        connection = sqlite3.connect(database_path)
        try:
            assert connection.execute("SELECT value FROM recovery_probe WHERE id = 1").fetchone()[0] == "durable-fixture"
        finally:
            connection.close()
        print("[P0-004] SQLite WAL + synchronous FULL reopen check: PASSED")

    print("REAL_POWER_CUT_DISK_FULL_FILESYSTEM_CORRUPTION=UNVERIFIED")
    print("P0_RECOVERY_SOFTWARE_HARNESS_PASSED")


if __name__ == "__main__":
    run()
