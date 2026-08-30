from ward_scale_simulation import build_ward, run_simulation


def run() -> None:
    report = run_simulation()
    assert report["hub_count"] == 1
    assert report["bed_count"] == 40
    assert report["accepted_packets"] == 313
    assert report["max_devices_configured"] == 40
    assert report["alerts"] == {"SIM-W01-B02": "FALL", "SIM-W01-B05": "VITAL_ANOMALY"}
    assert {item["bed_no"]: item["warning"] for item in report["warnings"]} == {
        "SIM-W01-B08": "DEVICE_DISCONNECTED_STALE",
        "SIM-W01-B12": "DEVICE_PERIMETER_WARNING",
        "SIM-W01-B20": "BLOOD_PRESSURE_SENSOR_UNSUPPORTED",
    }
    assert report["expected_results_matched"] is True
    assert report["patient_data_used"] is False
    assert report["hardware_contacted"] is False
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False
    assert len(build_ward()) == 40
    thirty_bed_report = run_simulation(bed_count=30)
    assert thirty_bed_report["bed_count"] == 30
    assert thirty_bed_report["accepted_packets"] == 233
    assert thirty_bed_report["expected_results_matched"] is True
    print("[Ward Scale] Forty synthetic beds on one Hub with risk scenarios: PASSED")
    print("[Ward Scale] Thirty synthetic beds on one Hub with the same risk coverage: PASSED")
    print("WARD_SCALE_SIMULATION_TESTS_PASSED")


if __name__ == "__main__":
    run()
