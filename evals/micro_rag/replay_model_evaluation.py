from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from evals.micro_rag.response_adapter import EvaluationMetadata, RetrievedEvidence, adapt_model_output
    from evals.micro_rag.run_gemini_evaluation import approved_docs, build_cases, load_documents
except ModuleNotFoundError:
    from response_adapter import EvaluationMetadata, RetrievedEvidence, adapt_model_output
    from run_gemini_evaluation import approved_docs, build_cases, load_documents


def run(report_path: Path) -> int:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    revision_override = os.getenv("SMART_WARD_REPLAY_MODEL_REVISION")
    docs = approved_docs(load_documents())
    cases = {case["case_id"]: case for case in build_cases(docs)}
    results: list[dict[str, Any]] = []
    for recorded in report.get("results", []):
        case = cases[recorded["case_id"]]
        metadata_payload = dict(recorded["metadata"])
        if revision_override:
            metadata_payload["model_revision"] = revision_override
        metadata = EvaluationMetadata.model_validate(metadata_payload)
        raw_output = recorded.get("redacted_raw_output", "")
        adapted = adapt_model_output(
            raw_output,
            retrieved=case["retrieved"],
            expected_scope=case["scope"],
            metadata=metadata,
        )
        case_passed = adapted.accepted
        if case["expected"] == "refusal":
            response = adapted.response
            case_passed = case_passed and response is not None and response.refusal_reason is not None and not response.citations
        results.append(
            {
                "case_id": recorded["case_id"],
                "expected": case["expected"],
                "case_passed": case_passed,
                "adapter_accepted": adapted.accepted,
                "violations": adapted.violations,
            }
        )

    passed = sum(1 for item in results if item["case_passed"])
    replay = {
        "suite": "micro-rag-model-specific-replay-v1",
        "source_report": str(report_path),
        "model_id": report.get("model_id"),
        "model_revision": revision_override or report.get("model_revision"),
        "corpus_revision": report.get("corpus_revision"),
        "adapter_version": "response-adapter-v1",
        "passed_cases": passed,
        "total_cases": len(results),
        "results": results,
        "status": "REPLAYED_WITH_UPDATED_ADAPTER" if passed == len(results) else "REQUIRES_REVIEW",
        "clinical_validity": "PENDING",
        "runtime_authority": "NONE",
    }
    output_path = Path(f"{report_path}.replay.json")
    output_path.write_text(json.dumps(replay, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"model_id": replay["model_id"], "model_revision": replay["model_revision"], "passed_cases": passed, "total_cases": len(results), "status": replay["status"], "report_path": str(output_path)}, sort_keys=True))
    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: replay_model_evaluation.py /path/to/model-evaluation.json")
    raise SystemExit(run(Path(sys.argv[1])))
