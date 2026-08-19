from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Protocol


HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ExternalAnchorError(ValueError):
    pass


@dataclass(frozen=True)
class AnchorRequest:
    package_id: int
    block_hash: str
    chain_tip: str

    @property
    def idempotency_key(self) -> str:
        material = f"{self.package_id}|{self.block_hash}|{self.chain_tip}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()


@dataclass(frozen=True)
class AnchorReceipt:
    provider_id: str
    anchor_id: str
    idempotency_key: str
    package_id: int
    block_hash: str
    chain_tip: str
    accepted_at_utc: str
    status: str
    evidence_class: str


class ExternalAnchorClient(Protocol):
    provider_id: str

    def publish(self, request: AnchorRequest) -> AnchorReceipt:
        ...

    def verify(self, receipt: AnchorReceipt) -> bool:
        ...


class ExternalAnchorAdapter:
    """Fail-closed adapter boundary for an independently operated anchor service."""

    def __init__(self, client: ExternalAnchorClient | None, *, provider_id: str) -> None:
        if not provider_id.strip() or provider_id.strip().lower() in {"local", "filesystem", "none"}:
            raise ExternalAnchorError("independent_provider_id_required")
        self.client = client
        self.provider_id = provider_id.strip()
        if client is not None and getattr(client, "provider_id", None) != self.provider_id:
            raise ExternalAnchorError("client_provider_id_mismatch")
        self.last_receipt: AnchorReceipt | None = None

    def anchor_with_receipt(self, *, block_hash: str, chain_tip: str, package_id: int) -> AnchorReceipt:
        request = self._validate_request(block_hash=block_hash, chain_tip=chain_tip, package_id=package_id)
        if self.client is None:
            raise ExternalAnchorError("external_anchor_client_unconfigured")
        receipt = self.client.publish(request)
        self._validate_receipt(request, receipt)
        if not self.client.verify(receipt):
            raise ExternalAnchorError("external_receipt_verification_failed")
        self.last_receipt = receipt
        return receipt

    def anchor(self, *, block_hash: str, chain_tip: str, package_id: int) -> bool:
        self.anchor_with_receipt(block_hash=block_hash, chain_tip=chain_tip, package_id=package_id)
        return True

    def verify_receipt(self, receipt: AnchorReceipt) -> bool:
        if self.client is None:
            return False
        return self.client.verify(receipt)

    @staticmethod
    def _validate_request(*, block_hash: str, chain_tip: str, package_id: int) -> AnchorRequest:
        if not isinstance(package_id, int) or isinstance(package_id, bool) or package_id <= 0:
            raise ExternalAnchorError("invalid_package_id")
        if not isinstance(block_hash, str) or not HEX64.fullmatch(block_hash):
            raise ExternalAnchorError("invalid_block_hash")
        if not isinstance(chain_tip, str) or not HEX64.fullmatch(chain_tip):
            raise ExternalAnchorError("invalid_chain_tip")
        return AnchorRequest(package_id=package_id, block_hash=block_hash, chain_tip=chain_tip)

    def _validate_receipt(self, request: AnchorRequest, receipt: AnchorReceipt) -> None:
        if not isinstance(receipt, AnchorReceipt):
            raise ExternalAnchorError("invalid_external_receipt")
        if receipt.provider_id != self.provider_id:
            raise ExternalAnchorError("receipt_provider_mismatch")
        if receipt.status != "ACCEPTED":
            raise ExternalAnchorError("external_anchor_not_accepted")
        if receipt.package_id != request.package_id:
            raise ExternalAnchorError("receipt_package_mismatch")
        if receipt.block_hash != request.block_hash or receipt.chain_tip != request.chain_tip:
            raise ExternalAnchorError("receipt_hash_mismatch")
        if receipt.idempotency_key != request.idempotency_key:
            raise ExternalAnchorError("receipt_idempotency_mismatch")
        if receipt.evidence_class != "EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED":
            raise ExternalAnchorError("receipt_evidence_class_invalid")


class MemoryAppendOnlyAnchor:
    """Deterministic provider stub; never claim this as external WORM evidence."""

    provider_id = "software-anchor-stub"

    def __init__(self) -> None:
        self._records: dict[str, AnchorReceipt] = {}
        self._sequence = 0

    def publish(self, request: AnchorRequest) -> AnchorReceipt:
        existing = self._records.get(request.idempotency_key)
        if existing is not None:
            return existing
        self._sequence += 1
        receipt = AnchorReceipt(
            provider_id=self.provider_id,
            anchor_id=f"stub-anchor-{self._sequence}",
            idempotency_key=request.idempotency_key,
            package_id=request.package_id,
            block_hash=request.block_hash,
            chain_tip=request.chain_tip,
            accepted_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            status="ACCEPTED",
            evidence_class="EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED",
        )
        self._records[request.idempotency_key] = receipt
        return receipt

    def verify(self, receipt: AnchorReceipt) -> bool:
        return self._records.get(receipt.idempotency_key) == receipt

    def delete(self, idempotency_key: str) -> None:
        raise ExternalAnchorError("append_only_delete_forbidden")

    def snapshot(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self._records.values()]

    def tamper_for_test(self, idempotency_key: str, *, block_hash: str) -> None:
        existing = self._records[idempotency_key]
        self._records[idempotency_key] = AnchorReceipt(
            provider_id=existing.provider_id,
            anchor_id=existing.anchor_id,
            idempotency_key=existing.idempotency_key,
            package_id=existing.package_id,
            block_hash=block_hash,
            chain_tip=existing.chain_tip,
            accepted_at_utc=existing.accepted_at_utc,
            status=existing.status,
            evidence_class=existing.evidence_class,
        )
