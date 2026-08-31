from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path

from system_identity import DEFAULT_DATABASE_FILENAME, PRODUCT_NAME, SYSTEM_NAME, SYSTEM_VERSION
import gcp_secrets

TRUE_VALUES = {"1", "true", "yes", "on"}


def _get_setting(name: str, default: str | None = None) -> str | None:
    return gcp_secrets.get_secret(name, default)


def _bool_env(name: str, default: bool) -> bool:
    value = _get_setting(name)
    return default if value is None else value.strip().lower() in TRUE_VALUES


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = _get_setting(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _token_config() -> dict[str, set[str]]:
    raw = _get_setting("SW_AUTH_TOKENS_JSON", "").strip()
    if not raw:
        # Default local developer/simulation token
        return {"test-token": {"admin", "telemetry:read", "telemetry:write", "pairing:write"}}
    try:
        parsed: dict[str, list[str]] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("SW_AUTH_TOKENS_JSON must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("SW_AUTH_TOKENS_JSON must contain an object")
    return {str(token): set(map(str, scopes)) for token, scopes in parsed.items()}


def _token_hashes_config() -> dict[str, set[str]]:
    raw = _get_setting("SW_AUTH_TOKEN_HASHES_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed: dict[str, list[str]] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("SW_AUTH_TOKEN_HASHES_JSON must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("SW_AUTH_TOKEN_HASHES_JSON must contain an object")
    return {str(token_hash).lower(): set(map(str, scopes)) for token_hash, scopes in parsed.items()}


@dataclass(frozen=True)
class Settings:
    environment: str
    product_name: str
    product_short_name: str
    product_description: str
    auto_create_db: bool
    seed_data: bool
    database_path: Path
    telemetry_state_path: Path
    telemetry_checkpoint_every: int
    telemetry_buffer_max_samples: int
    telemetry_max_devices: int
    telemetry_max_sample_bytes: int
    telemetry_memory_alarm_ratio: float
    sqlite_busy_timeout_ms: int
    sqlite_synchronous: str
    enable_docs: bool
    allowed_hosts: list[str]
    allowed_origins: list[str]
    auth_mode: str
    auth_tokens: dict[str, set[str]]
    auth_token_hashes: dict[str, set[str]]
    local_bootstrap_token: str | None
    oidc_issuer: str | None
    oidc_audience: str | None
    oidc_jwks_url: str | None
    oidc_algorithms: list[str]
    rate_limit_per_minute: int
    audit_log_path: Path
    idempotency_ttl_seconds: int
    forensic_anchor_path: Path | None
    forensic_window_seconds: int
    forensic_signing_private_key_path: Path | None
    forensic_signing_required: bool
    device_trust_mode: str
    device_trust_clock_skew_seconds: int


def load_settings() -> Settings:
    project_dir = Path(__file__).resolve().parent
    environment = _get_setting("SW_ENVIRONMENT", "development").lower()
    database_path = Path(
        _get_setting("SW_DATABASE_PATH", str(project_dir / DEFAULT_DATABASE_FILENAME))
    ).expanduser()
    state_path = Path(
        _get_setting("SW_TELEMETRY_STATE_PATH", str(project_dir / "edge_telemetry_state.json"))
    ).expanduser()
    audit_path = Path(
        _get_setting("SW_AUDIT_LOG_PATH", str(project_dir / "audit_events.jsonl"))
    ).expanduser()
    anchor_raw = _get_setting("SW_FORENSIC_ANCHOR_PATH", "").strip()
    anchor_path = Path(anchor_raw).expanduser() if anchor_raw else None
    signing_key_raw = _get_setting("SW_FORENSIC_SIGNING_PRIVATE_KEY_PATH", "").strip()
    signing_key_path = Path(signing_key_raw).expanduser() if signing_key_raw else None
    signing_required = _bool_env("SW_FORENSIC_SIGNING_REQUIRED", False)
    forensic_window_seconds = int(_get_setting("SW_FORENSIC_WINDOW_SECONDS", "600"))
    if forensic_window_seconds <= 0:
        raise RuntimeError("SW_FORENSIC_WINDOW_SECONDS must be positive")
    if signing_required and signing_key_path is None:
        raise RuntimeError(
            "SW_FORENSIC_SIGNING_REQUIRED requires SW_FORENSIC_SIGNING_PRIVATE_KEY_PATH"
        )
    if signing_key_path is not None and signing_key_path.exists() and os.name != "nt":
        st = signing_key_path.stat()
        if st.st_mode & 0o077:
            raise RuntimeError(
                f"Forensic signing key {signing_key_path} is group/other accessible; chmod 0400 required"
            )
    device_trust_mode = _get_setting("SW_DEVICE_TRUST_MODE", "disabled").lower()
    if device_trust_mode not in {"disabled", "observe", "enforce"}:
        raise RuntimeError("SW_DEVICE_TRUST_MODE must be disabled, observe, or enforce")
    auth_mode = _get_setting("SW_AUTH_MODE", "static").lower()
    allow_static_nonlocal = _bool_env("SW_ALLOW_STATIC_AUTH_IN_NONLOCAL", False)
    if environment in {"pilot", "production", "prod"} and auth_mode == "static" and not allow_static_nonlocal:
        raise RuntimeError(
            "Static authentication is disabled for pilot/production; configure SW_AUTH_MODE=oidc"
        )
    rate_limit_per_minute = int(_get_setting("SW_RATE_LIMIT_PER_MINUTE", "6000"))
    if environment in {"pilot", "production", "prod"} and rate_limit_per_minute <= 0:
        raise RuntimeError("SW_RATE_LIMIT_PER_MINUTE must be positive for pilot/production")
    synchronous = _get_setting("SW_SQLITE_SYNCHRONOUS", "FULL").upper()
    if synchronous not in {"OFF", "NORMAL", "FULL", "EXTRA"}:
        raise RuntimeError("SW_SQLITE_SYNCHRONOUS must be OFF, NORMAL, FULL, or EXTRA")
    local_bootstrap_token = _get_setting("SW_LOCAL_BOOTSTRAP_TOKEN", "").strip() or None
    return Settings(
        environment=environment,
        product_name=_get_setting("SW_PRODUCT_NAME", SYSTEM_NAME),
        product_short_name=_get_setting("SW_PRODUCT_SHORT_NAME", PRODUCT_NAME),
        product_description=_get_setting(
            "SW_PRODUCT_DESCRIPTION",
            f"{SYSTEM_NAME} / {PRODUCT_NAME} v{SYSTEM_VERSION} - ward-local monitoring and workflow hub",
        ),
        auto_create_db=_bool_env("SW_AUTO_CREATE_DB", environment in {"development", "test"}),
        seed_data=_bool_env("SW_SEED_DATA", environment in {"development", "test"}),
        database_path=database_path,
        telemetry_state_path=state_path,
        telemetry_checkpoint_every=int(_get_setting("SW_TELEMETRY_CHECKPOINT_EVERY", "128")),
        telemetry_buffer_max_samples=int(_get_setting("SW_TELEMETRY_BUFFER_MAX_SAMPLES", "90000")),
        telemetry_max_devices=int(_get_setting("SW_TELEMETRY_MAX_DEVICES", "256")),
        telemetry_max_sample_bytes=int(_get_setting("SW_TELEMETRY_MAX_SAMPLE_BYTES", "16384")),
        telemetry_memory_alarm_ratio=float(_get_setting("SW_TELEMETRY_MEMORY_ALARM_RATIO", "0.90")),
        sqlite_busy_timeout_ms=int(_get_setting("SW_SQLITE_BUSY_TIMEOUT_MS", "5000")),
        sqlite_synchronous=synchronous,
        enable_docs=_bool_env("SW_ENABLE_DOCS", False),
        allowed_hosts=_csv_env("SW_ALLOWED_HOSTS", ["127.0.0.1", "localhost", "testserver"]),
        allowed_origins=_csv_env("SW_ALLOWED_ORIGINS", []),
        auth_mode=auth_mode,
        auth_tokens=_token_config(),
        auth_token_hashes=_token_hashes_config(),
        local_bootstrap_token=local_bootstrap_token,
        oidc_issuer=_get_setting("SW_OIDC_ISSUER"),
        oidc_audience=_get_setting("SW_OIDC_AUDIENCE"),
        oidc_jwks_url=_get_setting("SW_OIDC_JWKS_URL"),
        oidc_algorithms=_csv_env("SW_OIDC_ALGORITHMS", ["RS256"]),
        rate_limit_per_minute=rate_limit_per_minute,
        audit_log_path=audit_path,
        idempotency_ttl_seconds=int(_get_setting("SW_IDEMPOTENCY_TTL_SECONDS", "86400")),
        forensic_anchor_path=anchor_path,
        forensic_window_seconds=forensic_window_seconds,
        forensic_signing_private_key_path=signing_key_path,
        forensic_signing_required=signing_required,
        device_trust_mode=device_trust_mode,
        device_trust_clock_skew_seconds=int(_get_setting("SW_DEVICE_TRUST_CLOCK_SKEW_SECONDS", "30")),
    )


settings = load_settings()
settings.database_path.parent.mkdir(parents=True, exist_ok=True)
settings.telemetry_state_path.parent.mkdir(parents=True, exist_ok=True)
settings.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
if settings.forensic_anchor_path is not None:
    settings.forensic_anchor_path.parent.mkdir(parents=True, exist_ok=True)
