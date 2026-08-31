#!/usr/bin/env python3
"""
IPD SMART SENTINEL — ONE-CLICK MASTER LAUNCHER & LIVE CONTROL CONSOLE
======================================================================
Coordinates Edge Hub startup, browser dashboards, telemetry streams,
and live clinical trigger demonstrations with a single command.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HUB_URL = "http://localhost:8000"


def print_banner() -> None:
    print(r"""
================================================================================
  🏥  IPD SMART SENTINEL — SOVEREIGN EDGE WARD HUB (NRE v5.0.0)
  ⚡  ONE-CLICK MASTER RUNTIME & DEMO CONTROLLER
================================================================================
  [•] Edge Server  : http://localhost:8000
  [•] Ward Kiosk   : http://localhost:8000/kiosk
  [•] Admission UI : http://localhost:8000/admission
  [•] WebSocket    : ws://localhost:8000/ws/v1/telemetry
================================================================================
""")


def wait_for_hub(timeout_seconds: int = 15) -> bool:
    print("[*] Waiting for Smart Ward Hub to reach healthy state...", end="", flush=True)
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            req = urllib.request.Request(f"{HUB_URL}/health")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    print(" [READY] ✅")
                    return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(0.5)
    print(" [TIMEOUT] ❌")
    return False


def generate_qr_codes() -> None:
    print("\n[*] Generating patient QR codes into ./demo_qr_codes ...")
    cmd = [sys.executable, str(ROOT / "scripts" / "generate_patient_qr.py"), "--batch", "1", "10", "--output", str(ROOT / "demo_qr_codes")]
    try:
        subprocess.run(cmd, check=True)
        print("[+] QR Codes generated successfully in ./demo_qr_codes")
    except Exception as exc:
        print(f"[!] Warning generating QR codes: {exc}")


def launch_browser() -> None:
    print("\n[*] Launching Central Kiosk Dashboard in default browser...")
    try:
        webbrowser.open(f"{HUB_URL}/kiosk")
    except Exception as exc:
        print(f"[!] Unable to open browser: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-Click Master Launcher for IPD Smart Sentinel")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    parser.add_argument("--beds", type=int, default=10, help="Number of simulated beds to stream")
    parser.add_argument("--auto-simulate", action="store_true", help="Automatically start telemetry stream on launch")
    args = parser.parse_args()

    print_banner()

    # 1. Pre-flight cleanup
    print("[*] Performing pre-flight runtime cleanup...")
    for db_file in ROOT.glob("ward_hub.db*"):
        try:
            db_file.unlink()
        except Exception:
            pass

    # 2. Start FastAPI Server via Uvicorn
    print("[*] Starting Smart Ward Hub Edge Server (FastAPI + Uvicorn)...")
    env = dict(os.environ)
    env["SW_DEVICE_TRUST_MODE"] = "enforce"
    env["SW_AUTO_CREATE_DB"] = "true"
    env["SW_SEED_DATA"] = "true"

    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    sim_process: subprocess.Popen | None = None

    try:
        if not wait_for_hub(timeout_seconds=12):
            print("[!] Failed to start Edge Hub. Please verify port 8000 is available.")
            return

        generate_qr_codes()

        if not args.no_browser:
            launch_browser()

        if args.auto_simulate:
            print(f"\n[*] Auto-starting background telemetry stream ({args.beds} beds)...")
            sim_process = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts" / "simulate_presentation.py"), "--beds", str(args.beds)],
                cwd=ROOT,
            )

        print("\n" + "=" * 80)
        print("🎛️  LIVE INTERACTIVE CLINICAL DEMO CONTROLLER")
        print("=" * 80)
        print("  [1] Start Live Patient Telemetry Stream (10 Beds)")
        print("  [2] Trigger Fall Alert on Bed-02 (Red Alert Demonstration)")
        print("  [3] Trigger Cardiac Vital Anomaly on Bed-05 (SpO2/Tachycardia)")
        print("  [4] Open Central Kiosk Dashboard (Browser)")
        print("  [5] Open Outside Admission Console (Browser)")
        print("  [6] Re-generate Fresh Patient QR Code Pack")
        print("  [7] Run Complete Master Regression Verification Suite")
        print("  [0] Graceful Shutdown & Exit")
        print("=" * 80)

        while True:
            try:
                choice = input("\n👉 Enter Command [0-7]: ").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if choice == "0":
                break
            elif choice == "1":
                if sim_process and sim_process.poll() is None:
                    print("[!] Simulation is already running. Stopping previous stream...")
                    sim_process.terminate()
                    sim_process.wait()
                print("[+] Spawning continuous telemetry stream for 10 beds...")
                sim_process = subprocess.Popen(
                    [sys.executable, str(ROOT / "scripts" / "simulate_presentation.py"), "--beds", "10"],
                    cwd=ROOT,
                )
            elif choice == "2":
                if sim_process and sim_process.poll() is None:
                    sim_process.terminate()
                    sim_process.wait()
                print("\n[🚨 TRIGGER] Simulating Sudden Bed Fall on BED-02 in 5 seconds...")
                sim_process = subprocess.Popen(
                    [sys.executable, str(ROOT / "scripts" / "simulate_presentation.py"), "--beds", "10", "--trigger-fall", "BED-02"],
                    cwd=ROOT,
                )
            elif choice == "3":
                if sim_process and sim_process.poll() is None:
                    sim_process.terminate()
                    sim_process.wait()
                print("\n[🚨 TRIGGER] Simulating Critical Cardiac Anomaly on BED-05 in 5 seconds...")
                sim_process = subprocess.Popen(
                    [sys.executable, str(ROOT / "scripts" / "simulate_presentation.py"), "--beds", "10", "--trigger-vitals", "BED-05"],
                    cwd=ROOT,
                )
            elif choice == "4":
                webbrowser.open(f"{HUB_URL}/kiosk")
            elif choice == "5":
                webbrowser.open(f"{HUB_URL}/admission")
            elif choice == "6":
                generate_qr_codes()
            elif choice == "7":
                print("\n[*] Running Master Regression Suite...")
                subprocess.run([sys.executable, str(ROOT / "run_all_tests.py")], cwd=ROOT)
            else:
                print("[!] Invalid command. Please select 0 to 7.")

    finally:
        print("\n[*] Shutting down Smart Ward Hub services...")
        if sim_process and sim_process.poll() is None:
            sim_process.terminate()
            sim_process.wait()
        if server_process and server_process.poll() is None:
            server_process.terminate()
            server_process.wait()
        print("[+] All services stopped cleanly. Ready to freeze! ✅")


if __name__ == "__main__":
    main()
