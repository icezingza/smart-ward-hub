# Smart Ward Hub - Smart Watch and HUB Intake Checklist

ใช้เอกสารนี้เมื่อได้รับ Smart Watch, gateway หรือ Fixed HUB สำหรับ laboratory bench เท่านั้น

สถานะเริ่มต้นของอุปกรณ์ทุกชิ้นคือ `UNTRUSTED_NON_CLINICAL_TEST_EQUIPMENT` จนกว่าจะผ่านการตรวจตามรายการนี้ ห้ามใช้อุปกรณ์กับผู้ป่วยจริง, ward network หรือ HIS จริง

## 1. ข้อมูลที่ต้องเก็บเมื่อรับอุปกรณ์

| รายการ | สิ่งที่ต้องบันทึก | ห้ามบันทึก |
|---|---|---|
| Asset ID | รหัส asset ภายในหรือรหัสที่ redacted | serial number เต็มใน public evidence |
| รุ่นและ firmware | model, firmware, bootloader, hardware revision | account หรือ password ที่มากับ vendor |
| การเชื่อมต่อ | BLE service/characteristic, Wi-Fi, MQTT, serial หรือ USB mode | production SSID, broker URL หรือ real credentials |
| ข้อมูล telemetry | schema, units, sample rate, timestamp, sequence, checksum/signature support | patient identifiers หรือ clinical notes |
| พลังงาน | battery state, charger, expected runtime, safe shutdown behavior | - |
| vendor materials | manual, SDK version, protocol specification, support window | unreviewed executable/binary |

ถ่ายภาพ label หรือ port ได้เฉพาะในพื้นที่ทดสอบ และตรวจว่าไม่มีชื่อผู้ป่วย, ward identifier หรือ secret ติดอยู่ในภาพก่อนเก็บเป็น evidence

## 2. Pre-connect safety check

- [ ] Hub อยู่บน test VLAN/SSID หรือ network ที่แยกจาก ward และ HIS
- [ ] เครื่องทดสอบใช้ disposable database, audit log และ telemetry path
- [ ] ไม่มี real patient token, name, HN, AN หรือ MRN ใน fixture
- [ ] vendor firmware/driver มี source, version และ hash ที่บันทึกได้
- [ ] ไม่มีการติดตั้ง remote-control software หรือ unsigned driver โดยไม่ review
- [ ] มีวิธีตัดไฟ/ถอด USB/ปิด Wi-Fi ได้ทันที
- [ ] บันทึก operator role, test date, git commit และ test scope

หากข้อใดไม่ผ่าน ให้หยุดที่ขั้นตอนนี้และบันทึกเป็น blocker

## 3. Capability discovery

ก่อนเขียน adapter หรือจับคู่ device ให้ตอบคำถามนี้จากเอกสาร vendor หรือการสังเกตใน isolated bench:

1. อุปกรณ์ส่งข้อมูลผ่าน BLE, Wi-Fi, serial, MQTT หรือ gateway protocol ใด
2. มี stable device ID หรือ rotating address
3. มี sequence number และ timestamp จากอุปกรณ์หรือไม่
4. telemetry field, unit และ sample rate คืออะไร
5. payload มี signature/attestation หรือเป็น plaintext
6. reconnect แล้ว device ส่งข้อมูลซ้ำหรือ reset sequence หรือไม่
7. firmware update, key rotation และ revocation ทำอย่างไร
8. มี SDK/cloud account บังคับใช้หรือไม่ และข้อมูลออกนอก site หรือไม่

ผลลัพธ์ต้องถูกระบุเป็นหนึ่งในสามสถานะ:

```text
COMPATIBLE_FOR_BENCH
NEEDS_GATEWAY_TRANSLATION
BLOCKED_UNKNOWN_PROTOCOL_OR_TRUST_MODEL
```

## 4. Bench onboarding sequence

| Step | Action | Pass condition | Evidence |
|---|---|---|---|
| D-001 | Inventory Hub/watch | model, firmware และ connection mode ถูกบันทึก | redacted inventory |
| D-002 | Observe-only discovery | device traffic ถูกจำแนกโดยไม่ forward เข้า Hub | protocol notes |
| D-003 | Synthetic frame mapping | source fields map สู่ `TelemetryPacket v1` แบบ versioned | mapping review |
| D-004 | Device identity | stable ID/gateway identity ถูกระบุ แต่ยังไม่ trusted | identity note |
| D-005 | Trust decision | signed payload หรือ approved gateway-attestation path ระบุชัด | trust design record |
| D-006 | Isolated telemetry | valid synthetic/bench packet เข้า adapter ได้ | redacted trace |
| D-007 | Negative cases | malformed, replay, missing trust และ PII fields ถูก reject | rejection evidence |
| D-008 | Disconnect/reconnect | sequence guard และ state recovery ยัง fail closed | recovery evidence |
| D-009 | Pressure | bounded queue/memory behavior ถูกบันทึก | resource snapshot |
| D-010 | Review | owner ตรวจ results และตัดสิน next gate | signed or pending decision |

ใช้ `Disabled` mode ได้เฉพาะ parser development. Evidence สำหรับ pilot ต้องใช้ `Enforce` mode ที่มี enrolled device credential หรือ approved gateway attestation ตาม [P2_EDGE_IOT_ADAPTER_ARCHITECTURE.md](../P2_EDGE_IOT_ADAPTER_ARCHITECTURE.md)

## 5. Hub acceptance minimum

ก่อนให้ Fixed HUB รับ telemetry จากอุปกรณ์ bench ต้องผ่าน:

- OS image, disk headroom, time source และ service account ถูกบันทึก
- backup/restore test ผ่านใน disposable environment
- adapter ทำงาน least privilege และไม่มี direct database access
- telemetry ingress ปฏิเสธ duplicate, out-of-order, unknown device และ PII fields
- audit logs ไม่มี raw frame, token, private key หรือ patient identifier
- rollback command และ operator contact ถูกบันทึก

## 6. Stop conditions

หยุดทันทีเมื่อพบ unknown driver prompt, traffic ที่ไม่อธิบายได้, vendor cloud login ที่ไม่มี approval, real patient identifier, raw credential, command field, sequence replay ที่ถูกยอมรับ, memory growth เกิน bound หรือการเชื่อมต่อใด ๆ ไปยัง ward/HIS จริง

## 7. After bench success

ผ่าน checklist นี้หมายถึงอุปกรณ์ "พร้อมเข้าสู่ technical validation" เท่านั้น ยังไม่ใช่ clinical validation, pilot approval หรือ production authorization

ขั้นต่อไปต้องส่ง redacted evidence ให้ security/reliability owner และ independent reviewer ก่อนเชื่อมต่อ environment ที่กว้างขึ้น
