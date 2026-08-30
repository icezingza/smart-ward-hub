"""Validate local mTLS launcher inputs without opening certificate or private-key contents.

A successful run proves only local file/configuration hygiene. It does not prove a
successful mutual TLS handshake, certificate-chain trust, renewal, revocation, or
hospital network segmentation.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


def _private_key_is_safe(path: Path) -> tuple[bool, str]:
    if os.name != "nt":
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
            return False, "private key is group/other accessible"
        return True, f"present mode={mode:04o}"

    # chmod mode bits are not authoritative on NTFS. Require an explicit ACL and
    # reject common broad principals before a local launcher can use the key.
    acl = subprocess.run(["icacls", str(path)], capture_output=True, text=True, check=False)
    if acl.returncode != 0:
        return False, "unable to inspect Windows ACL"
    output = f"{acl.stdout}\n{acl.stderr}".lower()
    broad_principals = ("everyone", "authenticated users", "builtin\\users", "codexsandboxusers", "s-1-5-32-545")
    if "(i)" in output:
        return False, "private key has inherited ACL entries"
    if any(principal in output for principal in broad_principals):
        return False, "private key is group/other accessible"
    return True, "present with explicit Windows ACL"


def _path_check(name: str, require_private_mode: bool = False) -> tuple[bool, str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return False, "missing"
    path = Path(raw).expanduser()
    if not path.is_file():
        return False, "file not found"
    if require_private_mode:
        return _private_key_is_safe(path)
    mode = stat.S_IMODE(path.stat().st_mode)
    return True, f"present mode={mode:04o}"


def main() -> int:
    checks = [
        ("SW_MTLS_CERTFILE", *_path_check("SW_MTLS_CERTFILE")),
        ("SW_MTLS_KEYFILE", *_path_check("SW_MTLS_KEYFILE", require_private_mode=True)),
        ("SW_MTLS_CA_CERTS", *_path_check("SW_MTLS_CA_CERTS")),
    ]
    for name, ok, detail in checks:
        print(f"[MTLS-CONFIG] {name}: {'PASS' if ok else 'FAIL'} ({detail})")
    if all(ok for _, ok, _ in checks):
        print("MTLS_LOCAL_CONFIGURATION_VALID")
        print("LIVE_HANDSHAKE_ROTATION_REVOCATION_AND_SEGMENTATION=UNVERIFIED")
        return 0
    print("MTLS_LOCAL_CONFIGURATION_INVALID_FAIL_CLOSED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
