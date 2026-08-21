from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from internal_foundation_readiness import evaluate_internal_foundation


def export(output: Path, *, project_root: Path, bind_host: str = "127.0.0.1", port: int = 8080) -> dict[str, object]:
    result = evaluate_internal_foundation(
        dict(os.environ),
        project_root=project_root,
        bind_host=bind_host,
        port=port,
    )
    snapshot = {
        "schema_version": result["schema_version"],
        "snapshot_kind": "INTERNAL_FOUNDATION_READINESS",
        "evidence_class": "LOCAL_SOFTWARE_SIMULATION",
        "status": result["status"],
        "checks": result["checks"],
        "software_only": result["software_only"],
        "physical_validation": result["physical_validation"],
        "clinical_validation": result["clinical_validation"],
        "external_authority": result["external_authority"],
        "runtime_authority": result["runtime_authority"],
        "authorization_boundary": result["authorization_boundary"],
        "pilot_gate_status": result["pilot_gate_status"],
        "source_root": str(project_root.resolve()),
        "next_action": "Resolve any FAIL/ADVISORY checks locally; obtain target-host and external evidence separately before any production decision.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Export local Smart Ward Hub internal foundation readiness")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    snapshot = export(args.output.resolve(), project_root=args.project_root.resolve(), bind_host=args.host, port=args.port)
    print(
        json.dumps(
            {
                "snapshot_kind": snapshot["snapshot_kind"],
                "status": snapshot["status"],
                "evidence_class": snapshot["evidence_class"],
                "pilot_gate_status": snapshot["pilot_gate_status"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if snapshot["status"] != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
