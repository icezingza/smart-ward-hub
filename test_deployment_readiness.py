from __future__ import annotations

from pathlib import Path

from deployment_readiness import validate_environment


ROOT = Path(__file__).resolve().parent


def valid_environment() -> dict[str, str]:
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
        "SW_DEVICE_TRUST_MODE": "observe",
    }


def run() -> None:
    result = validate_environment(valid_environment(), project_root=ROOT)
    assert result.status == "PASS", result
    assert result.physical_validation == "UNVERIFIED"
    assert result.clinical_validation == "PENDING"
    print("[Deployment] Pilot OIDC/loopback/path-separation baseline passes: PASSED")

    bad = valid_environment()
    bad["SW_AUTO_CREATE_DB"] = "true"
    bad["SW_ALLOWED_HOSTS"] = "0.0.0.0,*"
    bad["SW_DATABASE_PATH"] = str(ROOT / "ward_hub.db")
    failed = validate_environment(bad, project_root=ROOT)
    assert failed.status == "FAIL"
    print("[Deployment] Unsafe auto-create, wildcard host and source-tree path fail closed: PASSED")

    static = valid_environment()
    static["SW_AUTH_MODE"] = "static"
    static["SW_AUTH_TOKENS_JSON"] = '{"local-token":["admin"]}'
    advisory = validate_environment(static, project_root=ROOT)
    assert advisory.status == "ADVISORY"
    print("[Deployment] Static token configuration remains advisory, not pilot approval: PASSED")
    print("DEPLOYMENT_READINESS_TESTS_PASSED")


if __name__ == "__main__":
    run()
