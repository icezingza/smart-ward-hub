import argparse
import base64
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone
import requests
import threading

HUB_URL = "http://localhost:8000"
TOKEN = "test-token"

def request_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }

def generate_dummy_pubkey():
    # Ed25519 public key is 32 bytes, base64 encoded is 44 characters
    return base64.b64encode(uuid.uuid4().bytes * 2).decode('utf-8')

def enroll_device(device_id: str):
    print(f"[*] Enrolling device {device_id} into Zero-Trust...")
    payload = {
        "device_id": device_id,
        "key_id": f"key-{device_id}",
        "algorithm": "Ed25519",
        "public_key_b64": generate_dummy_pubkey()
    }
    resp = requests.post(f"{HUB_URL}/api/v1/device-trust/enroll", json=payload, headers=request_headers())
    if resp.status_code not in (200, 409):
        print(f"[!] Failed to enroll {device_id}: {resp.status_code} {resp.text}")
    
def pair_device(bed_no: str, device_id: str, risk_level: str = "Low"):
    print(f"[*] Pairing {device_id} to {bed_no}...")
    patient_token = f"anon-{uuid.uuid4().hex[:12]}"
    payload = {
        "patient_token": patient_token,
        "bed_no": bed_no,
        "device_id": device_id,
        "risk_level": risk_level,
        "placement_position": "WRIST",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    resp = requests.post(f"{HUB_URL}/api/v1/pairing", json=payload, headers=request_headers())
    if resp.status_code != 200:
        print(f"[!] Failed to pair {device_id}: {resp.status_code} {resp.text}")

def simulate_telemetry_loop(bed_no: str, device_id: str, trigger_event: str | None = None):
    seq = 0
    print(f"[+] Starting telemetry stream for {device_id} on {bed_no} (Trigger: {trigger_event})")
    
    # 5 seconds delay before trigger
    trigger_seq = 5 if trigger_event else -1
    
    while True:
        seq += 1
        accel_z = 1.0
        heart_rate = random.uniform(70.0, 75.0)
        spo2 = random.uniform(97.0, 100.0)
        
        if trigger_event == "FALL" and seq >= trigger_seq:
            accel_z = 3.5  # Simulate high g-force for fall
        elif trigger_event == "VITALS" and seq >= trigger_seq:
            heart_rate = 145.0  # Tachycardia
            spo2 = 88.0
            
        payload = {
            "schema_version": "1.0",
            "device_id": device_id,
            "sequence": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ppg": 0.85,
            "accel_x": random.uniform(-0.1, 0.1),
            "accel_y": random.uniform(-0.1, 0.1),
            "accel_z": accel_z,
            "skin_temp": 36.5,
            "battery_pct": 100.0,
            "heart_rate": heart_rate,
            "spo2": spo2
        }
        
        try:
            resp = requests.post(f"{HUB_URL}/api/v1/telemetry", json=payload, headers=request_headers())
            if resp.status_code not in (200, 202):
                print(f"[!] Telemetry rejected for {device_id}: {resp.status_code} {resp.text}")
        except Exception as e:
            pass
            
        time.sleep(1.0)

def main():
    parser = argparse.ArgumentParser(description="Live Presentation Simulator")
    parser.add_argument("--beds", type=int, default=10, help="Number of beds to simulate (max 30)")
    parser.add_argument("--trigger-fall", type=str, default=None, help="Bed number to trigger a fall (e.g. BED-02)")
    parser.add_argument("--trigger-vitals", type=str, default=None, help="Bed number to trigger a vital anomaly (e.g. BED-05)")
    args = parser.parse_args()
    
    print("=======================================")
    print("🏥 Smart Ward Hub - Live Simulator 🚀")
    print("=======================================")
    
    beds_count = min(args.beds, 30)
    threads = []
    
    for i in range(1, beds_count + 1):
        bed_no = f"BED-{i:02d}"
        device_id = f"wristband-{i:02d}"
        risk_level = "High" if bed_no in (args.trigger_fall, args.trigger_vitals) else "Low"
        
        enroll_device(device_id)
        pair_device(bed_no, device_id, risk_level)
        
        trigger = None
        if bed_no == args.trigger_fall:
            trigger = "FALL"
        elif bed_no == args.trigger_vitals:
            trigger = "VITALS"
            
        t = threading.Thread(target=simulate_telemetry_loop, args=(bed_no, device_id, trigger), daemon=True)
        t.start()
        threads.append(t)
        
    print("\n[+] All simulated patients are now streaming data!")
    print("[!] Press Ctrl+C to stop the simulation.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Stopping simulation...")
        sys.exit(0)

if __name__ == "__main__":
    main()
