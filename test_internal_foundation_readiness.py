from __future__ import annotations

from pathlib import Path
import tempfile

from internal_foundation_readiness import AUTHORIZATION_BOUNDARY, evaluate_internal_foundation
from schemas import TelemetryPacket


ROOT = Path(__file__).resolve().parent


def valid_environment(root: Path) -> dict[str, str]:
    return {
        "SW_ENVIRONMENT": "pilot",
        "SW_AUTO_CREATE_DB": "false",
        "SW_SEED_DATA": "false",
        "SW_ENABLE_DOCS": "false",
        "SW_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "SW_AUTH_MODE": "oidc",
        "SW_OIDC_ISSUER": "https://idp.example.org/",
        "SW_OIDC_AUDIENCE": "smart-ward-hub",
        "SW_OIDC_JWKS_URL": "https://idp.example.org/.well-known/jwks.json",
        "SW_DATABASE_PATH": "/var/lib/smart-ward-hub/ward_hub.db",
        "SW_TELEMETRY_STATE_PATH": "/var/lib/smart-ward-hub/edge_telemetry_state.json",
        "SW_AUDIT_LOG_PATH": "/var/log/smart-ward-hub/audit_events.jsonl",
        "SW_TELEMETRY_CHECKPOINT_EVERY": "128",
        "SW_TELEMETRY_BUFFER_MAX_SAMPLES": "90000",
        "SW_TELEMETRY_MAX_DEVICES": "256",
        "SW_TELEMETRY_MAX_SAMPLE_BYTES": "16384",
        "SW_TELEMETRY_MEMORY_ALARM_RATIO": "0.90",
        "SW_SQLITE_BUSY_TIMEOUT_MS": "5000",
        "SW_RATE_LIMIT_PER_MINUTE": "6000",
        "SW_IDEMPOTENCY_TTL_SECONDS": "86400",
        "SW_DEVICE_TRUST_CLOCK_SKEW_SECONDS": "30",
        "SW_DEVICE_TRUST_MODE": "observe",
    }


def check(result: dict[str, object], name: str) -> dict[str, str]:
    return next(item for item in result["checks"] if item["check"] == name)


def expect_status(env: dict[str, str], expected: str, label: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result = evaluate_internal_foundation(env, project_root=root)
        assert result["status"] == expected, (label, result)
    print(f"[Foundation] {label}: PASSED")


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result = evaluate_internal_foundation(valid_environment(root), project_root=root)
        assert result["status"] == "PASS", result
        assert result["software_only"] is True
        assert result["physical_validation"] == "UNVERIFIED"
        assert result["clinical_validation"] == "PENDING"
        assert result["authorization_boundary"] == AUTHORIZATION_BOUNDARY
        assert check(result, "runtime_artifact_hygiene")["status"] == "PASS"
        assert check(result, "private_material_scan")["status"] == "PASS"
        print("[Foundation] valid pilot baseline and locked boundary: PASSED")

        bad = valid_environment(root)
        bad["SW_TELEMETRY_BUFFER_MAX_SAMPLES"] = "0"
        bad["SW_TELEMETRY_MAX_SAMPLE_BYTES"] = "128"
        bad["SW_TELEMETRY_MEMORY_ALARM_RATIO"] = "1.1"
        bad["SW_RATE_LIMIT_PER_MINUTE"] = "not-an-integer"
        result = evaluate_internal_foundation(bad, project_root=root)
        assert result["status"] == "FAIL"
        assert check(result, "SW_TELEMETRY_BUFFER_MAX_SAMPLES")["status"] == "FAIL"
        assert check(result, "SW_TELEMETRY_MAX_SAMPLE_BYTES")["status"] == "FAIL"
        assert check(result, "SW_TELEMETRY_MEMORY_ALARM_RATIO")["status"] == "FAIL"
        assert check(result, "SW_RATE_LIMIT_PER_MINUTE")["status"] == "FAIL"
        print("[Foundation] invalid numeric bounds fail closed: PASSED")

        bad = valid_environment(root)
        bad["SW_ALLOWED_HOSTS"] = "*"
        bad["SW_DATABASE_PATH"] = str(root / "ward_hub.db")
        result = evaluate_internal_foundation(bad, project_root=root)
        assert result["status"] == "FAIL"
        assert check(result, "allowed_hosts")["status"] == "FAIL"
        assert check(result, "path:SW_DATABASE_PATH")["status"] == "FAIL"
        print("[Foundation] wildcard exposure and source-tree runtime path fail closed: PASSED")

        bad = valid_environment(root)
        bad["SW_AUTH_MODE"] = "static"
        bad["SW_AUTH_TOKENS_JSON"] = '{"local-token":["admin"]}'
        result = evaluate_internal_foundation(bad, project_root=root)
        assert result["status"] == "ADVISORY"
        assert check(result, "auth_mode")["status"] == "ADVISORY"
        assert check(result, "secret_source")["status"] == "ADVISORY"
        print("[Foundation] static token remains advisory, not approval: PASSED")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ward_hub.db").write_text("runtime", encoding="utf-8")
            result = evaluate_internal_foundation(valid_environment(root), project_root=root)
            assert result["status"] == "FAIL"
            assert check(result, "runtime_artifact_hygiene")["status"] == "FAIL"
        print("[Foundation] runtime artifact residue fails closed: PASSED")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = "-----BEGIN " + "PRIVATE" + " KEY-----"
            (root / "unsafe.md").write_text(marker + "\nredacted\n", encoding="utf-8")
            result = evaluate_internal_foundation(valid_environment(root), project_root=root)
            assert result["status"] == "FAIL"
            assert check(result, "private_material_scan")["status"] == "FAIL"
        print("[Foundation] private-key marker fails closed: PASSED")

        packet = TelemetryPacket(
            device_id="MAC-A1:B2:C3",
            sequence=1,
            ppg=70.0,
            accel_x=0.0,
            accel_y=0.0,
            accel_z=1.0,
            skin_temp=36.5,
            battery_pct=90.0,
        )
        assert packet.device_id == "MAC-A1:B2:C3"
        try:
            TelemetryPacket(
                device_id="device/with/slash",
                sequence=1,
                ppg=70.0,
                accel_x=0.0,
                accel_y=0.0,
                accel_z=1.0,
                skin_temp=36.5,
                battery_pct=90.0,
            )
        except Exception:
            pass
        else:
            raise AssertionError("malformed device_id was accepted")
        print("[Foundation] canonical device_id schema boundary: PASSED")

        result = evaluate_internal_foundation(valid_environment(ROOT), project_root=ROOT)
        assert result["authorization_boundary"] == {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        }
        print("[Foundation] repository baseline has no authorization promotion: PASSED")

    print("INTERNAL_FOUNDATION_READINESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
