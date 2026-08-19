# Hardware research notes — 2026-08-19

## BMAX MaxPad I11 S

Official BMAX product page: https://www.bmaxit.com/MaxPad-I11-S-pd573114068.html

Reported specifications: UNISOC T606, 2x Cortex-A75 + 6x Cortex-A55 at 1.6 GHz, Mali G57 GPU, 4 GB physical RAM plus 8 GB expansion/virtual memory, 128 GB storage, Android 15, 11-inch IPS 1280x800 display, dual-band 802.11a/b/g/n/ac Wi-Fi, Bluetooth 5.0, USB-C charging, microSD expansion, 8000 mAh/30.8 Wh battery, approximately 530 g. The official page does not establish NFC, wired Ethernet, device-owner kiosk policy, secure boot/TPM, or support for running the current Python/FastAPI backend locally.

UL benchmark page: https://benchmarks.ul.com/hardware/tablet/BMAX+MaxPad+I11+S+review

The benchmark entry identifies a Tiger T606, 4 GB memory, 128 GB storage, Android 14 in the tested listing, Bluetooth/WLAN and USB Type-C. This conflicts with the newer official listing showing Android 15 and “4GB+8GB expansion”, so the physical tablet’s Android version and memory configuration must be confirmed on-device.

## Acer Spin N17H2

Source: https://www.ultrabookreview.com/18578-acer-spin-1-review/

The N17H2 is associated with Acer Spin 1 SP111-32N. The reviewed family is a Windows convertible with an 11.6-inch touch display, commonly Intel Pentium N4200, 4 GB LPDDR3 and 64/128 GB storage depending on configuration. The source reports that Windows 10 S may be present on some units, Ubuntu can support touchscreen operation, and internal expansion/battery behavior is model/configuration dependent. These are family-level/review observations, not a verified serial-specific specification.

## Provisional comparison

BMAX is better as a lightweight touch kiosk/display candidate but is not yet proven to run the current Python/FastAPI Edge runtime locally or provide required NFC/Ethernet/kiosk controls. Acer Spin N17H2 is more promising as a local Edge software host if it runs a full Windows/Linux environment, but its old CPU/RAM/storage and battery condition are concerns. The final choice requires on-device verification of OS, RAM, storage health, ports, touch, Bluetooth, NFC availability, kiosk/auto-start capability, and sustained power behavior.

## Acer source confirmation

Acer Store page: https://store.acer.com/en-ca/spin-1-laptop-sp111-32n-p7cn

A representative SP111-32N configuration is listed with Windows 10 Home 64-bit, Intel Pentium N4200 1.10 GHz (up to 2.50 GHz), 4 GB DDR3L, 128 GB flash, 11.6-inch Full HD IPS multitouch display, 802.11a/b/g/n/ac Wi-Fi, Bluetooth 4.0, two USB ports, HDMI, 2-cell 4670 mAh battery and 45 W adapter. N17H2 is a family/model identifier and exact SKU configuration must still be verified on the physical unit.

Acer Community discussion: https://community.acer.com/en/discussion/544673/spin-1-sp111-32n-m-2-ssd-slot-usable

The discussion indicates that many SP111-32N boards do not have a usable M.2 connector and use eMMC/flash storage. This is a community report, not a universal specification, but it supports treating the Acer storage as non-upgradeable until the exact unit is checked.

## Updated provisional decision

For running the existing Python/FastAPI Edge runtime locally, Acer Spin N17H2 is the stronger candidate than BMAX i11_s because it is a full 64-bit Windows convertible with USB, HDMI, touch and a conventional desktop OS path. However, 4 GB RAM, old Pentium N4200, aging eMMC/flash, Windows 10 lifecycle, battery condition and lack of confirmed NFC/Ethernet remain significant pilot risks.

BMAX i11_s is the better lightweight kiosk/display candidate, but the official Android 15/T606 specification does not prove that the current Python/FastAPI backend can run locally or that NFC, wired Ethernet, kiosk device-owner controls and persistent service supervision are available. It is better treated as UI/kiosk or a future Android-native port until verified.
