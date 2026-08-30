# Smart Ward Hub

Smart Ward Hub เป็น **controlled production prototype** สำหรับระบบติดตามผู้ป่วยแบบ **Sovereign Edge / Offline-first** ที่ออกแบบให้ Fixed Hub ประจำวอร์ดทำงานได้แม้การเชื่อมต่อภายนอกไม่เสถียร โดยใช้ SQLite WAL เป็นแหล่งความจริงภายใน Edge, ใช้ RAM ring buffer เป็นชั้นเร่งความเร็ว และแยกข้อมูลผู้ป่วยออกจาก Edge ด้วย opaque `patient_token` เท่านั้น

> สถานะปัจจุบัน: **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation**, **clinical validation pending**. ผลการทดสอบใน repository นี้เป็น software verification และ deterministic simulation เว้นแต่จะระบุเป็นหลักฐานจากอุปกรณ์จริงโดยชัดเจน

## จุดเด่นของระบบ

ระบบมุ่งเน้นหกแกนหลัก ได้แก่ Sovereign Edge และ Offline-first operation, Zero-PII edge boundary, Patient Safety Intelligence, Tamper-Evident Evidence, HIS/EMR interoperability และ Device Trust with secure provisioning. นอกจากนี้ยังรองรับ Outside-in Ward Workflow สำหรับตรวจเตียงว่างและเตรียม admission จากนอกวอร์ด, Roaming Tablet synchronization ที่ให้ Fixed Hub เป็น authority, และขอบเขต Edge IoT adapters สำหรับ MQTT, WebSocket, Serial และ BLE

| ความสามารถ | ขอบเขตที่ตรวจสอบแล้ว |
|---|---|
| Edge persistence | SQLite WAL, migrations, safe sync/purge lifecycle |
| Telemetry | bounded high-concurrency ingestion, `TelemetryPacket v1`, duplicate/out-of-order rejection |
| Patient safety | AI triage baseline, silent-fall detection, alert persistence and acknowledgement gates |
| Forensics | SHA-256 hash chain, tamper detection, incident-triggered freeze boundary, hardened local anchor receipt/readback baseline |
| Interoperability | structured FHIR handover acknowledgement and identity-matching purge gate |
| Trust and workflow | bearer/OIDC-ready auth boundary, Ed25519 device trust, outside-in admission, roaming snapshot/commands |
| IoT baseline | transport-neutral adapters, bounded Serial framing, CRC32, partial-read and pressure simulations |
| Micro-RAG | bilingual/adversarial hallucination suite, response adapter, approved registry and rebuildable index |
| Safety governance | Clinical shadow-mode policy gate, safe signal labels, review classifications and stop/resume control contract |

## สิ่งที่ผลทดสอบยืนยัน และสิ่งที่ยังไม่ยืนยัน

Master regression suite ครอบคลุม Phase 1–6, P0 hardening, residual controls, Device Trust, ward workflow, outside-in admission, roaming synchronization, Micro-RAG baseline, P2-002 adapters, Serial framing, network pressure simulation และ Serial bench runner safety. ผลลัพธ์เหล่านี้แสดงว่า software baseline ทำงานตาม contract ที่กำหนดภายใต้สภาพแวดล้อมทดสอบที่ควบคุมได้ แต่ไม่ใช่หลักฐานว่าอุปกรณ์จริง, ระบบ HIS จริง หรือการใช้งานทางคลินิกผ่านการรับรองแล้ว

| หลักฐาน | สถานะ |
|---|---|
| Unit/integration/regression tests ใน sandbox | ผ่าน |
| Deterministic concurrency, 30-day และ pressure simulations | ผ่านใน software simulation |
| Acer Spin N17H2 host inventory | ตรวจแบบ read-only; Windows 11 Pro build 26200, Python 3.14.3, ไม่พบ COM port |
| Physical USB-serial loopback on Acer | ยังไม่เริ่ม; ต้องมี fixture และ deploy project บน Acer |
| HIS/Admission Gateway จริง | รอ integration |
| OIDC/mTLS กับ IdP จริง | รอ external validation |
| Clinical validation และ shadow-mode | รอ clinical governance |
| External forensic anchoring | Local FileAnchorStore hardening and software external-adapter contract passed; independent WORM service and cross-boundary verification pending |
| Device Trust key custody | Software custody lifecycle passed; manufacturer CA/HSM/secure element and hardware custody pending |
| Clinical shadow-mode | Software governance contract and expanded Zero-PII/metrics tests passed; clinical owner, governance approval, human-factors and real shadow review pending |
| Clinical validation readiness | Software preflight contract passed; real-world authorization remains false and external governance gates are open |
| External validation coordination | Ten-gate evidence package passed software contract tests; external review, physical gates and clinical authorization remain open |
| Host hardening, power-loss testing | รอ external validation |

จึงห้ามตีความ repository นี้ว่าเป็น **clinical-ready**, **tamper-proof**, **HIPAA/PDPA compliant 100%** หรือ **production-ready** จาก functional tests เพียงอย่างเดียว

## โครงสร้างสำคัญ

`main.py` เป็น FastAPI application หลัก ส่วน `database.py`, `models.py` และ Alembic migrations ดูแล persistence contract. `edge_iot_adapters.py`, `serial_framing.py`, `network_pressure_simulation.py` และ `serial_bench_runner.py` เป็นขอบเขต P2-002 สำหรับ ingestion และ bench validation. `evals/micro_rag/` เก็บ corpus, response adapter, approved registry, rebuildable index และ evaluation suites. เอกสาร `prd.md`, `design.md`, `architecture.md`, `agents.md`, `memory.md`, `tasks.md`, `rules.md` และ `skills.md` เป็น AI-native project system สำหรับทำให้การพัฒนาต่อมีบริบทและ guardrails ที่สม่ำเสมอ

## การติดตั้งและทดสอบ software baseline

ใช้ Python 3.12 ขึ้นไปใน environment ที่แยกจาก production และติดตั้ง dependencies จาก `requirements.txt`:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 run_all_tests.py
```

สำหรับตรวจ checkout แบบเดียวกับ CI ให้ใช้ `scripts/verify_local.sh` จาก Bash/Git Bash:

```bash
bash scripts/verify_local.sh
```

สคริปต์นี้สร้าง virtual environment แยก, ตรวจ compile/dependencies, ตรวจช่องโหว่ dependencies, รัน master regression suite และยืนยันว่าไม่มี runtime artifacts ถูกสร้างเป็นไฟล์ติดตามใน repository

สำหรับตรวจ Serial framing โดยไม่เปิดพอร์ต ให้ใช้คำสั่งต่อไปนี้:

```bash
python3 serial_bench_runner.py --list-ports
python3 serial_bench_runner.py --dry-run --output serial_bench_evidence.json
```

การทดสอบ physical ต้องมี USB-serial loopback fixture ที่ไม่ใช่อุปกรณ์ production, ต้องระบุพอร์ตอย่างเจาะจง และต้องใช้คำยืนยันตรงตัว:

```bash
python3 serial_bench_runner.py \
  --port COMx \
  --baudrate 115200 \
  --confirm-physical I_HAVE_A_NONPRODUCTION_LOOPBACK \
  --output serial_bench_evidence.json
```

ห้ามรัน physical command จนกว่าจะตรวจว่าพอร์ตเป็น fixture ทดสอบที่ปลอดภัย, ไม่มี patient device อยู่ในเส้นทาง, ไม่มีข้อมูลผู้ป่วยจริง และมี operator ที่รับผิดชอบ bench gate

## จำลอง Smart Watch เพื่อพัฒนา HUB

ขณะรออุปกรณ์จริง สามารถใช้ `smartwatch_simulator.py` สร้าง telemetry สังเคราะห์ตาม `TelemetryPacket v1` เพื่อพัฒนาและทดสอบ HUB ได้ โดยค่าเริ่มต้นเป็น dry-run จึงไม่ส่งข้อมูลผ่านเครือข่าย:

```bash
python smartwatch_simulator.py --scenario normal
python smartwatch_simulator.py --scenario replay
python smartwatch_simulator.py --scenario out_of_order
python smartwatch_simulator.py --scenario offline_reconnect
```

มีรายละเอียดเรื่องขอบเขตและการเชื่อมต่อ Hub บนเครื่องตนเองใน `docs/SMARTWATCH_SIMULATOR_GUIDE.md` ตัวจำลองใช้ข้อมูล synthetic เท่านั้น ไม่ยืนยันความแม่นยำของ sensor, BLE/radio, battery, firmware หรือผลทางคลินิก

## Simulation Matrix

รัน simulation matrix แบบรวมทุก feature/risk ที่ตรวจด้วย software ได้ในเครื่องเดียว:

```bash
python software_simulation_matrix.py --execute
```

คำสั่งนี้รัน telemetry, transport pressure, identity/trust, workflow, alerts, recovery, forensics, HIS/FHIR, worker และ deployment-configuration fixtures โดยไม่ติดต่อ network หรือ hardware จริง รายละเอียด coverage และ external gates อยู่ใน `docs/SOFTWARE_SIMULATION_COVERAGE_MATRIX.md`

## Ward Simulation: 40 Beds / 1 Hub

```bash
python ward_scale_simulation.py --beds 40 --ticks 8
```

## Virtual Wristband Telemetry Streamer: 30 Beds

สร้าง telemetry สังเคราะห์จากสายรัดข้อมือเสมือน 30 เตียงพร้อมกัน รองรับ `normal`,
`cardiac_distress`, `silent_fall` และ `mixed` โดยค่าเริ่มต้นเป็น dry-run:

```powershell
python virtual_wristband_telemetry_streamer.py --beds 30 --samples 8 --scenario mixed
python test_virtual_wristband_telemetry_streamer.py
```

การส่งเข้า HUB ใช้ได้เฉพาะ loopback และต้อง pair อุปกรณ์สังเคราะห์ไว้ก่อน:

```powershell
python virtual_wristband_telemetry_streamer.py --send --hub-url http://127.0.0.1:8000 --token <local-token>
```

Streamer เก็บ 6-axis (`accel` + `gyro`) ในหลักฐานจำลอง แต่ map เข้า `TelemetryPacket v1`
เฉพาะฟิลด์ที่ HUB รองรับในปัจจุบัน จึงไม่ใช่การยืนยันว่า Band จริงส่งข้อมูลเหล่านี้ผ่าน BLE ได้
และ latency ที่วัดได้เป็นเพียง loopback software evidence ไม่ใช่ผลทดสอบ production หรือ clinical

## Medical Black Box

เมื่อเกิด alert ระบบเลือก telemetry จาก RAM ring buffer ย้อนหลังตาม time window 600 วินาที,
freeze เป็น forensic package, ต่อ SHA-256 hash chain และรองรับ RSA-PSS/SHA-256 signature
จาก private-key file ที่ operator provision ภายนอก repository รายละเอียด contract, configuration
และข้อจำกัดด้านกฎหมายอยู่ใน `docs/MEDICAL_BLACK_BOX_SPEC.md`

ฟังก์ชันนี้เป็น tamper-evident software baseline เท่านั้น ไม่ใช่ WORM storage, ISO certification
หรือการรับประกันว่าหลักฐานจะถูกรับฟังในศาลโดยอัตโนมัติ

จำลอง 40 เตียงพร้อม injected scenarios: fall, vital anomaly, device disconnect, perimeter warning และ blood-pressure capability gap โดยไม่ใช้ข้อมูลผู้ป่วยจริง ดูข้อจำกัดของค่า BP/location และผลที่คาดหวังใน `docs/WARD_SCALE_SIMULATION_GUIDE.md`

## Hospital Full-System Simulation

```bash
python hospital_full_system_simulation.py --wards 5 --beds-per-ward 40 --ticks 8
```

จำลอง FastAPI end-to-end หลายวอร์ดผ่าน Hub จริงใน database ชั่วคราว และตรวจ Hub-to-Server retain/retry/structured-ack contract โดยไม่ติดต่อ Server จริง แนวทาง data path อยู่ใน `docs/HUB_TO_SERVER_DATA_PATH.md`

## การรัน API ในโหมดพัฒนา

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

ก่อนใช้งานควรอ่าน `OPERATIONS_RUNBOOK.md`, `SECURITY_BASELINE.md`, `P0_STATUS_REPORT.md`, `P2_EDGE_IOT_ADAPTER_READINESS_REPORT.md`, `SERIAL_BENCH_VALIDATION_PLAN.md` และ `ACER_BENCH_READONLY_INVENTORY.md` เพื่อแยก software evidence ออกจาก physical, security และ clinical gates

## สถานะการเผยแพร่

Repository นี้ควรเผยแพร่แบบ private ระหว่างช่วง controlled prototype และ pilot preparation. Runtime database, audit log, generated simulation output, credentials และ private keys ถูกกำหนดไว้ใน `.gitignore` และต้องไม่ถูก commit
