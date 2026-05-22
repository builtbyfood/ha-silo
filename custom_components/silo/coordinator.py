"""Redfish client and data update coordinator for SiLO."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

SYSTEM_PATH = "/redfish/v1/Systems/1"
PROCESSOR_PATH = "/redfish/v1/Systems/1/Processors/1"
THERMAL_PATH = "/redfish/v1/Chassis/1/Thermal"
MANAGER_PATH = "/redfish/v1/Managers/1"
UPDATE_PATH = "/redfish/v1/UpdateService"
FW_INVENTORY_PATH = "/redfish/v1/UpdateService/FirmwareInventory"
EVENTS_PATH = "/redfish/v1/Systems/1/LogServices/Event/Entries"
SESSIONS_PATH = "/redfish/v1/SessionService/Sessions"

# Firmware inventory is static between updates, so refresh it infrequently
# instead of fetching every member on every poll.
FW_REFRESH_SECONDS = 21600  # 6 hours


class RedfishAuthError(Exception):
    """Authentication failed."""


def _health(status: dict | None):
    """Return Health, falling back to HealthRollup (HPE populates the rollup)."""
    status = status or {}
    return status.get("Health") or status.get("HealthRollup")


class RedfishClient:
    """Minimal async Redfish client using session-token auth."""

    def __init__(self, hass: HomeAssistant, host: str, user: str, password: str, verify_ssl: bool):
        self._base = f"https://{host}"
        self._user = user
        self._password = password
        self._verify_ssl = verify_ssl
        self._session = async_get_clientsession(hass, verify_ssl=verify_ssl)

    async def login(self) -> tuple[str, str | None]:
        """Create a Redfish session, return (token, session_location)."""
        try:
            async with self._session.post(
                self._base + SESSIONS_PATH,
                json={"UserName": self._user, "Password": self._password},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise RedfishAuthError(f"auth rejected ({resp.status})")
                if resp.status not in (200, 201):
                    raise UpdateFailed(f"Redfish login failed: HTTP {resp.status}")
                token = resp.headers.get("X-Auth-Token")
                location = resp.headers.get("Location")
                if not token:
                    raise UpdateFailed("Redfish login returned no X-Auth-Token")
                return token, location
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Cannot reach iLO: {err}") from err

    async def logout(self, token: str, location: str | None) -> None:
        """Best-effort session teardown."""
        if not location:
            return
        url = location if location.startswith("http") else self._base + location
        try:
            async with self._session.delete(
                url, headers={"X-Auth-Token": token}, timeout=aiohttp.ClientTimeout(total=15)
            ):
                pass
        except (aiohttp.ClientError, TimeoutError):
            pass

    async def get(self, token: str, path: str) -> dict | None:
        """GET a Redfish resource as JSON, or None on failure."""
        try:
            async with self._session.get(
                self._base + path,
                headers={"X-Auth-Token": token},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None


async def async_validate(hass: HomeAssistant, host: str, user: str, password: str, verify_ssl: bool) -> dict:
    """Validate connectivity/credentials and return basic identity info."""
    client = RedfishClient(hass, host, user, password, verify_ssl)
    token, location = await client.login()
    try:
        system = await client.get(token, SYSTEM_PATH)
    finally:
        await client.logout(token, location)
    if not system:
        raise UpdateFailed("Connected but could not read /Systems/1")
    return {
        "serial": system.get("SerialNumber"),
        "model": system.get("Model"),
        "name": system.get("Model") or f"HPE iLO @ {host}",
    }


class SiLOCoordinator(DataUpdateCoordinator):
    """Single batched poll across the useful Redfish endpoints."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self._client = RedfishClient(
            hass,
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
        self._fw_inventory: dict[str, str] = {}
        self._fw_inventory_ts: float = 0.0

    async def _fetch_firmware_inventory(self, token: str) -> dict[str, str] | None:
        """Walk the FirmwareInventory collection (members are links, not expanded)."""
        coll = await self._client.get(token, FW_INVENTORY_PATH)
        if not coll:
            return None
        paths = [m.get("@odata.id") for m in (coll.get("Members") or []) if m.get("@odata.id")]
        if not paths:
            return None
        results = await asyncio.gather(
            *[self._client.get(token, p) for p in paths], return_exceptions=True
        )
        inv: dict[str, str] = {}
        for r in results:
            if isinstance(r, dict):
                name = r.get("Name")
                version = r.get("Version")
                if name and version:
                    inv[name] = version
        return inv or None

    async def _async_update_data(self) -> dict:
        try:
            token, location = await self._client.login()
        except RedfishAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        try:
            system = await self._client.get(token, SYSTEM_PATH)
            processor = await self._client.get(token, PROCESSOR_PATH)
            thermal = await self._client.get(token, THERMAL_PATH)
            manager = await self._client.get(token, MANAGER_PATH)
            update = await self._client.get(token, UPDATE_PATH)
            try:
                events = await self._client.get(token, EVENTS_PATH)
            except Exception:  # noqa: BLE001 - event log is best-effort
                events = None

            # Refresh the (static) firmware inventory only periodically.
            now = time.monotonic()
            if not self._fw_inventory or (now - self._fw_inventory_ts) > FW_REFRESH_SECONDS:
                inv = await self._fetch_firmware_inventory(token)
                if inv:
                    self._fw_inventory = inv
                    self._fw_inventory_ts = now
        finally:
            await self._client.logout(token, location)

        data = self._parse(system, processor, thermal, manager, update, events)
        data["firmware"] = dict(self._fw_inventory)
        return data

    @staticmethod
    def _parse(system, processor, thermal, manager, update, events) -> dict:
        system = system or {}
        processor = processor or {}
        thermal = thermal or {}
        manager = manager or {}
        update = update or {}

        proc = system.get("ProcessorSummary") or {}
        mem = system.get("MemorySummary") or {}
        integrity = (((update.get("Oem") or {}).get("Hpe") or {}).get("FirmwareIntegrity") or {})

        cpu_cores = processor.get("TotalCores") or proc.get("CoreCount")
        cpu_threads = processor.get("TotalThreads") or proc.get("LogicalProcessorCount")

        data: dict = {
            "health": _health(system.get("Status")),
            "power_state": system.get("PowerState"),
            "bios_version": system.get("BiosVersion"),
            "model": system.get("Model"),
            "serial": system.get("SerialNumber"),
            "cpu_model": (proc.get("Model") or processor.get("Model") or "").strip() or None,
            "cpu_count": proc.get("Count"),
            "cpu_cores": cpu_cores,
            "cpu_threads": cpu_threads,
            "ram_gib": mem.get("TotalSystemMemoryGiB"),
            "ram_health": _health(mem.get("Status")),
            "ilo_firmware": manager.get("FirmwareVersion"),
            "fw_integrity": integrity.get("LastScanResult"),
            "fw_last_scan": integrity.get("LastScanTime"),
        }

        temps: dict = {}
        for t in thermal.get("Temperatures") or []:
            if (t.get("Status") or {}).get("State") == "Enabled":
                name = t.get("Name")
                reading = t.get("ReadingCelsius")
                if name is not None and reading is not None:
                    temps[name] = reading
        data["temperatures"] = temps

        fans: dict = {}
        for f in thermal.get("Fans") or []:
            name = f.get("Name")
            reading = f.get("Reading")
            if name is not None and reading is not None:
                fans[name] = reading
        data["fans"] = fans

        if events:
            members = events.get("Members") or []
            data["critical_events"] = sum(1 for m in members if m.get("Severity") == "Critical")
        else:
            data["critical_events"] = None

        return data
