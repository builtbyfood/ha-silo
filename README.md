# SiLO for Home Assistant
Your HPE iLO fleet in home assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/builtbyfood/ha-silo)](https://github.com/builtbyfood/ha-silo/releases)
[![Validate](https://github.com/builtbyfood/ha-silo/actions/workflows/validate.yml/badge.svg)](https://github.com/builtbyfood/ha-silo/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A lightweight, **Redfish-native** Home Assistant integration for HPE ProLiant
servers managed by **iLO 5 / iLO 6**.

This component talks to the modern Redfish REST API directly, so it works on Gen10/Gen11
hardware where the old approach is dead.

![Device page](images/device.png)

## Why this exists

iLO 6 dropped the old RIBCL interface. Integrations built on `python-hpilo`
connect but then read nothing. This one uses Redfish end to end, with proper
session-token auth so it doesn't exhaust the iLO's session pool.

## Features

- **UI config flow** — add each server by host + a read-only iLO account. No YAML.
- **Session-token auth** — logs in once per cycle, reuses the `X-Auth-Token` for
  all reads, then logs out. Avoids the `NoValidSession` errors that per-request
  Basic auth causes on iLO.
- **One batched coordinator poll** feeds every entity — a handful of requests,
  not dozens, protecting the limited iLO management processor.
- **Auto-created entities** you can sift down to what you want.

## Screenshots

| Search | Setup |
| --- | --- |
| ![Search](images/search-silo.png) | ![Setup](images/setup.png) ![Setup2] (images/setup-filled.png) ![Name] (images/naming.png) |

| Device page | Dashboard card |
| --- | --- |
| ![Device](images/device.png) | ![Card1](images/added1.png) ![Card2] (images/added2.png) |


## Entities

| Entity | Source |
| --- | --- |
| Health (binary, problem) | `Systems/1` `Status` |
| Power state | `Systems/1` `PowerState` |
| CPU model / count / cores / threads | `Systems/1` + `Processors/1` |
| RAM, memory health | `Systems/1` `MemorySummary` |
| Temperatures (per active sensor) | `Chassis/1/Thermal` |
| Fan speed (%) | `Chassis/1/Thermal` |
| iLO firmware, BIOS version | `Managers/1`, `Systems/1` |
| Firmware integrity + last scan | `UpdateService` (HPE OEM) |
| Firmware components (per item) | `UpdateService/FirmwareInventory` |
| Critical events (count) | `Systems/1/LogServices/Event` |

## Requirements

- Home Assistant 2024.1 or newer
- An iLO account with read access (a dedicated read-only user is recommended)
- iLO 5 or iLO 6 (Gen10 / Gen11)

## Installation

### HACS (custom repository)
1. HACS → ⋮ (top right) → **Custom repositories**
2. Add `https://github.com/builtbyfood/ha-silo`, category **Integration**
3. Install **SiLO**, then restart Home Assistant

### Manual
Copy `custom_components/ha-silo/` into your HA `config/custom_components/`
directory and restart.

## Configuration

Settings → Devices & Services → **Add Integration** → **SiLO**.
Enter the iLO host/IP, username, and password. Leave "Verify SSL" off for the
default self-signed iLO certificate. Set the polling interval (default 120 s;
longer is gentler on the iLO). Add one entry per server.

## Notes

- **Power draw:** entry-tier models (e.g. ProLiant MicroServer Gen11) report
  `HasPowerMetering: false` and have no power-metering hardware, so no watt
  reading is possible by any method — a hardware limit, not a bug. Use a smart
  plug or metered PDU if you need consumption.
- **Firmware inventory** is cached and refreshed every 6 hours (it only changes
  on an update), so it doesn't add load to every poll.
- This is an independent project, not affiliated with or endorsed by HPE.
  "iLO", "ProLiant", and "Redfish" are trademarks of their respective owners.

## Tested on

- ProLiant MicroServer Gen11, iLO 6 v1.74

(Reports of other Gen10/Gen11 models welcome — open an issue.)

## License

MIT — see [LICENSE](LICENSE).
