from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class SyncBatch:
    batch_id: str
    device_id: str
    sample_count: int
    first_sequence: int | None
    last_sequence: int | None
    batch_hash: str
    created_at: datetime
    status: str  # PENDING, SYNCED, FAILED
    his_transaction_id: str | None = None
    synced_at: datetime | None = None


class HisSyncGate:
    """Safe Sync & Purge Gate for Ward Hub.

    Guarantees that telemetry and shift summaries are only purged from local cache
    after receiving an authoritative HTTP 200 OK confirmation with a valid transaction
    reference from the hospital HIS/EMR endpoint.
    """

    def __init__(self) -> None:
        self._batches: dict[str, SyncBatch] = {}

    def create_batch(
        self,
        *,
        device_id: str,
        samples: list[dict[str, Any]],
        batch_id: str | None = None,
    ) -> SyncBatch:
        now = utc_now()
        ordered = sorted(samples, key=lambda s: s.get("sequence", -1))
        first_seq = ordered[0].get("sequence") if ordered else None
        last_seq = ordered[-1].get("sequence") if ordered else None
        
        serialized = json.dumps(
            {"device_id": device_id, "sample_count": len(ordered), "first_seq": first_seq, "last_seq": last_seq},
            sort_keys=True,
            separators=(",", ":"),
        )
        batch_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        bid = batch_id or f"sync-batch-{device_id}-{now.strftime('%Y%m%d%H%M%S')}"

        batch = SyncBatch(
            batch_id=bid,
            device_id=device_id,
            sample_count=len(ordered),
            first_sequence=first_seq,
            last_sequence=last_seq,
            batch_hash=batch_hash,
            created_at=now,
            status="PENDING",
        )
        self._batches[bid] = batch
        return batch

    def confirm_sync(
        self,
        *,
        batch_id: str,
        http_status_code: int,
        his_response: dict[str, Any],
    ) -> bool:
        """Confirm HIS acknowledgment. Only HTTP 200 OK with valid transaction ID grants sync."""
        batch = self._batches.get(batch_id)
        if not batch:
            logger.warning("Sync confirmation failed: batch %s not found", batch_id)
            return False

        if http_status_code == 200:
            tx_id = his_response.get("transaction_id") or his_response.get("id") or his_response.get("ack_code")
            if tx_id:
                batch.status = "SYNCED"
                batch.his_transaction_id = str(tx_id)
                batch.synced_at = utc_now()
                logger.info("Safe Sync Gate: batch %s confirmed by HIS with tx %s", batch_id, tx_id)
                return True

        batch.status = "FAILED"
        logger.warning("Safe Sync Gate: batch %s rejected with status %s", batch_id, http_status_code)
        return False

    def can_purge(self, batch_id: str) -> bool:
        """Returns True ONLY if batch was successfully confirmed with HTTP 200 by HIS."""
        batch = self._batches.get(batch_id)
        return bool(batch and batch.status == "SYNCED")

    def get_batch(self, batch_id: str) -> SyncBatch | None:
        return self._batches.get(batch_id)
