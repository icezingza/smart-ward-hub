from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SCRIPT = PROJECT_DIR / "validate_oidc_config.py"


def run_probe(overrides: dict[str, str | None]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name, value in overrides.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def run() -> None:
    invalid = run_probe(
        {
            "SW_AUTH_MODE": "oidc",
            "SW_OIDC_ISSUER": None,
            "SW_OIDC_AUDIENCE": None,
            "SW_OIDC_JWKS_URL": None,
        }
    )
    assert invalid.returncode == 1
    assert "OIDC_LOCAL_CONFIGURATION_INVALID_FAIL_CLOSED" in invalid.stdout
    print("[P0] OIDC missing configuration fails closed: PASSED")

    valid = run_probe(
        {
            "SW_AUTH_MODE": "oidc",
            "SW_OIDC_ISSUER": "https://idp.example.test/",
            "SW_OIDC_AUDIENCE": "smart-ward-hub",
            "SW_OIDC_JWKS_URL": "https://idp.example.test/.well-known/jwks.json",
            "SW_OIDC_ALGORITHMS": "RS256",
        }
    )
    assert valid.returncode == 0
    assert "OIDC_LOCAL_CONFIGURATION_VALID" in valid.stdout
    assert "LIVE_IDP_JWKS_ROTATION_AND_REVOCATION=UNVERIFIED" in valid.stdout
    print("[P0] OIDC local configuration contract validates without overclaiming live IdP evidence: PASSED")


if __name__ == "__main__":
    run()
