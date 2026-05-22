# Changelog

## 0.3.0
- Add full firmware inventory: one sensor per component from
  `/redfish/v1/UpdateService/FirmwareInventory` (System ROM, iLO, SPS,
  Intelligent Provisioning, NICs, CPLD, TPM, drives, etc.).
- Inventory is cached and refreshed every 6 hours (it rarely changes),
  so it doesn't add per-poll request load.

## 0.2.0
- CPU cores and threads pulled from `/redfish/v1/Systems/1/Processors/1`
  (`TotalCores` / `TotalThreads`).
- Memory health falls back to `Status.HealthRollup`.

## 0.1.0
- Initial release: Redfish-native integration for HPE iLO 5 / iLO 6.
- Session-token auth, single batched coordinator poll.
- Health, temperatures, fan, CPU/RAM, iLO + BIOS firmware,
  firmware integrity, power state, IML critical-event count.
