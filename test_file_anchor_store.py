from __future__ import annotations

import json
from pathlib import Path
import tempfile

from edge_controls import FileAnchorStore


BLOCK = "a" * 64
CHAIN = "b" * 64


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ValueError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="smart-ward-file-anchor-") as directory:
        root = Path(directory)
        source = root / "source"
        source.mkdir()
        path = root / "runtime" / "forensic_anchors.jsonl"
        store = FileAnchorStore(path, source_root=source)
        receipt = store.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=1)
        assert receipt is not None
        assert receipt["anchor_version"] == "1.1"
        assert receipt["evidence_class"] == "LOCAL_TAMPER_EVIDENT_UNVERIFIED"
        assert store.verify_receipt(receipt) is True
        print("[FileAnchorStore] Structured local receipt and readback verification: PASSED")

        replay = store.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=1)
        assert replay == receipt
        assert len(store.read_records()) == 1
        print("[FileAnchorStore] Stable idempotent replay avoids duplicate local record: PASSED")

        expect_error(lambda: store.anchor(block_hash="bad", chain_tip=CHAIN, package_id=2), "invalid_anchor_block_hash")
        expect_error(lambda: store.anchor(block_hash=BLOCK, chain_tip=CHAIN, package_id=0), "invalid_anchor_package_id")
        expect_error(lambda: FileAnchorStore(source / "forensic.jsonl", source_root=source), "anchor_path_must_be_outside_source_tree")
        print("[FileAnchorStore] Hash/package/path validation fails closed: PASSED")

        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["chain_tip"] = "c" * 64
        path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
        assert store.read_records() == []
        assert store.verify_receipt(receipt) is False
        print("[FileAnchorStore] Record-hash tampering is excluded from verified readback: PASSED")

        legacy = root / "legacy.jsonl"
        legacy.write_text(
            json.dumps(
                {
                    "anchor_version": "1.0",
                    "package_id": 3,
                    "block_hash": BLOCK,
                    "chain_tip": CHAIN,
                    "anchored_at": "2026-01-01T00:00:00Z",
                    "anchor_type": "local_append_only_adapter",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        legacy_store = FileAnchorStore(legacy, source_root=source)
        assert len(legacy_store.read_records()) == 1
        print("[FileAnchorStore] Legacy v1 local record remains readable: PASSED")

    print("FILE_ANCHOR_STORE_REGRESSION_TESTS_PASSED")


if __name__ == "__main__":
    run()
