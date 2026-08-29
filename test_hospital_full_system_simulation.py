from hospital_full_system_simulation import run_hospital_simulation


def run() -> None:
    report = run_hospital_simulation(ward_count=2, beds_per_ward=20, ticks=8)
    assert report["hospital_profile"] == {"ward_count": 2, "beds_per_ward": 20, "hub_count": 2, "total_beds": 40}
    assert report["accepted_packets"] == report["expected_packets"] == 306
    assert report["active_pairings"] == 40
    assert report["alert_count"] == report["forensic_package_count"] == 4
    assert len(report["warnings"]) == 4
    assert len(report["server_sync"]) == 2
    assert all(item["retained_on_503"] and item["acknowledged_after_structured_ack"] for item in report["server_sync"])
    assert report["expected_results_matched"] is True
    assert report["patient_data_used"] is False
    assert report["external_server_contacted"] is False
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False
    print("[Hospital Full System] Two wards and forty synthetic beds through FastAPI: PASSED")
    print("HOSPITAL_FULL_SYSTEM_SIMULATION_TESTS_PASSED")


if __name__ == "__main__":
    run()
