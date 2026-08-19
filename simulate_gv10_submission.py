from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from external_validation_package import default_pilot_package
from gv10_evidence import EvidenceEntry, GV10EvidenceDossier, GV10EvidenceError, build_gv10_template


ROOT = Path(__file__).resolve().parent
SIMULATION_TIMESTAMP = "2026-08-20T10:00:00+00:00"


class SimulationFailure(AssertionError):
    pass


def artifact_sha256(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.is_file():
        raise SimulationFailure(f"missing_real_artifact:{relative_path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_entry(
    *,
    evidence_id: str,
    gate_id: str,
    artifact_ref: str,
    evidence_class: str,
    source_boundary: str,
    chain_of_custody_ref: str,
    **overrides: Any,
) -> EvidenceEntry:
    values: dict[str, Any] = {
        "evidence_id": evidence_id,
        "gate_id": gate_id,
        "artifact_ref": artifact_ref,
        "artifact_sha256": artifact_sha256(artifact_ref),
        "evidence_class": evidence_class,
        "collected_at_utc": SIMULATION_TIMESTAMP,
        "prepared_by_role": "engineering_evidence_coordinator",
        "source_boundary": source_boundary,
        "redaction_status": "PASS",
        "chain_of_custody_ref": chain_of_custody_ref,
        "independent_verification_required": True,
    }
    values.update(overrides)
    return EvidenceEntry(**values)


def positive_cases() -> list[EvidenceEntry]:
    return [
        make_entry(
            evidence_id="EV-GV10-P1001-001",
            gate_id="GV-02",
            artifact_ref="backup_restore.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-P1001-001",
        ),
        make_entry(
            evidence_id="EV-GV10-P1005-001",
            gate_id="GV-09",
            artifact_ref="clinical_shadow_mode.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-P1005-001",
        ),
        make_entry(
            evidence_id="EV-GV10-P2002-001",
            gate_id="GV-06",
            artifact_ref="network_pressure_simulation.py",
            evidence_class="SIMULATION_ONLY",
            source_boundary="deterministic_simulation_artifact",
            chain_of_custody_ref="COC-GV10-P2002-001",
        ),
        make_entry(
            evidence_id="EV-GV10-P1004-001",
            gate_id="GV-07",
            artifact_ref="external_anchor.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-P1004-001",
        ),
        make_entry(
            evidence_id="EV-GV10-GV06-BLOCKER-001",
            gate_id="GV-06",
            artifact_ref="ACER_BENCH_READONLY_INVENTORY.md",
            evidence_class="BLOCKER_RECORD",
            source_boundary="physical_hardware_validation_boundary",
            chain_of_custody_ref="COC-GV10-GV06-001",
        ),
    ]


def build_positive_review() -> dict[str, Any]:
    dossier = build_gv10_template()
    accepted: list[dict[str, Any]] = []
    for item in positive_cases():
        dossier.add_entry(item)
        accepted.append(
            {
                "evidence_id": item.evidence_id,
                "gate_id": item.gate_id,
                "artifact_ref": item.artifact_ref,
                "evidence_class": item.evidence_class,
                "decision": "ACCEPTED_FOR_REVIEW",
                "note": "รับ artifact เข้ากระบวนการตรวจซ้ำเท่านั้น ไม่ใช่การปิด gate หรืออนุมัติ clinical/production",
            }
        )
    readiness = dossier.review_readiness()
    if readiness["clinical_validation_authorized"] or readiness["production_authorized"]:
        raise SimulationFailure("authorization_boundary_breached")
    return {
        "scenario": "positive_submission",
        "decision": "ACCEPTED_FOR_REVIEW",
        "accepted_entries": accepted,
        "readiness": readiness,
    }


def expect_rejection(
    name: str,
    expected_error: str,
    action: Callable[[], Any],
) -> dict[str, Any]:
    try:
        action()
    except GV10EvidenceError as exc:
        actual = str(exc)
        if actual != expected_error:
            raise SimulationFailure(f"{name}:expected={expected_error}:actual={actual}") from exc
        return {
            "scenario": name,
            "decision": "REJECTED_FAIL_CLOSED",
            "expected_error": expected_error,
            "actual_error": actual,
        }
    raise SimulationFailure(f"{name}:accepted_invalid_evidence")


def build_external_gate_matrix() -> dict[str, Any]:
    package = default_pilot_package()
    blockers = {
        "GV-01": "ยังไม่มี clinical owner, approved protocol และ committee sign-off",
        "GV-03": "ยังไม่มี real HIS transcript และ failure-recovery evidence จากระบบจริง",
        "GV-04": "ยังไม่มี real OIDC/mTLS handshake และ key-rotation transcript",
        "GV-06": "Acer Spin N17H2 ยังไม่มี COM port ที่ enumerate; physical serial/power-loss bench ยังไม่เสร็จ",
        "GV-07": "ยังไม่มี independent WORM receipt และ trusted timestamp จากระบบภายนอก",
        "GV-08": "ยังไม่มี manufacturer provenance และ hardware key-custody evidence",
        "GV-09": "ยังไม่มี staff training, manual-fallback SOP sign-off และ clinical operations review",
    }
    for gate_id, reason in blockers.items():
        package.block_gate(gate_id, reason)
    summary = package.readiness_summary()
    rows = []
    for gate_id in sorted(package.gates):
        gate = package.gates[gate_id]
        rows.append({
            "gate_id": gate.gate_id,
            "domain": gate.domain,
            "owner_role": gate.owner_role,
            "status": gate.status,
            "blocker": gate.blocker,
            "required_evidence": list(gate.required_evidence),
        })
    if len(rows) != 10:
        raise SimulationFailure(f"expected_10_external_gates:actual={len(rows)}")
    return {"summary": summary, "gates": rows}


def fail_closed_cases() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def raw_identity() -> None:
        dossier = build_gv10_template()
        dossier.add_entry(make_entry(
            evidence_id="EV-GV10-NEG-RAWID-001",
            gate_id="GV-02",
            artifact_ref="backup_restore.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-HN-2026-1234",
        ))

    results.append(expect_rejection("raw_identity_reference", "unsafe_chain_of_custody_ref", raw_identity))

    def bad_hash() -> None:
        dossier = build_gv10_template()
        dossier.add_entry(make_entry(
            evidence_id="EV-GV10-NEG-HASH-001",
            gate_id="GV-02",
            artifact_ref="backup_restore.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-NEG-HASH-001",
            artifact_sha256="not-a-sha256",
        ))

    results.append(expect_rejection("bad_sha256", "artifact_sha256_required", bad_hash))

    def missing_redaction() -> None:
        dossier = build_gv10_template()
        dossier.add_entry(make_entry(
            evidence_id="EV-GV10-NEG-REDACT-001",
            gate_id="GV-09",
            artifact_ref="clinical_shadow_mode.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-NEG-REDACT-001",
            redaction_status="PENDING",
        ))

    results.append(expect_rejection("missing_redaction_pass", "redaction_pass_required", missing_redaction))

    def forbidden_claim() -> None:
        dossier = build_gv10_template()
        dossier.add_entry(make_entry(
            evidence_id="EV-GV10-NEG-CLAIM-001",
            gate_id="GV-01",
            artifact_ref="clinical_shadow_mode.py",
            evidence_class="CLINICAL_VALIDATED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-NEG-CLAIM-001",
        ))

    results.append(expect_rejection("forbidden_clinical_claim", "forbidden_evidence_class", forbidden_claim))

    def naive_timestamp() -> None:
        dossier = build_gv10_template()
        dossier.add_entry(make_entry(
            evidence_id="EV-GV10-NEG-TIME-001",
            gate_id="GV-02",
            artifact_ref="backup_restore.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-NEG-TIME-001",
            collected_at_utc="2026-08-20T10:00:00",
        ))

    results.append(expect_rejection("naive_timestamp", "collected_at_must_be_timezone_aware", naive_timestamp))

    def duplicate_evidence_id() -> None:
        dossier = build_gv10_template()
        first = make_entry(
            evidence_id="EV-GV10-NEG-DUP-001",
            gate_id="GV-02",
            artifact_ref="backup_restore.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-NEG-DUP-001",
        )
        dossier.add_entry(first)
        dossier.add_entry(first)

    results.append(expect_rejection("duplicate_evidence_id", "duplicate_evidence_id", duplicate_evidence_id))

    def unknown_gate() -> None:
        dossier = build_gv10_template()
        dossier.add_entry(make_entry(
            evidence_id="EV-GV10-NEG-GATE-001",
            gate_id="GV-99",
            artifact_ref="backup_restore.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-NEG-GATE-001",
        ))

    results.append(expect_rejection("unknown_gate_id", "unknown_gate_id", unknown_gate))

    def missing_preparer() -> None:
        dossier = build_gv10_template()
        dossier.add_entry(make_entry(
            evidence_id="EV-GV10-NEG-ROLE-001",
            gate_id="GV-02",
            artifact_ref="backup_restore.py",
            evidence_class="SOFTWARE_VERIFIED",
            source_boundary="repository_software_artifact",
            chain_of_custody_ref="COC-GV10-NEG-ROLE-001",
            prepared_by_role="",
        ))

    results.append(expect_rejection("missing_prepared_by_role", "prepared_by_role_required", missing_preparer))

    def unsafe_claim_boundary() -> None:
        dossier = build_gv10_template()
        dossier.claim_boundary = "INDEPENDENT_REVIEW_INPUT"
        dossier.add_entry(positive_cases()[0])
        dossier.review_readiness()

    results.append(expect_rejection("unsafe_dossier_claim_boundary", "dossier_claim_boundary_must_remain_unverified", unsafe_claim_boundary))

    def empty_dossier() -> None:
        build_gv10_template().review_readiness()

    results.append(expect_rejection("empty_dossier", "evidence_entries_required", empty_dossier))
    return results


def build_report(result: dict[str, Any]) -> str:
    positive = result["positive_submission"]
    negatives = result["fail_closed_mutations"]
    lines = [
        "# GV-10 Evidence Submission Simulation Report",
        "",
        "**สถานะ:** simulation-only; ไม่ใช่ independent review outcome, clinical validation หรือ production approval",
        "",
        f"**Simulation timestamp:** `{SIMULATION_TIMESTAMP}`",
        "",
        "## สรุปผล",
        "",
        f"จำลอง positive submission จำนวน **{len(positive['accepted_entries'])} รายการ** และ fail-closed mutations จำนวน **{len(negatives)} กรณี** โดยใช้ artifact ที่มีอยู่จริงใน repository และคำนวณ SHA-256 ใหม่ระหว่างการรัน",
        "",
        "| กลุ่ม | จำนวน | ผล |\n|---|---:|---|\n| Positive evidence | " + str(len(positive["accepted_entries"])) + " | ACCEPTED_FOR_REVIEW |\n| Fail-closed mutations | " + str(len(negatives)) + " | REJECTED_FAIL_CLOSED |\n| Clinical validation authorization | 0 | DENIED |\n| Production authorization | 0 | DENIED |",
        "",
        "## Positive submission",
        "",
        "| Evidence ID | Gate | Artifact | Class | Decision |\n|---|---|---|---|---|\n",
    ]
    for item in positive["accepted_entries"]:
        lines.append(
            f"| `{item['evidence_id']}` | `{item['gate_id']}` | `{item['artifact_ref']}` | `{item['evidence_class']}` | `{item['decision']}` |"
        )
    lines.extend([
        "",
        "> `ACCEPTED_FOR_REVIEW` หมายถึงรับ artifact เข้ากระบวนการตรวจซ้ำเท่านั้น ไม่ได้หมายความว่า gate ผ่าน หรือระบบได้รับอนุญาตให้ใช้งานทางคลินิก/production",
        "",
        "## 10 External Gates status matrix",
        "",
        f"Registry summary: `{result['external_gate_matrix']['summary']['status_counts']}`; `ready_for_external_review={result['external_gate_matrix']['summary']['ready_for_external_review']}`.",
        "",
        "| Gate | Domain | Status | Owner | Current blocker |\n|---|---|---|---|---|",
    ])
    for gate in result["external_gate_matrix"]["gates"]:
        blocker = gate["blocker"] or "ยังไม่มี blocker ที่บังคับให้ block; หลักฐานภายนอก/การ review ยังไม่เสร็จ"
        lines.append(
            f"| `{gate['gate_id']}` | `{gate['domain']}` | `{gate['status']}` | `{gate['owner_role']}` | {blocker} |"
        )
    lines.extend([
        "",
        "`OPEN` หมายถึง gate ยังรอ evidence หรือการ review; `BLOCKED` หมายถึงต้องแก้ prerequisite และ/หรือเรียก `reopen()` ก่อนส่ง evidence ใหม่; ไม่มี gate ใดถูกสรุปว่า PASSED จาก simulation นี้",
        "",
        "## Fail-closed mutations",
        "",
        "| Scenario | Expected error | Actual error | Decision |\n|---|---|---|---|\n",
    ])
    for item in negatives:
        lines.append(
            f"| `{item['scenario']}` | `{item['expected_error']}` | `{item['actual_error']}` | `{item['decision']}` |"
        )
    lines.extend([
        "",
        "## Review readiness boundary",
        "",
        f"Dossier readiness result: `{positive['readiness']['ready_for_independent_review']}`; covered gates: `{', '.join(positive['readiness']['gate_ids_covered'])}`; classes: `{', '.join(positive['readiness']['evidence_classes'])}`.",
        "",
        "แม้ validator จะให้ dossier เป็น `ready_for_independent_review=True` แต่ยังคงบังคับ `clinical_validation_authorized=False` และ `production_authorized=False` ตาม no-authorization boundary",
        "",
        "## Decision matrix",
        "",
        "| Evidence class / condition | Expected review outcome | Gate status implication |\n|---|---|---|\n| `SOFTWARE_VERIFIED` | ACCEPTED_FOR_REVIEW หาก hash, provenance และ redaction ผ่าน | ไม่ปิด external gate โดยอัตโนมัติ |\n| `SIMULATION_ONLY` | ACCEPTED_FOR_REVIEW พร้อมติดป้าย simulation-only | ไม่เทียบเท่า field/hardware evidence |\n| `EXTERNAL_UNVERIFIED` | REQUIRES_CLARIFICATION หรือ BLOCKED_EXTERNAL_EVIDENCE | ต้องมีหลักฐานจากระบบภายนอกจริง |\n| `CLINICAL_GOVERNANCE_UNVERIFIED` | BLOCKED_EXTERNAL_EVIDENCE จนมี owner/committee sign-off | ห้ามสรุป clinical validation |\n| `BLOCKER_RECORD` | ACCEPTED_FOR_REVIEW เพื่ออธิบาย residual blocker | gate ยังคง BLOCKED/OPEN ตาม registry |\n| raw identity, bad hash, naive timestamp, missing redaction, forbidden claim, duplicate ID | REJECTED | ห้ามเข้าสู่ review bundle |",
        "",
        "## ข้อสรุป",
        "",
        "ผลจำลองยืนยันว่า `gv10_evidence.py` ทำงานแบบ fail-closed ตามเกณฑ์หลัก ได้แก่ hash, timezone-aware timestamp, redaction PASS, chain-of-custody, raw-identity rejection, forbidden-claim rejection, duplicate protection และ no-authorization boundary ผลนี้เป็น **software verification ของ validator** ไม่ใช่หลักฐานว่าระบบผ่าน 10 External Gates หรือผ่าน clinical validation",
        "",
        "**Product status:** controlled production prototype; P0-hardened software baseline; functional verification passed; pilot-ready foundation; clinical validation pending; GV-10 independent review not yet completed.",
        "",
    ])
    return "\n".join(lines)


def run_simulation() -> dict[str, Any]:
    positive = build_positive_review()
    negatives = fail_closed_cases()
    result = {
        "simulation_timestamp": SIMULATION_TIMESTAMP,
        "validator": "gv10_evidence.py",
        "positive_submission": positive,
        "fail_closed_mutations": negatives,
        "external_gate_matrix": build_external_gate_matrix(),
        "summary": {
            "positive_count": len(positive["accepted_entries"]),
            "negative_count": len(negatives),
            "all_negative_cases_rejected": all(item["decision"] == "REJECTED_FAIL_CLOSED" for item in negatives),
            "clinical_validation_authorized": False,
            "production_authorized": False,
        },
    }
    if not result["summary"]["all_negative_cases_rejected"]:
        raise SimulationFailure("not_all_negative_cases_rejected")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate GV-10 evidence submission and fail-closed review")
    parser.add_argument("--json-output", type=Path, default=Path("/tmp/gv10_simulation_result.json"))
    parser.add_argument(
        "--report-output",
        type=Path,
        default=ROOT / "GV10_SIMULATION_REPORT.md",
    )
    args = parser.parse_args()

    result = run_simulation()
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report_output.write_text(build_report(result), encoding="utf-8")

    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    print("GV10_SUBMISSION_SIMULATION_PASSED")


if __name__ == "__main__":
    main()


__all__ = ["run_simulation", "build_report"]
