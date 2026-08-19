from pathlib import Path
import os
import subprocess
import sys
import tempfile


def run() -> None:
    project_dir = Path(__file__).resolve().parent
    env = os.environ.copy()
    env["SW_AUTH_MODE"] = "oidc"
    env.pop("SW_OIDC_ISSUER", None)
    env.pop("SW_OIDC_AUDIENCE", None)
    env.pop("SW_OIDC_JWKS_URL", None)
    oidc_probe = subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert oidc_probe.returncode != 0
    assert "OIDC mode requires" in (oidc_probe.stderr + oidc_probe.stdout)
    print("[P0] Missing OIDC configuration fails closed: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "migration.db"
        migration_env = env.copy()
        migration_env["SW_AUTH_MODE"] = "static"
        migration_env["SW_DATABASE_PATH"] = str(database_path)
        migration_env.pop("SW_AUTH_TOKENS_JSON", None)
        upgrade = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_dir,
            env=migration_env,
            capture_output=True,
            text=True,
        )
        assert upgrade.returncode == 0, upgrade.stderr
        current = subprocess.run(
            ["alembic", "current"],
            cwd=project_dir,
            env=migration_env,
            capture_output=True,
            text=True,
        )
        assert current.returncode == 0, current.stderr
        assert "head" in current.stdout
        pilot_env = migration_env.copy()
        pilot_env["SW_ENVIRONMENT"] = "pilot"
        pilot_env["SW_AUTO_CREATE_DB"] = "false"
        pilot_env["SW_SEED_DATA"] = "false"
        pilot_env["SW_AUTH_TOKENS_JSON"] = '{"pilot-token":["admin"]}'
        pilot_env["SW_TELEMETRY_STATE_PATH"] = str(Path(directory) / "state.json")
        startup_probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "from fastapi.testclient import TestClient; from main import app; c=TestClient(app); r=c.get('/health'); print(r.json())",
            ],
            cwd=project_dir,
            env=pilot_env,
            capture_output=True,
            text=True,
        )
        assert startup_probe.returncode == 0, startup_probe.stderr
        assert "external_migration_required" in startup_probe.stdout
    print("[P0] Alembic clean-database upgrade reaches head: PASSED")
    print("[P0] Migration-first pilot startup without demo seed: PASSED")
    print("P0 HARDENING TESTS PASSED")


if __name__ == "__main__":
    run()
