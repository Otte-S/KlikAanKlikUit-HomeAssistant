from __future__ import annotations

from .api import IcsDevice

CATEGORY_LIGHT = "light"
CATEGORY_DIMMER = "dimmer"
CATEGORY_TEMP_HUMIDITY = "temp_humidity"
CATEGORY_GONG = "gong"
CATEGORY_INPUT = "input"

LIGHT_TYPES = {1, 3, 12, 33, 41}
DIMMER_TYPES = {2, 24, 34, 35, 36, 40}
TEMP_HUMIDITY_TYPES = {46}
GONG_TYPES = {13}
INPUT_TYPES = {21, 25, 26, 28}
ZIGBEE_TYPES = {33, 34, 35, 36, 40, 41}


def classify(device: IcsDevice) -> str | None:
    for category, types in (
        (CATEGORY_DIMMER, DIMMER_TYPES),
        (CATEGORY_TEMP_HUMIDITY, TEMP_HUMIDITY_TYPES),
        (CATEGORY_GONG, GONG_TYPES),
        (CATEGORY_INPUT, INPUT_TYPES),
        (CATEGORY_LIGHT, LIGHT_TYPES),
    ):
        if device.device_type in types:
            return category
    return None


def power_function(device: IcsDevice) -> int:
    return 3 if device.device_type in ZIGBEE_TYPES else 0


def dim_function(device: IcsDevice) -> int:
    return 4 if device.device_type in ZIGBEE_TYPES else 1


def max_brightness(device: IcsDevice) -> int:
    return 254 if device.device_type in ZIGBEE_TYPES else 15
