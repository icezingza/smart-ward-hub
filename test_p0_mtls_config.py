from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SCRIPT = PROJECT_DIR / "validate_mtls_config.py"


def run_probe(env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name, value in env_overrides.items():
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
    missing = run_probe(
        {
            "SW_MTLS_CERTFILE": None,
            "SW_MTLS_KEYFILE": None,
            "SW_MTLS_CA_CERTS": None,
        }
    )
    assert missing.returncode == 1
    assert "MTLS_LOCAL_CONFIGURATION_INVALID_FAIL_CLOSED" in missing.stdout
    print("[P0] mTLS missing file configuration fails closed: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        cert = root / "server.crt"
        key = root / "server.key"
        ca = root / "ca.crt"
        cert.write_text("certificate-fixture\n")
        key.write_text("private-key-fixture\n")
        ca.write_text("ca-fixture\n")
        cert.chmod(0o644)
        key.chmod(0o600)
        ca.chmod(0o644)
        valid = run_probe(
            {
                "SW_MTLS_CERTFILE": str(cert),
                "SW_MTLS_KEYFILE": str(key),
                "SW_MTLS_CA_CERTS": str(ca),
            }
        )
        assert valid.returncode == 0
        assert "MTLS_LOCAL_CONFIGURATION_VALID" in valid.stdout
        assert "LIVE_HANDSHAKE_ROTATION_REVOCATION_AND_SEGMENTATION=UNVERIFIED" in valid.stdout
        print("[P0] mTLS local file hygiene validates without reading key material: PASSED")

        key.chmod(stat.S_IRUSR | stat.S_IRGRP)
        unsafe = run_probe(
            {
                "SW_MTLS_CERTFILE": str(cert),
                "SW_MTLS_KEYFILE": str(key),
                "SW_MTLS_CA_CERTS": str(ca),
            }
        )
        assert unsafe.returncode == 1
        assert "private key is group/other accessible" in unsafe.stdout
        print("[P0] mTLS group-readable private key rejected: PASSED")


if __name__ == "__main__":
    run()
