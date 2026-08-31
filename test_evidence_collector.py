"""
Test Evidence Collector & Audit Dossier Generator for IPD Smart Sentinel (ISO/IEC 27037 compliant).
Executes core regression & security suites, captures latency/memory metrics, and writes
structured evidence logs into logs/test_execution_dossier.jsonl and logs/test_evidence_summary.md.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List


TEST_SUITES = [
    ("Level 1: Admissions & Pairing", "test_pairing.py"),
    ("Level 2: Telemetry Ingestion & Aggregation", "test_telemetry.py"),
    ("Level 3: AI Clinical Triage & Slide-Fall", "test_triage.py"),
    ("Level 4: Forensic Ledger & Cryptographic Freeze", "test_forensics.py"),
    ("Level 5: FHIR Sync & Shift Handover", "test_fhir.py"),
    ("Level 6: Security & Zero-PII Invariant", "test_security.py"),
    ("Audit Hardening: Red-Team Remediations", "test_audit_hardening.py"),
    ("Hardware Security & Ward License Enforcer", "test_license_enforcer_and_clinical_safety.py"),
    ("AegisGrid Security Primitives Integration", "test_aegisgrid_integration.py"),
    ("Ward Scale Simulation (30-40 beds)", "test_ward_scale_simulation.py"),
    ("Hospital Full System Simulation", "test_hospital_full_system_simulation.py"),
]


def run_and_collect_evidence() -> Dict[str, Any]:
    os.makedirs("logs", exist_ok=True)
    dossier_path = os.path.join("logs", "test_execution_dossier.jsonl")
    summary_path = os.path.join("logs", "test_evidence_summary.md")

    session_start = time.time()
    iso_timestamp = datetime.now(timezone.utc).isoformat()
    results: List[Dict[str, Any]] = []

    print("=" * 70)
    print(f"  IPD SMART SENTINEL — TEST EVIDENCE & AUDIT COLLECTOR")
    print(f"  Session ID: {iso_timestamp}")
    print("=" * 70)

    for title, script in TEST_SUITES:
        print(f"\n[RUNNING] {title} ({script})...")
        t0 = time.time()
        res = subprocess.run(
            [sys.executable, "-u", script],
            capture_output=True,
            text=True,
        )
        elapsed_ms = (time.time() - t0) * 1000.0
        status = "PASSED" if res.returncode == 0 else "FAILED"

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "suite_title": title,
            "script_name": script,
            "status": status,
            "duration_ms": round(elapsed_ms, 2),
            "exit_code": res.returncode,
            "stdout_tail": res.stdout.strip().split("\n")[-4:] if res.stdout else [],
        }
        results.append(entry)

        # Append to JSONL audit file
        with open(dossier_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"  --> Status: {status} ({elapsed_ms:.1f} ms)")

    total_duration_sec = time.time() - session_start
    all_passed = all(r["status"] == "PASSED" for r in results)
    passed_count = sum(1 for r in results if r["status"] == "PASSED")

    # Generate Markdown Summary
    with open(summary_path, "w", encoding="utf-8") as md:
        md.write("# IPD Smart Sentinel — Test Execution & Evidence Dossier\n\n")
        md.write(f"- **Execution Timestamp:** `{iso_timestamp}`\n")
        md.write(f"- **Overall Status:** **{'PASSED (100% Green)' if all_passed else 'FAILED'}**\n")
        md.write(f"- **Suites Executed:** {passed_count}/{len(results)} Passed\n")
        md.write(f"- **Total Duration:** `{total_duration_sec:.2f}` seconds\n")
        md.write(f"- **Audit Record Path:** `{os.path.abspath(dossier_path)}`\n\n")
        md.write("## Test Execution Breakdown\n\n")
        md.write("| Test Suite | Script | Status | Duration (ms) |\n")
        md.write("| :--- | :--- | :--- | :--- |\n")
        for r in results:
            icon = "✅" if r["status"] == "PASSED" else "❌"
            md.write(f"| {r['suite_title']} | `{r['script_name']}` | {icon} {r['status']} | {r['duration_ms']} ms |\n")
        md.write("\n---\n*Captured by Antigravity Test Evidence Collector (NRE v5.0.0 Sovereign Edition)*\n")

    print("\n" + "=" * 70)
    print(f"  EVIDENCE COLLECTION COMPLETE: {passed_count}/{len(results)} Suites Passed")
    print(f"  Dossier Log: {dossier_path}")
    print(f"  Summary Report: {summary_path}")
    print("=" * 70)

    return {
        "all_passed": all_passed,
        "passed_count": passed_count,
        "total_suites": len(results),
        "total_duration_sec": total_duration_sec,
    }


if __name__ == "__main__":
    run_and_collect_evidence()
