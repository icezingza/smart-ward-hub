# Smart Ward Hub — Tablet Hardware Decision Record

**Devices evaluated:** Acer Spin N17H2 / SP111-32N family and BMAX MaxPad i11 S  
**Decision status:** provisional bench-prototype decision; physical verification required  
**Software status:** controlled production prototype; clinical validation pending

## 1. Evidence boundary

The Acer N17H2 identifier maps to the Spin 1 SP111-32N family, but the family contains configuration differences. Acer's representative store configuration lists Windows 10 Home 64-bit, Intel Pentium N4200, 4 GB DDR3L, 128 GB flash, 11.6-inch 1920×1080 multitouch display, Wi-Fi 802.11ac, Bluetooth 4.0, two USB ports, HDMI and a 45 W adapter. The exact unit's CPU, storage size, OS edition, battery health and ports must still be checked on the device.

The official BMAX I11 S listing reports UNISOC T606, 4 GB physical plus 8 GB memory expansion, 128 GB storage, Android 15, 11-inch 1280×800 IPS display, dual-band Wi-Fi, Bluetooth 5.0, USB-C charging, microSD and an 8000 mAh battery. A benchmark listing identifies a similar device as Android 14 with 4 GB RAM, so the physical tablet's installed version and memory configuration must be verified. Neither source establishes NFC, wired Ethernet, secure boot/TPM, Android device-owner policy or local support for the current Python/FastAPI backend.

## 2. Comparison

| Dimension | Acer Spin N17H2 / SP111-32N family | BMAX MaxPad I11 S | Assessment for Smart Ward Hub |
|---|---|---|---|
| Local Edge runtime | Full Windows/Linux-capable x86 convertible; current FastAPI/Python path is technically plausible | Android ARM tablet; current Python/FastAPI service cannot be assumed to run as a managed local appliance | **Acer advantage** |
| Touch/UI | 11.6-inch multitouch, representative Full HD | 11-inch IPS 1280×800 multitouch | Acer gives more workspace; BMAX is lighter |
| CPU/RAM | Representative Pentium N4200, 4 GB | T606 octa-core, 4 GB physical plus virtual expansion | BMAX may be newer/faster for UI, but virtual RAM is not physical RAM |
| Storage | 64/128 GB flash/eMMC depending SKU; likely not practically upgradeable | 128 GB listed; microSD expansion; storage type/configuration requires verification | Neither should be trusted for pilot until storage health and write endurance are tested |
| Connectivity | Wi-Fi ac, Bluetooth 4.0, two USB and HDMI in representative SKU | Wi-Fi ac, Bluetooth 5.0, USB-C and microSD; NFC/Ethernet not confirmed | Acer has more convenient peripheral options; both need NFC/LAN verification |
| Kiosk/auto-run | Windows kiosk/Assigned Access or Linux systemd + browser shell are possible | Android device-owner/kiosk is possible only if OEM policy and enrollment are supported | Acer is easier for current software; BMAX requires Android-native deployment validation |
| Power | 45 W adapter; used battery health is a major unknown | 8000 mAh/30.8 Wh listed; charger/dock and always-on behavior require test | BMAX has newer-looking battery capacity; neither proves 24/7 safety |
| Physical role | Convertible notebook; keyboard/hinge are less ideal for a fixed ward kiosk | Light tablet form factor, better for touch-only station | BMAX advantage as UI shell |
| Privacy/security | Mature OS controls are available, but old Windows lifecycle and device age matter | Android privacy/kiosk policy and update support need verification | Acer for controlled prototype; BMAX for display after platform validation |

## 3. Provisional decision

For the **first functional Edge prototype using the existing Smart Ward Hub Python/FastAPI code**, use the Acer Spin N17H2 as the primary host if it has a full Windows edition or can boot a supported Linux distribution. It is the more realistic candidate for running SQLite WAL, `EdgeTelemetryStore`, Device Trust verification, local kiosk service and the current regression suite.

Use the BMAX i11_s as the preferred **touch/UI and physical kiosk candidate** only after verifying Android device-owner mode, automatic app launch, persistent local storage behavior, NFC/BLE availability and the ability to run the chosen local Edge service. If the BMAX cannot run the backend reliably, it should display a browser-based UI served by the Acer during the bench phase; this is a temporary two-device prototype, not the final Tablet-only architecture.

If the requirement is strictly **one physical tablet only**, the Acer is the safer first choice for the current software baseline. The BMAX is the more attractive final form factor, but it needs a separate Android-native or validated embedded-runtime path before it can become the sovereign Edge source of truth.

## 4. Required checks on the actual devices

| Check | Acer | BMAX | Pass condition |
|---|---:|---:|---|
| Exact OS edition/version | Required | Required | Supported kiosk and service supervision |
| CPU/RAM/storage actual values | Required | Required | Matches deployment sizing and no misleading virtual RAM assumption |
| Storage health/write test | Required | Required | SQLite WAL/checkpoint/audit write workload remains stable |
| Battery health and thermal soak | Required | Required | 8–12 hour powered operation without unexpected sleep/throttle |
| Touch and glove interaction | Required | Required | Large tap targets and no ghost input |
| NFC reader availability | Required | Required | Reader and driver/API can read pointer without storing patient identity |
| BLE capability | Required | Required | C60/proxy test packets received and verified |
| Wired LAN through dock/USB | Required | Required | Stable ward VLAN connectivity and offline fallback |
| Auto-boot and kiosk escape resistance | Required | Required | Service/UI starts without keyboard and ordinary users cannot exit kiosk |
| Reboot restore | Required | Required | Pairing/session/alert/checkpoint state restored with freshness flags |
| Power interruption | Required | Required | No duplicate pairing, purge or handover; manual fallback visible |

## 5. Recommended prototype sequence

Start with the Acer as an **Edge host and development kiosk**. Install the current backend, apply the latest Alembic migration, enable `SW_DEVICE_TRUST_MODE=observe`, launch the local kiosk route, and validate auto-start, checkpoint restore, stale-state banners, session workflows and offline operation.

Then connect or test the BMAX as a separate touch display only if its browser, kiosk and network behavior are stable. If the BMAX passes Android device-owner and embedded-runtime tests, evaluate a migration of the local Edge service; otherwise keep the Acer as the source of truth and label the BMAX as a UI terminal during bench validation.

## References

[1]: https://www.bmaxit.com/MaxPad-I11-S-pd573114068.html "BMAX MaxPad I11 S official product page"
[2]: https://benchmarks.ul.com/hardware/tablet/BMAX+MaxPad+I11+S+review "UL benchmark BMAX MaxPad I11 S listing"
[3]: https://store.acer.com/en-ca/spin-1-laptop-sp111-32n-p7cn "Acer Spin 1 SP111-32N representative official store configuration"
[4]: https://community.acer.com/en/discussion/544673/spin-1-sp111-32n-m-2-ssd-slot-usable "Acer Community discussion on SP111-32N storage expansion"
[5]: https://www.ultrabookreview.com/18578-acer-spin-1-review/ "Acer Spin 1 SP111-32N family review"
