from __future__ import annotations

import argparse
import json
from pathlib import Path

from wave_e_execution_preflight import build_empty_preflight


def export(*, output: Path, package_revision: str, source_revision: str) -> dict:
    preflight = build_empty_preflight(package_revision=package_revision, source_revision=source_revision)
    packet = preflight.export_handoff_packet()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Wave E owner-appointment preflight snapshot")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-revision", required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    packet = export(output=args.output, package_revision=args.package_revision, source_revision=args.source_revision)
    print(
        json.dumps(
            {
                "packet_status": packet["packet_status"],
                "package_hash": packet["package_hash"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
