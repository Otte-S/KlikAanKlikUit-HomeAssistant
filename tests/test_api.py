import asyncio
import base64
import json
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from custom_components.klikaanklikuit.api import (
    BASE_URL,
    IcsAuthError,
    IcsClient,
    IcsDevice,
    IcsError,
    build_command,
    decrypt_json,
    normalize_mac,
)

KEY = bytes.fromhex("00112233445566778899aabbccddeeff")
MAC = "001122334455"


def encrypted(data):
    raw = json.dumps(data, ensure_ascii=False).encode()
    padder = padding.PKCS7(128).padder()
    payload = padder.update(raw) + padder.finalize()
    encryptor = Cipher(algorithms.AES(KEY), modes.CBC(bytes(16))).encryptor()
    return base64.b64encode(bytes(16) + encryptor.update(payload) + encryptor.finalize()).decode()


async def test_login_uses_form_credentials_and_selects_requested_hub(aioclient_mock):
    aioclient_mock.post(
        BASE_URL + "/account.php",
        json={
            "homes": [
                {"mac": "aabbccddeeff", "aes_key": "11" * 16, "home_id": 1},
                {"mac": "00:11:22:33:44:55", "aes_key": KEY.hex(), "home_id": 2},
            ]
        },
    )
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        client = IcsClient(session, MAC, "private@example.com", "secret")
        await client.async_login()
    request = aioclient_mock.mock_calls[0]
    assert "secret" not in str(request[1])
    assert request[2]["password_hash"] == "secret"
    assert client._home_id == 2
    assert client._key == KEY


@pytest.mark.parametrize(
    "status,body,error",
    [
        (401, {}, IcsAuthError),
        (200, {"homes": []}, IcsAuthError),
        (503, {}, IcsError),
        (200, {"homes": [{"home_id": 1}]}, IcsError),
    ],
)
async def test_login_failures(aioclient_mock, status, body, error):
    aioclient_mock.post(BASE_URL + "/account.php", status=status, json=body)
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(error):
            await IcsClient(session, MAC, "private@example.com", "secret").async_login()


async def test_request_timeout_is_bounded_and_does_not_expose_credentials(aioclient_mock):
    aioclient_mock.post(BASE_URL + "/account.php", exc=TimeoutError("secret in underlying error"))
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(IcsError) as caught:
            await IcsClient(session, MAC, "private@example.com", "secret").async_login()
    assert "secret" not in str(caught.value)
    assert caught.value.__suppress_context__


async def test_inventory_keeps_numeric_types_and_unicode_names(aioclient_mock):
    aioclient_mock.post(
        BASE_URL + "/gateway.php",
        json=[
            {"data": encrypted({"module": {"id": 42, "name": "Büro 🌡", "device": 46, "info": []}})},
            {
                "data": encrypted(
                    {"module": {"id": 43, "name": "Unknown", "device": 999, "info": []}}
                )
            },
        ],
    )
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        client = IcsClient(session, MAC, "e", "p")
        client._key = KEY
        devices = await client.async_get_devices()
    assert devices == [IcsDevice(42, "Büro 🌡", 46), IcsDevice(43, "Unknown", 999)]


async def test_statuses_are_batched_and_match_ids_independent_of_response_order(aioclient_mock):
    aioclient_mock.post(
        BASE_URL + "/entity.php",
        json=[
            {"id": 2, "status": encrypted({"module": {"functions": [0, 8]}})},
            {"id": 1, "status": encrypted({"module": {"id": 1, "functions": [1]}})},
            {"id": 3, "status": None},
        ],
    )
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        client = IcsClient(session, MAC, "e", "p")
        client._key = KEY
        client.devices = [IcsDevice(i, str(i), 1) for i in (1, 2, 3)]
        assert await client.async_get_statuses() == {1: [1], 2: [0, 8]}
    assert len(aioclient_mock.mock_calls) == 1
    assert json.loads(aioclient_mock.mock_calls[0][2]["entity_id"]) == [1, 2, 3]


@pytest.mark.parametrize("body", [[], {}, [{"id": 1, "status": "broken"}]])
async def test_invalid_status_response_does_not_look_like_success(aioclient_mock, body):
    aioclient_mock.post(BASE_URL + "/entity.php", json=body)
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        client = IcsClient(session, MAC, "e", "p")
        client._key = KEY
        client.devices = [IcsDevice(1, "Desk", 1)]
        with pytest.raises(IcsError):
            await client.async_get_statuses()


def test_command_has_compatible_header_and_encrypted_payload():
    packet = build_command(MAC, KEY, 12345, 4, 127)
    assert len(packet[:43]) == 43
    assert packet[0] == 1 and packet[2] == 128
    assert packet[3:9] == bytes.fromhex(MAC)
    assert struct.unpack_from("<I", packet, 9)[0] == 653213
    assert struct.unpack_from("<I", packet, 29)[0] == 12345
    assert struct.unpack_from("<H", packet, 41)[0] == len(packet[43:])
    assert decrypt_json(base64.b64encode(packet[43:]).decode(), KEY) == {
        "module": {"id": 12345, "function": 4, "value": 127}
    }


async def test_local_send_error_falls_back_to_cloud(aioclient_mock):
    aioclient_mock.post(BASE_URL + "/command.php", json=True)
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        client = IcsClient(session, MAC, "e", "p", "10.0.0.2")
        client._key = KEY
        loop = asyncio.get_running_loop()
        with (
            patch("custom_components.klikaanklikuit.api.socket.socket"),
            patch.object(loop, "sock_sendto", AsyncMock(side_effect=OSError)),
        ):
            await client.async_send(1, 0, 1)
    assert len(aioclient_mock.mock_calls) == 1
    assert "command" in aioclient_mock.mock_calls[0][2]


async def test_discovery_ignores_a_different_hub():
    client = IcsClient(MagicMock(), MAC, "e", "p")
    wrong = bytes(3) + bytes.fromhex("aabbccddeeff")
    correct = bytes(3) + bytes.fromhex(MAC)
    loop = asyncio.get_running_loop()
    with (
        patch("custom_components.klikaanklikuit.api.socket.socket"),
        patch.object(loop, "sock_sendto", AsyncMock()),
        patch.object(
            loop,
            "sock_recvfrom",
            AsyncMock(side_effect=[(wrong, ("10.0.0.3", 2012)), (correct, ("10.0.0.2", 2012))]),
        ),
    ):
        await client.async_discover()
    assert client.local_ip == "10.0.0.2"


@pytest.mark.parametrize("value", ["00:11:22:33:44:55", "00-11-22-33-44-55", "001122334455"])
def test_mac_formats_share_an_identity(value):
    assert normalize_mac(value) == MAC


async def test_successful_cloud_command_accepts_an_empty_response(aioclient_mock):
    aioclient_mock.post(BASE_URL + "/command.php", text="")
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        client = IcsClient(session, MAC, "e", "p")
        client._key = KEY
        await client.async_send(1, 0, 1)
    assert len(aioclient_mock.mock_calls) == 1


async def test_login_does_not_select_another_accounts_hub(aioclient_mock):
    aioclient_mock.post(
        BASE_URL + "/account.php",
        json={
            "homes": [
                {"mac": "aabbccddeeff", "aes_key": KEY.hex(), "home_id": 1},
            ]
        },
    )
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(IcsAuthError):
            await IcsClient(session, MAC, "e", "p").async_login()


async def test_command_repetitions_are_serialized():
    client = IcsClient(MagicMock(), MAC, "e", "p")
    client._key = KEY
    active, maximum = 0, 0
    commands = []

    async def request(endpoint, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        commands.append(
            decrypt_json(base64.b64encode(bytes.fromhex(kwargs["command"])[43:]).decode(), KEY)[
                "module"
            ]["id"]
        )
        await asyncio.sleep(0)
        active -= 1

    client._request = request
    await asyncio.gather(client.async_send(1, 0, 1, tries=2, delay=0), client.async_send(2, 0, 0))
    assert maximum == 1
    assert commands == [1, 1, 2]
