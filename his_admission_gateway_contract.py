from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any


class GatewayTokenError(ValueError):
    """Raised when a gateway token cannot be used for a Hub handoff."""


@dataclass
class _TokenRecord:
    token_digest: str
    expires_at: datetime
    revoked: bool = False


class SandboxAdmissionGateway:
    """Synthetic gateway boundary for contract tests only.

    Raw HN/AN values are accepted only at this simulated outside boundary and are
    immediately discarded. The Hub-facing payload contains only an opaque token.
    This class is not a hospital identity provider and is not production auth.
    """

    def __init__(self, *, clock: callable | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: dict[str, _TokenRecord] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self, raw_his_reference: str, *, ttl_seconds: int = 300) -> str:
        if not raw_his_reference or ttl_seconds <= 0:
            raise GatewayTokenError("invalid_gateway_issue_request")
        opaque = f"ptok-{secrets.token_urlsafe(24)}"
        self._records[opaque] = _TokenRecord(
            token_digest=self._digest(opaque),
            expires_at=self._clock() + timedelta(seconds=ttl_seconds),
        )
        # Raw reference is intentionally not retained after token issuance.
        return opaque

    def revoke(self, token: str) -> None:
        record = self._records.get(token)
        if record is None:
            raise GatewayTokenError("unknown_token")
        record.revoked = True

    def validate(self, token: str) -> None:
        record = self._records.get(token)
        if record is None or record.token_digest != self._digest(token):
            raise GatewayTokenError("unknown_token")
        if record.revoked:
            raise GatewayTokenError("revoked_token")
        if self._clock() >= record.expires_at:
            raise GatewayTokenError("expired_token")

    def hub_admission_payload(self, token: str, *, bed_no: str, idempotency_key: str) -> dict[str, Any]:
        self.validate(token)
        return {
            "patient_token": token,
            "bed_no": bed_no,
            "idempotency_key": idempotency_key,
            "source_console_id": "sandbox-admission-gateway",
        }
