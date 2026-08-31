from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ReadinessResult:
    status: str
    checks: list[dict[str, str]]
    physical_validation: str
    clinical_validation: str


def _check(checks: list[dict[str, str]], name: str, status: str, detail: str) -> None:
    checks.append({"check": name, "status": status, "detail": detail})


def validate_environment(
    env: Mapping[str, str],
    *,
    project_root: Path,
    bind_host: str = "127.0.0.1",
    port: int = 8080,
) -> ReadinessResult:
    checks: list[dict[str, str]] = []
    hard_fail = False
    advisory = False

    if env.get("SW_ENVIRONMENT") == "pilot":
        _check(checks, "environment", "PASS", "SW_ENVIRONMENT=pilot")
    else:
        _check(checks, "environment", "FAIL", "SW_ENVIRONMENT must be pilot")
        hard_fail = True

    for name, expected in (
        ("SW_AUTO_CREATE_DB", "false"),
        ("SW_SEED_DATA", "false"),
        ("SW_ENABLE_DOCS", "false"),
    ):
        if env.get(name, "").lower() == expected:
            _check(checks, name, "PASS", f"{name}={expected}")
        else:
            _check(checks, name, "FAIL", f"{name} must be {expected}")
            hard_fail = True

    if bind_host in {"127.0.0.1", "localhost", "::1"} and 1 <= port <= 65535:
        _check(checks, "loopback_binding", "PASS", f"{bind_host}:{port}")
    else:
        _check(checks, "loopback_binding", "FAIL", "pilot reference service must bind to loopback")
        hard_fail = True

    allowed_hosts = {item.strip() for item in env.get("SW_ALLOWED_HOSTS", "").split(",") if item.strip()}
    if allowed_hosts and "*" not in allowed_hosts and "0.0.0.0" not in allowed_hosts:  # nosec B104
        _check(checks, "allowed_hosts", "PASS", "no wildcard or all-interface host entry")
    else:
        _check(checks, "allowed_hosts", "FAIL", "SW_ALLOWED_HOSTS must be explicit and non-wildcard")
        hard_fail = True

    auth_mode = env.get("SW_AUTH_MODE", "").lower()
    if auth_mode == "oidc":
        _check(checks, "auth_mode", "PASS", "OIDC selected for pilot")
        if env.get("SW_OIDC_ISSUER") and env.get("SW_OIDC_AUDIENCE") and env.get("SW_OIDC_JWKS_URL", "").startswith("https://"):
            _check(checks, "oidc_shape", "PASS", "issuer, audience and HTTPS JWKS shape present")
        else:
            _check(checks, "oidc_shape", "FAIL", "OIDC issuer/audience/HTTPS JWKS are incomplete")
            hard_fail = True
    elif auth_mode == "static":
        _check(checks, "auth_mode", "ADVISORY", "static auth is allowed only for local bench/development")
        advisory = True
    else:
        _check(checks, "auth_mode", "FAIL", "SW_AUTH_MODE must be oidc or static")
        hard_fail = True

    source = project_root.resolve()
    for name in ("SW_DATABASE_PATH", "SW_TELEMETRY_STATE_PATH", "SW_AUDIT_LOG_PATH"):
        raw = env.get(name, "").strip()
        if not raw:
            _check(checks, f"path:{name}", "FAIL", "runtime path is missing")
            hard_fail = True
            continue
        path = Path(raw).expanduser().resolve()
        try:
            path.relative_to(source)
        except ValueError:
            _check(checks, f"path:{name}", "PASS", f"outside source tree: {path}")
        else:
            _check(checks, f"path:{name}", "FAIL", "runtime path must not be inside source tree")
            hard_fail = True

    if env.get("SW_AUTH_TOKENS_JSON"):
        _check(checks, "secret_source", "ADVISORY", "static token material is present in process environment; use a secret store for pilot")
        advisory = True
    else:
        _check(checks, "secret_source", "PASS", "no static token material found in validator input")

    if env.get("SW_DEVICE_TRUST_MODE") in {"observe", "enforce"}:
        _check(checks, "device_trust_stage", "PASS", f"Device Trust staged as {env['SW_DEVICE_TRUST_MODE']}")
    else:
        _check(checks, "device_trust_stage", "ADVISORY", "pilot should stage Device Trust in observe or enforce")
        advisory = True

    status = "FAIL" if hard_fail else "ADVISORY" if advisory else "PASS"
    return ReadinessResult(
        status=status,
        checks=checks,
        physical_validation="UNVERIFIED",
        clinical_validation="PENDING",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Smart Ward Hub pilot deployment configuration")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = validate_environment(dict(os.environ), project_root=args.project_root, bind_host=args.host, port=args.port)
    print(json.dumps({"status": result.status, "checks": result.checks, "physical_validation": result.physical_validation, "clinical_validation": result.clinical_validation}, ensure_ascii=True, indent=2))
    return 0 if result.status != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
