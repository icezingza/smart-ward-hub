"""Validate Smart Ward OIDC configuration without contacting or trusting a live IdP.

This tool verifies local configuration shape only. A successful run is not evidence of
issuer availability, JWKS rotation, token acceptance, role mapping, or revocation.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _required(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _https_url(name: str, value: str | None) -> Check:
    if value is None:
        return Check(name, False, "missing")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return Check(name, False, "must be an absolute https URL")
    return Check(name, True, "configured")


def collect_checks() -> list[Check]:
    mode = os.getenv("SW_AUTH_MODE", "static").strip().lower()
    checks = [Check("SW_AUTH_MODE", mode == "oidc", mode)]
    issuer = _required("SW_OIDC_ISSUER")
    audience = _required("SW_OIDC_AUDIENCE")
    jwks_url = _required("SW_OIDC_JWKS_URL")
    checks.extend(
        [
            Check("SW_OIDC_ISSUER", issuer is not None, "configured" if issuer else "missing"),
            Check("SW_OIDC_AUDIENCE", audience is not None, "configured" if audience else "missing"),
            _https_url("SW_OIDC_JWKS_URL", jwks_url),
        ]
    )
    algorithms = [item.strip().upper() for item in os.getenv("SW_OIDC_ALGORITHMS", "RS256").split(",") if item.strip()]
    safe_algorithms = bool(algorithms) and "NONE" not in algorithms and all(item in {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"} for item in algorithms)
    checks.append(Check("SW_OIDC_ALGORITHMS", safe_algorithms, ",".join(algorithms) if algorithms else "missing"))
    return checks


def main() -> int:
    checks = collect_checks()
    for check in checks:
        print(f"[OIDC-CONFIG] {check.name}: {'PASS' if check.ok else 'FAIL'} ({check.detail})")
    if all(check.ok for check in checks):
        print("OIDC_LOCAL_CONFIGURATION_VALID")
        print("LIVE_IDP_JWKS_ROTATION_AND_REVOCATION=UNVERIFIED")
        return 0
    print("OIDC_LOCAL_CONFIGURATION_INVALID_FAIL_CLOSED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
