from unittest.mock import AsyncMock, patch

import pytest

from custom_components.klikaanklikuit.api import IcsDevice


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_client():
    with patch("custom_components.klikaanklikuit.IcsClient", autospec=True) as factory:
        client = factory.return_value
        client.mac = "001122334455"
        client.local_ip = "10.0.0.2"
        client.devices = [
            IcsDevice(1, "Desk", 1),
            IcsDevice(2, "Dimmer", 34),
            IcsDevice(3, "Climate", 46),
            IcsDevice(4, "Gong", 13),
            IcsDevice(5, "Doorbell", 21),
            IcsDevice(6, "Contact", 28),
            IcsDevice(7, "Unknown", 999),
        ]
        client.async_login = AsyncMock()
        client.async_get_devices = AsyncMock(return_value=client.devices)
        client.async_discover = AsyncMock()
        climate = [0] * 12
        climate[4], climate[11] = 2150, 4500
        client.async_get_statuses = AsyncMock(
            return_value={
                1: [1],
                2: [0, 0, 0, 1, 127],
                3: climate,
                4: [1],
                5: [0],
                6: [1],
            }
        )
        client.async_send = AsyncMock()
        yield client
