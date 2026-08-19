---
name: smart-ward-create-vps
description: Prepare or review the Fixed Edge Hub host for Smart Ward Hub. Use when provisioning Acer Spin N17H2 or another controlled host, hardening Linux/Windows boundaries, configuring firewall/SSH, or validating host prerequisites.
---

# Smart Ward host preparation

Use the global `create-vps` skill as the procedure baseline, then apply this project overlay.

## Protect the architecture

Treat the Acer Spin N17H2 as the **Fixed Edge Hub** and the BMAX i11_s as a future roaming client. Keep SQLite and the local FastAPI service on the Edge Hub. Do not move patient identity mapping, forensic authority or clinical alert authority into the tablet or a generic control-plane service.

## Required gates

Inventory OS, disk encryption status, operator account, patch state, firewall, service binding, time source, power behavior, backup destination and network path. Prefer a private ward network and bind administrative endpoints narrowly. Record every result as `Implemented`, `Experimental`, `Planned`, `Not Found` or `Unverified`.

Never claim that a host is production-ready from a configuration file alone. A real bench run must verify reboot recovery, service restart, thermal/charging behavior, disk-full response, network interruption and power-loss recovery.

## Do not collect

Do not place raw HN, patient name, national ID, clinical notes, bearer tokens or private keys in host reports. Use ward identifier, service name, redacted device identifier and key fingerprint only.

## Approval boundary

Require explicit approval before opening a port, changing firewall rules, enabling remote administration, installing packages, creating a non-root operator, or applying a hardening change to a live host.
