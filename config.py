from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "on"}


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in TRUE_VALUES


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _token_config() -> dict[str, set[str]]:
    raw = os.getenv("SW_AUTH_TOKENS_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed: dict[str, list[str]] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("SW_AUTH_TOKENS_JSON must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("SW_AUTH_TOKENS_JSON must contain an object")
    return {str(token): set(map(str, scopes)) for token, scopes in parsed.items()}


@dataclass(frozen=True)
class Settings:
    environment: str
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
    oidc_issuer: str | None
    oidc_audience: str | None
    oidc_jwks_url: str | None
    oidc_algorithms: list[str]
    rate_limit_per_minute: int
    audit_log_path: Path
    idempotency_ttl_seconds: int
    forensic_anchor_path: Path | None
    device_trust_mode: str
    device_trust_clock_skew_seconds: int


def load_settings() -> Settings:
    project_dir = Path(__file__).resolve().parent
    environment = os.getenv("SW_ENVIRONMENT", "development").lower()
    database_path = Path(os.getenv("SW_DATABASE_PATH", str(project_dir / "ward_hub.db"))).expanduser()
    state_path = Path(
        os.getenv("SW_TELEMETRY_STATE_PATH", str(project_dir / "edge_telemetry_state.json"))
    ).expanduser()
    audit_path = Path(
        os.getenv("SW_AUDIT_LOG_PATH", str(project_dir / "audit_events.jsonl"))
    ).expanduser()
    anchor_raw = os.getenv("SW_FORENSIC_ANCHOR_PATH", "").strip()
    anchor_path = Path(anchor_raw).expanduser() if anchor_raw else None
    device_trust_mode = os.getenv("SW_DEVICE_TRUST_MODE", "disabled").lower()
    if device_trust_mode not in {"disabled", "observe", "enforce"}:
        raise RuntimeError("SW_DEVICE_TRUST_MODE must be disabled, observe, or enforce")
    synchronous = os.getenv("SW_SQLITE_SYNCHRONOUS", "FULL").upper()
    if synchronous not in {"OFF", "NORMAL", "FULL", "EXTRA"}:
        raise RuntimeError("SW_SQLITE_SYNCHRONOUS must be OFF, NORMAL, FULL, or EXTRA")
    return Settings(
        environment=environment,
        auto_create_db=_bool_env("SW_AUTO_CREATE_DB", environment in {"development", "test"}),
        seed_data=_bool_env("SW_SEED_DATA", environment in {"development", "test"}),
        database_path=database_path,
        telemetry_state_path=state_path,
        telemetry_checkpoint_every=int(os.getenv("SW_TELEMETRY_CHECKPOINT_EVERY", "128")),
        telemetry_buffer_max_samples=int(os.getenv("SW_TELEMETRY_BUFFER_MAX_SAMPLES", "90000")),
        telemetry_max_devices=int(os.getenv("SW_TELEMETRY_MAX_DEVICES", "256")),
        telemetry_max_sample_bytes=int(os.getenv("SW_TELEMETRY_MAX_SAMPLE_BYTES", "16384")),
        telemetry_memory_alarm_ratio=float(os.getenv("SW_TELEMETRY_MEMORY_ALARM_RATIO", "0.90")),
        sqlite_busy_timeout_ms=int(os.getenv("SW_SQLITE_BUSY_TIMEOUT_MS", "5000")),
        sqlite_synchronous=synchronous,
        enable_docs=_bool_env("SW_ENABLE_DOCS", False),
        allowed_hosts=_csv_env("SW_ALLOWED_HOSTS", ["127.0.0.1", "localhost", "testserver"]),
        allowed_origins=_csv_env("SW_ALLOWED_ORIGINS", []),
        auth_mode=os.getenv("SW_AUTH_MODE", "static").lower(),
        auth_tokens=_token_config(),
        oidc_issuer=os.getenv("SW_OIDC_ISSUER"),
        oidc_audience=os.getenv("SW_OIDC_AUDIENCE"),
        oidc_jwks_url=os.getenv("SW_OIDC_JWKS_URL"),
        oidc_algorithms=_csv_env("SW_OIDC_ALGORITHMS", ["RS256"]),
        rate_limit_per_minute=int(os.getenv("SW_RATE_LIMIT_PER_MINUTE", "6000")),
        audit_log_path=audit_path,
        idempotency_ttl_seconds=int(os.getenv("SW_IDEMPOTENCY_TTL_SECONDS", "86400")),
        forensic_anchor_path=anchor_path,
        device_trust_mode=device_trust_mode,
        device_trust_clock_skew_seconds=int(os.getenv("SW_DEVICE_TRUST_CLOCK_SKEW_SECONDS", "30")),
    )


settings = load_settings()
settings.database_path.parent.mkdir(parents=True, exist_ok=True)
settings.telemetry_state_path.parent.mkdir(parents=True, exist_ok=True)
settings.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
if settings.forensic_anchor_path is not None:
    settings.forensic_anchor_path.parent.mkdir(parents=True, exist_ok=True)
