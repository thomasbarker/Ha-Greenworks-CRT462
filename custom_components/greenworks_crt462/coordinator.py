"""DataUpdateCoordinator and API client for Greenworks CRT4262."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CORP_ID,
    DOMAIN,
    GUC_BASE,
    GUC_CLIENT_ID,
    GUC_CLIENT_SECRET,
    GUC_SCOPE,
    IDDS_BASE,
    MOWER_MODEL,
    XAPI_BASE,
)

_LOGGER = logging.getLogger(__name__)

# Datapoints polled from v_device endpoint
# DP 0 = total battery %, DPs 142/148/154/160/166/172 = individual slot % (CRT category)
_DATAPOINTS = "0,1,2,4,6,7,8,9,10,11,16,18,19,24,28,92,94,95,97,142,148,154,160,166,172"


class GreenworksCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages authentication and periodic data refresh for the mower."""

    def __init__(
        self,
        hass: HomeAssistant,
        email: str,
        password: str,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.email = email
        self.password = password

        # xapi auth state
        self._xapi_token: str | None = None
        self._xapi_refresh: str | None = None
        self._xapi_expiry: datetime | None = None
        self._user_id: str | None = None

        # GUC Bearer token state (used for IDDS requests)
        self._guc_token: str | None = None
        self._guc_expiry: datetime | None = None

        # Cached device identifiers (set on first successful fetch)
        self._device_id: str | None = None
        self._product_id: str | None = None
        self._mac: str | None = None

        # Set to True when login fails due to server rejecting credentials (4xx)
        # vs a transient network error. Used by __init__.py to raise the right exception.
        self.auth_failed: bool = False

        # Last successfully fetched data — returned on update failure to keep entities available
        self._last_good_data: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def async_login(self) -> bool:
        """Authenticate with both xapi and GUC OAuth. Returns True on success."""
        self.auth_failed = False
        session = async_get_clientsession(self.hass)

        # xapi login
        try:
            async with session.post(
                f"{XAPI_BASE}/v2/user_auth",
                json={"corp_id": CORP_ID, "email": self.email, "password": self.password},
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("xapi login failed: HTTP %s", resp.status)
                    self.auth_failed = True  # server reachable but rejected
                    return False
                try:
                    data = await resp.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError) as err:
                    _LOGGER.error("xapi login: invalid JSON response: %s", err)
                    return False

            self._xapi_token = data.get("access_token")
            self._xapi_refresh = data.get("refresh_token")
            try:
                expire_in = int(data.get("expire_in") or 3600)
            except (ValueError, TypeError):
                expire_in = 3600
            self._xapi_expiry = datetime.now() + timedelta(seconds=expire_in)
            self._user_id = str(data.get("user_id", ""))
        except aiohttp.ClientError as err:
            _LOGGER.error("xapi login error: %s", err)
            return False

        # GUC login (needed for IDDS mowing statistics)
        await self._guc_login(session)

        return bool(self._xapi_token)

    async def _guc_login(self, session: aiohttp.ClientSession) -> None:
        """Obtain a GUC Bearer token for IDDS requests."""
        try:
            async with session.post(
                f"{GUC_BASE}/connect/token",
                data={
                    "scope": GUC_SCOPE,
                    "grant_type": "password",
                    "client_id": GUC_CLIENT_ID,
                    "client_secret": GUC_CLIENT_SECRET,
                    "username": self.email,
                    "password": self.password,
                    "HasLocationInfo": "false",
                    "Latitude": "0",
                    "Longitude": "0",
                    "LoginTime": "0",
                },
            ) as resp:
                if resp.status == 200:
                    try:
                        gdata = await resp.json(content_type=None)
                        self._guc_token = gdata.get("access_token")
                        try:
                            expires_in = int(gdata.get("expires_in") or 3600)
                        except (ValueError, TypeError):
                            expires_in = 3600
                        self._guc_expiry = datetime.now() + timedelta(seconds=expires_in)
                    except (ValueError, aiohttp.ContentTypeError) as err:
                        _LOGGER.warning("GUC login: invalid JSON response: %s", err)
                else:
                    _LOGGER.warning(
                        "GUC login failed (HTTP %s); mowing stats will be unavailable",
                        resp.status,
                    )
        except aiohttp.ClientError as err:
            _LOGGER.warning("GUC login error: %s; mowing stats will be unavailable", err)

    async def _ensure_tokens(self) -> None:
        """Re-authenticate if tokens are expired or close to expiry."""
        now = datetime.now()
        margin = timedelta(minutes=5)

        xapi_expired = (
            self._xapi_token is None
            or self._xapi_expiry is None
            or self._xapi_expiry - now < margin
        )
        if xapi_expired:
            if self._xapi_refresh and self._xapi_token:
                refreshed = await self._xapi_refresh_token()
                if not refreshed:
                    await self.async_login()
                    return  # async_login already handles GUC
            else:
                await self.async_login()
                return  # async_login already handles GUC

        # Always check GUC separately (may expire independently of xapi)
        guc_expired = (
            self._guc_token is None
            or self._guc_expiry is None
            or self._guc_expiry - now < margin
        )
        if guc_expired:
            await self._guc_login(async_get_clientsession(self.hass))

    async def _xapi_refresh_token(self) -> bool:
        """Refresh the xapi access token. Returns True on success."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{XAPI_BASE}/v2/user/token/refresh",
                json={"refresh_token": self._xapi_refresh},
                headers={"Access-Token": self._xapi_token or ""},
            ) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError):
                        return False
                    self._xapi_token = data.get("access_token")
                    self._xapi_refresh = data.get("refresh_token")
                    try:
                        expire_in = int(data.get("expire_in") or 3600)
                    except (ValueError, TypeError):
                        expire_in = 3600
                    self._xapi_expiry = datetime.now() + timedelta(seconds=expire_in)
                    return True
        except aiohttp.ClientError:
            pass
        return False

    # ------------------------------------------------------------------
    # Header builders
    # ------------------------------------------------------------------

    def _xapi_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Access-Token": self._xapi_token or "",
            "Xlink-Access-Token": self._xapi_token or "",
            "Xlink-User-Id": self._user_id or "",
        }

    def _idds_headers(self) -> dict[str, str]:
        headers = self._xapi_headers()
        if self._guc_token:
            headers["Authorization"] = f"Bearer {self._guc_token}"
        return headers

    # ------------------------------------------------------------------
    # Authenticated HTTP helper
    # ------------------------------------------------------------------

    async def _authed_get(
        self,
        url: str,
        headers_fn: Any,  # callable returning dict[str, str]
        *,
        label: str = "",
    ) -> dict | None:
        """GET a URL with automatic re-login on auth failure.

        Returns the parsed JSON dict on success, or None on non-auth errors.
        Raises UpdateFailed if credentials are rejected after re-login.

        xapi signals an expired token with HTTP 403 + body {"code": 4031022, ...}
        as well as the standard HTTP 401, so we check both.
        """
        session = async_get_clientsession(self.hass)

        for attempt in range(2):
            try:
                async with session.get(url, headers=headers_fn()) as resp:
                    if resp.status == 200:
                        return await resp.json()

                    # Detect auth failure: 401 or 403 with xapi expired-token code
                    auth_failed = resp.status == 401
                    if resp.status == 403:
                        try:
                            body = await resp.json()
                            auth_failed = body.get("code") == 4031022
                        except Exception:
                            pass

                    if auth_failed:
                        if attempt == 0:
                            _LOGGER.debug(
                                "%s: auth error (HTTP %s), re-logging in",
                                label or url,
                                resp.status,
                            )
                            if not await self.async_login():
                                raise UpdateFailed(
                                    f"{label or url}: re-login failed — check credentials"
                                )
                            continue  # retry with fresh tokens
                        raise UpdateFailed(
                            f"{label or url}: still unauthorised after re-login"
                        )

                    _LOGGER.debug("%s: HTTP %s", label or url, resp.status)
                    return None  # non-auth error — caller handles gracefully

            except UpdateFailed:
                raise
            except aiohttp.ClientError as err:
                _LOGGER.debug("%s fetch error: %s", label or url, err)
                return None

        return None

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    async def _fetch_devices(self) -> list[dict]:
        """Fetch subscribed devices from xapi."""
        url = f"{XAPI_BASE}/v2/user/{self._user_id}/subscribe/devices?version=0"
        data = await self._authed_get(url, self._xapi_headers, label="subscribe/devices")
        if data is None:
            raise UpdateFailed("subscribe/devices returned no data")
        return data.get("list", [])

    async def _fetch_vdevice(self, product_id: str, device_id: str) -> dict:
        """Fetch v_device status and datapoints."""
        url = (
            f"{XAPI_BASE}/v2/product/{product_id}/v_device/{device_id}"
            f"?datapoints={_DATAPOINTS}"
        )
        return await self._authed_get(url, self._xapi_headers, label="v_device") or {}

    async def _fetch_idds(
        self, product_id: str, mac: str, device_id: str
    ) -> dict[str, Any]:
        """Fetch mowing statistics from the IDDS service."""
        if not self._guc_token:
            return {}

        result: dict[str, Any] = {}
        calls = {
            "total": (
                f"{IDDS_BASE}/api/v1/workingSessionStatistics"
                f"/totalWorkingSessionInfo/1/1/{MOWER_MODEL}/{device_id}"
            ),
            "current_duration": (
                f"{IDDS_BASE}/api/CurrentCutting/CurrentCuttingDuration"
                f"/{product_id}/{MOWER_MODEL}/{device_id}"
            ),
            "current_area": (
                f"{IDDS_BASE}/api/CurrentCutting/CurrentCuttingArea"
                f"/{product_id}/{MOWER_MODEL}/{device_id}"
            ),
            "sessions": f"{IDDS_BASE}/api/v2/report/sessions/{mac}/10",
            # Remaining cutting capacity on current charge
            "remaining_cutting": f"{IDDS_BASE}/api/v2/remainingCutting/{device_id}",
            # Per-slot battery health: totalPower, per-slot power/state/temperature
            "battery_check": (
                f"{IDDS_BASE}/api/Battery/BatterySlotCheck"
                f"/{product_id}/{MOWER_MODEL}/{device_id}"
            ),
        }

        for key, url in calls.items():
            try:
                data = await self._authed_get(
                    url, self._idds_headers, label=f"IDDS/{key}"
                )
            except UpdateFailed as err:
                _LOGGER.warning("IDDS %s unavailable: %s", key, err)
                continue
            if data is not None:
                result[key] = data.get("data", {})

        return result

    # ------------------------------------------------------------------
    # Data assembly
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data. Called by DataUpdateCoordinator on each poll."""
        try:
            await self._ensure_tokens()

            if not self._xapi_token:
                raise UpdateFailed("Not authenticated — check your credentials")

            try:
                devices = await self._fetch_devices()
            except UpdateFailed:
                raise
            except Exception as err:
                raise UpdateFailed(f"Device list fetch failed: {err}") from err

            if not devices:
                raise UpdateFailed("No devices found on this account")

            dev = devices[0]
            device_id = str(dev.get("id", ""))
            product_id = str(dev.get("product_id", ""))
            mac = str(dev.get("mac", ""))

            # Cache for use in property accessors
            self._device_id = device_id
            self._product_id = product_id
            self._mac = mac

            vdevice: dict = {}
            if device_id and product_id:
                vdevice = await self._fetch_vdevice(product_id, device_id)

            idds: dict = {}
            if device_id and product_id and mac:
                idds = await self._fetch_idds(product_id, mac, device_id)

            result = _build_state(dev, vdevice, idds)
            result["last_updated"] = datetime.now(timezone.utc)
            self._last_good_data = result
            return result

        except Exception as err:
            if self._last_good_data is not None:
                _LOGGER.warning(
                    "Greenworks data fetch failed (%s); returning last known values "
                    "(last updated: %s)",
                    err,
                    self._last_good_data.get("last_updated"),
                )
                return self._last_good_data
            if isinstance(err, UpdateFailed):
                raise
            raise UpdateFailed(f"Unexpected error: {err}") from err


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _dp_int(vdevice: dict, key: str) -> int | None:
    """Return a datapoint value as int, or None if absent/unparseable."""
    val = vdevice.get(key)
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert a value to float safely, returning default on failure."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Convert a value to int safely, returning default on failure."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _to_bool(val: Any) -> bool:
    """Normalise API boolean values — handles int, bool, and string forms."""
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes")
    return False


def _parse_dp94_gps(raw: str) -> tuple[float | None, float | None, str | None]:
    """Parse DP 94 GPS string: 'YYYYMMDDHHmmSS,lat,lon,YYYYMMDDHHmmSS'."""
    if not raw or raw == "0":
        return None, None, None
    parts = raw.split(",")
    if len(parts) < 3:
        return None, None, None
    try:
        lat = float(parts[1])
        lon = float(parts[2])
        ts_raw = parts[0]
        gps_ts: str | None = None
        if len(ts_raw) == 14:
            gps_ts = (
                f"{ts_raw[0:4]}-{ts_raw[4:6]}-{ts_raw[6:8]}"
                f"T{ts_raw[8:10]}:{ts_raw[10:12]}:{ts_raw[12:14]}"
            )
        return lat, lon, gps_ts
    except (ValueError, IndexError):
        return None, None, None


def _build_state(dev: dict, vdevice: dict, idds: dict) -> dict[str, Any]:
    """Combine raw API data into a flat state dictionary."""
    # GPS from datapoint 94
    lat, lon, gps_ts = _parse_dp94_gps(str(vdevice.get("94", "") or ""))

    # IDDS totals
    total = idds.get("total") or {}
    curr_dur = idds.get("current_duration") or {}
    curr_area = idds.get("current_area") or {}
    sessions = idds.get("sessions") or {}
    remaining = idds.get("remaining_cutting") or {}
    batt_check = idds.get("battery_check") or {}

    total_dur_ms = _safe_float(total.get("totalWorkingDuration"))
    total_area_m2 = _safe_float(total.get("totalWorkingArea"))
    curr_dur_ms = _safe_float(curr_dur.get("value"))
    curr_area_acre = _safe_float(curr_area.get("value"))
    curr_session_start_ts = curr_dur.get("startTimestamp")
    curr_session_end_ts = curr_dur.get("endTimestamp")

    # Remaining cutting — area likely in acres (same as CurrentCuttingArea endpoint)
    remaining_area_raw = _safe_float(remaining.get("cuttingArea"))
    remaining_unit = str(remaining.get("unit") or "").lower()
    remaining_area_m2 = round(
        remaining_area_raw * 4046.86 if "acre" in remaining_unit else remaining_area_raw,
        1,
    )
    remaining_time_min = _safe_float(remaining.get("cuttingTime"))

    # Battery slot check — per-slot health from IDDS
    battery_slot_details = [
        {
            "slot": d.get("batterySlotNumber"),
            "name": d.get("batteryName"),
            "power_pct": d.get("power"),
            "state": d.get("batteryState"),
            "temperature_c": d.get("batteryTemperature"),
            "in_slot": d.get("isInSlot"),
        }
        for d in (batt_check.get("details") or [])
    ]

    return {
        # Device identity
        "name": dev.get("name") or "Greenworks Mower",
        "sn": str(dev.get("sn", "")),
        "mac": str(dev.get("mac", "")),
        "product_id": str(dev.get("product_id", "")),
        "device_id": str(dev.get("id", "")),
        "active_date": str(dev.get("active_date") or ""),
        # Status
        "is_online": _to_bool(dev.get("is_online")),
        # is_active from the API means the device registration is active (not mowing).
        # Gate it on is_online — the mower can't be running if it's not connected.
        "is_active": _to_bool(dev.get("is_online")) and _to_bool(dev.get("is_active")),
        # Firmware
        "firmware_version": str(dev.get("firmware_version") or ""),
        "mcu_version": str(dev.get("mcu_version") or ""),
        # v_device timestamps and counters
        "last_login": vdevice.get("last_login"),
        "last_logout": vdevice.get("last_logout"),
        "online_count": _safe_int(vdevice.get("online_count")),
        "ip": str(vdevice.get("ip") or ""),
        # GPS
        "latitude": lat,
        "longitude": lon,
        "gps_timestamp": gps_ts,
        # IDDS statistics (durations in minutes, area in m²)
        "total_working_duration_min": round(total_dur_ms / 60_000, 1),
        "total_working_area_m2": round(total_area_m2, 1),
        "current_session_duration_min": round(curr_dur_ms / 60_000, 1),
        "current_session_area_m2": round(curr_area_acre * 4046.86, 1),
        "current_session_start_ts": curr_session_start_ts,
        "current_session_end_ts": curr_session_end_ts,
        "session_count": _safe_int(sessions.get("totalNumber")),
        "latest_sessions": (sessions.get("reportSessions") or [])[:5],
        # Remaining cutting capacity on current charge
        "remaining_cutting_area_m2": remaining_area_m2,
        "remaining_cutting_time_min": round(remaining_time_min, 1),
        "remaining_cutting_unit": str(remaining.get("unit") or ""),
        # Battery — DP 0 = total %, IDDS battery check for detailed slot info
        "battery_level": _dp_int(vdevice, "0"),
        "battery_total_power": _safe_float(batt_check.get("totalPower")) or None,
        "battery_slot_details": battery_slot_details,
        # Individual battery slot % (CRT category, DPs 142/148/154/160/166/172)
        "battery_slot_1": _dp_int(vdevice, "142"),
        "battery_slot_2": _dp_int(vdevice, "148"),
        "battery_slot_3": _dp_int(vdevice, "154"),
        "battery_slot_4": _dp_int(vdevice, "160"),
        "battery_slot_5": _dp_int(vdevice, "166"),
        "battery_slot_6": _dp_int(vdevice, "172"),
        # Motor datapoints (RPM — 0 when mower is off)
        "dp_motor_a_rpm": _dp_int(vdevice, "7"),
        "dp_motor_b_rpm": _dp_int(vdevice, "11"),
        "dp_blade_left_rpm": _dp_int(vdevice, "18"),
        "dp_blade_mid_rpm": _dp_int(vdevice, "24"),
        "dp_blade_right_rpm": _dp_int(vdevice, "28"),
        # Settings datapoints
        "dp_cut_height_mm": _dp_int(vdevice, "9"),
        # Diagnostic datapoints (meaning unconfirmed from source)
        "dp_92": _dp_int(vdevice, "92"),
    }
