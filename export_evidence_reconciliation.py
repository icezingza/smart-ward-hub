from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

from evidence_reconciliation import default_paths, reconcile_packages


def export(*, root: Path, output: Path) -> dict:
    root = root.resolve()
    current_paths = default_paths(root)
    freeze_path = current_paths["freeze_path"]
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    source_revision = freeze["source_revision"]
    with tempfile.TemporaryDirectory() as directory:
        frozen_root = Path(directory)
        archive = subprocess.run(["git", "archive", source_revision], cwd=root, check=True, stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(frozen_root, filter="data")
        (frozen_root / freeze_path.relative_to(root)).write_bytes(freeze_path.read_bytes())
        result = reconcile_packages(**default_paths(frozen_root))
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Export cross-package evidence reconciliation snapshot")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export(root=args.root.resolve(), output=args.output)
    print(
        json.dumps(
            {
                "reconciliation_status": result["reconciliation_status"],
                "gate_decision": result["gate_decision"],
                "source_revision_alignment": result["source_revision_alignment"],
                "finding_count": len(result["findings"]),
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
