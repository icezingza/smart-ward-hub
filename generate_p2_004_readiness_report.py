from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.micro_rag.run_gemini_evaluation import build_registry_index, load_documents
from persistence_contract import default_software_policy
from repeated_sample_evaluation import aggregate_reports
from runtime_semantic_retrieval_readiness import evaluate_runtime_readiness


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate_p2_004_readiness_report.py OUTPUT_JSON MODEL_REPORT_JSON")
    output_path = Path(sys.argv[1])
    source_path = Path(sys.argv[2])
    registry, index = build_registry_index(load_documents())
    sample_summary = aggregate_reports([source_path])
    decision = evaluate_runtime_readiness(
        registry=registry,
        index=index,
        persistence_policy=default_software_policy("index_snapshot"),
        repeated_summary=sample_summary,
    )
    payload = {
        "suite": "p2-004-runtime-semantic-retrieval-readiness-v1",
        "source_report": str(source_path),
        "sample_summary": sample_summary,
        "index_snapshot": index.snapshot_manifest(),
        "readiness": decision.as_dict(),
        "clinical_validity": "PENDING",
        "runtime_authority": "NONE",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "status": decision.status, "clinical_validation_authorized": False, "production_authorized": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
