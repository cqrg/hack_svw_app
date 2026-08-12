"""device_tracker - TODO 脱壳后实现：轮询车辆状态并更新 device_tracker 实体。"""
from __future__ import annotations

import logging

from homeassistant.components.device_tracker.config_entry import BaseTrackerEntity
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    # TODO 脱壳后：实例化 SvwClient，创建协调器，注册车辆实体
    async_add_entities([SvwVehicleTracker(entry)], update_before_add=True)


class SvwVehicleTracker(BaseTrackerEntity):
    _attr_has_entity_name = True

    def __init__(self, entry) -> None:
        self._entry = entry
        self._attr_unique_id = f"svw_{entry.entry_id}"
        self._attr_name = "ID.3"

    @property
    def source_type(self):
        from homeassistant.components.device_tracker import SourceType
        return SourceType.GPS

    @property
    def latitude(self):
        # TODO 脱壳后：从车辆状态接口获取
        return None

    @property
    def longitude(self):
        return None
