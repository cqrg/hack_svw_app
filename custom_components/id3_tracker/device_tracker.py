"""VW ID.3 (上汽大众) device_tracker / sensor / button platform."""
from __future__ import annotations

import logging
import threading
import time
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DeviceTrackerEntity,
    PLATFORM_SCHEMA,
    SourceType,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from .client import ID3Client, ID3Error

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("user_id"): cv.string,
        vol.Required("vin"): cv.string,
        vol.Required("auth_jwt"): cv.string,
        vol.Required("cop_token"): cv.string,
        vol.Required("device_id", default="vwa0a1b298a1598603"): cv.string,
        vol.Required("did", default=""): cv.string,
        vol.Optional(CONF_NAME, default="VW ID.3"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up ID.3 tracker platform."""
    client = ID3Client(
        user_id=config["user_id"],
        vin=config["vin"],
        auth_jwt=config["auth_jwt"],
        cop_token=config["cop_token"],
        device_id=config["device_id"],
        did=config.get("did", ""),
    )
    # 账号密码模式：尝试自动登录（pwdlogin；/app/token 受限时降级提示）
    if config.get("username") and config.get("password") and not config.get("auth_jwt"):
        login = client.login_with_password(config["username"], config["password"], config.get("did", ""))
        if login.get("ok"):
            _LOGGER.info("ID3 账号密码自动登录成功")
        else:
            _LOGGER.warning("ID3 账号密码登录受限：%s（请改用 token 模式，在 App 登录一次后填 auth_jwt）", login.get("error"))
            return False
    coordinator = ID3Coordinator(client, scan_seconds=int(SCAN_INTERVAL.total_seconds()))
    try:
        coordinator.refresh()
    except ID3Error:
        _LOGGER.exception("ID3 首次拉取车况失败，请检查 token 与网络（token 2 小时过期）")
        return False

    name = config.get(CONF_NAME, "VW ID.3")
    add_entities(
        [
            ID3LocationTracker(coordinator, name),
            ID3ChargeSensor(coordinator, name),
            ID3ClimateSensor(coordinator, name),
            ID3DoorsSensor(coordinator, name),
            ID3ACStartButton(coordinator, name),
            ID3ACStopButton(coordinator, name),
        ],
        True,
    )


class ID3Coordinator:
    """Shared poller caching full vehicle state."""

    def __init__(self, client: ID3Client, scan_seconds: int) -> None:
        self.client = client
        self.scan_seconds = scan_seconds
        self._lock = threading.Lock()
        self._last_ok = 0.0
        self.data: dict = {}

    def refresh(self) -> dict:
        with self._lock:
            if self.data and time.monotonic() - self._last_ok < self.scan_seconds:
                return self.data
            self.data = self.client.refresh_all()
            self._last_ok = time.monotonic()
            return self.data


def _f(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class ID3LocationTracker(DeviceTrackerEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ID3Coordinator, name: str) -> None:
        self._coordinator = coordinator
        self._attr_name = name
        self._attr_unique_id = f"id3_{name}_location"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self):
        loc = self._coordinator.data.get("location", {})
        return _f(loc.get("locationLat")) if loc.get("valid") else None

    @property
    def longitude(self):
        loc = self._coordinator.data.get("location", {})
        return _f(loc.get("locationLng")) if loc.get("valid") else None

    @property
    def extra_state_attributes(self):
        loc = self._coordinator.data.get("location", {})
        return {"timestamp": loc.get("timeStamp"), "valid": loc.get("valid")}

    def update(self) -> None:
        self._coordinator.refresh()


class ID3ChargeSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ID3Coordinator, name: str) -> None:
        self._coordinator = coordinator
        self._attr_name = f"{name} 电量"
        self._attr_unique_id = f"id3_{name}_soc"
        self._attr_unit_of_measurement = "%"

    @property
    def native_value(self):
        batt = self._coordinator.data.get("charging", {}).get("batteryStatus", {})
        return _f(batt.get("currentSocPct"))

    @property
    def extra_state_attributes(self):
        chg = self._coordinator.data.get("charging", {})
        batt = chg.get("batteryStatus", {})
        cst = chg.get("chargingStatus", {})
        return {
            "cruising_range_km": batt.get("cruisingRangeElectricKm"),
            "charging_state": cst.get("chargingState"),
            "charge_power_kw": cst.get("chargePowerKW"),
            "plug_connected": chg.get("plugStatus", {}).get("plugConnectionState"),
            "captured_at": batt.get("carCapturedTimestamp"),
        }

    def update(self) -> None:
        self._coordinator.refresh()


class ID3ClimateSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ID3Coordinator, name: str) -> None:
        self._coordinator = coordinator
        self._attr_name = f"{name} 空调"
        self._attr_unique_id = f"id3_{name}_climate"

    @property
    def native_value(self):
        cs = self._coordinator.data.get("climatisation", {}).get("climatisationStatus", {})
        return cs.get("climatisationState")

    @property
    def extra_state_attributes(self):
        cs = self._coordinator.data.get("climatisation", {}).get("climatisationStatus", {})
        wh = self._coordinator.data.get("climatisation", {}).get("windowHeatingStatus", {})
        return {
            "remaining_min": cs.get("remainingClimatisationTimeMin"),
            "captured_at": cs.get("carCapturedTimestamp"),
            "window_heating": wh.get("windowHeatingStatusList"),
        }

    def update(self) -> None:
        self._coordinator.refresh()


class ID3DoorsSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ID3Coordinator, name: str) -> None:
        self._coordinator = coordinator
        self._attr_name = f"{name} 车门"
        self._attr_unique_id = f"id3_{name}_doors"

    @property
    def native_value(self):
        acc = self._coordinator.data.get("access_lights", {}).get("access", {})
        return acc.get("overallStatus", "unknown")

    @property
    def extra_state_attributes(self):
        acc = self._coordinator.data.get("access_lights", {}).get("access", {})
        doors = {d.get("name"): d.get("status") for d in acc.get("doors", [])}
        windows = {w.get("name"): w.get("status") for w in acc.get("windows", [])}
        lights = self._coordinator.data.get("access_lights", {}).get("lights", [])
        return {
            "doors": doors,
            "windows": windows,
            "lights": {l_.get("name"): l_.get("status") for l_ in lights},
            "captured_at": acc.get("carCapturedTimestamp"),
        }

    def update(self) -> None:
        self._coordinator.refresh()


class _ID3ACButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ID3Coordinator, name: str, action: str) -> None:
        self._coordinator = coordinator
        self._attr_name = f"{name} 空调{'开' if action == 'start' else '关'}"
        self._attr_unique_id = f"id3_{name}_ac_{action}"
        self._action = action

    async def async_press(self) -> None:
        def do():
            if self._action == "start":
                return self._coordinator.client.climatisation_start()
            return self._coordinator.client.climatisation_stop()

        try:
            await self.hass.async_add_executor_job(do)
            _LOGGER.info("ID3 AC %s command sent", self._action)
        except ID3Error:
            _LOGGER.exception("ID3 AC %s failed", self._action)


class ID3ACStartButton(_ID3ACButton):
    def __init__(self, coordinator: ID3Coordinator, name: str) -> None:
        super().__init__(coordinator, name, "start")


class ID3ACStopButton(_ID3ACButton):
    def __init__(self, coordinator: ID3Coordinator, name: str) -> None:
        super().__init__(coordinator, name, "stop")




