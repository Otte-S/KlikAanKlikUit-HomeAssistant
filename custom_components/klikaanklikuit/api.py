from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import os
import re
import socket
import struct
from dataclasses import dataclass
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BASE_URL = "https://trustsmartcloud2.com/ics2000_api"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)
DISCOVERY_PACKET = bytes.fromhex(
    "010003ffffffffffffca000000010400044795000401040004000400040000000000000000020000003000"
)


class IcsError(Exception):
    pass


class IcsAuthError(IcsError):
    pass


def normalize_mac(value: str) -> str:
    normalized = re.sub(r"[:-]", "", value.strip()).lower()
    if not re.fullmatch(r"[0-9a-f]{12}", normalized):
        raise ValueError("Invalid MAC address")
    return normalized


def normalize_ip(value: str) -> str:
    return str(ipaddress.IPv4Address(value.strip())) if value.strip() else ""


def decrypt_json(value: str, key: bytes) -> dict[str, Any]:
    raw = base64.b64decode(value, validate=True)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(raw[:16])).decryptor()
    padded = decryptor.update(raw[16:]) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    decoded = json.loads((unpadder.update(padded) + unpadder.finalize()).decode())
    if not isinstance(decoded, dict):
        raise ValueError("Expected an object")
    return decoded


def build_command(mac: str, key: bytes, entity: int, function: int, value: int) -> bytes:
    payload = json.dumps(
        {"module": {"id": entity, "function": function, "value": value}},
        separators=(",", ":"),
    ).encode()
    padder = padding.PKCS7(128).padder()
    padded = padder.update(payload) + padder.finalize()
    iv = os.urandom(16)
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encrypted = iv + encryptor.update(padded) + encryptor.finalize()
    header = bytearray(43)
    header[0], header[2] = 1, 128
    header[3:9] = bytes.fromhex(normalize_mac(mac))
    struct.pack_into("<I", header, 9, 653213)
    struct.pack_into("<I", header, 29, entity)
    struct.pack_into("<H", header, 41, len(encrypted))
    return bytes(header) + encrypted


@dataclass(frozen=True)
class IcsDevice:
    id: int
    name: str
    device_type: int


class IcsClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        mac: str,
        email: str,
        password: str,
        local_ip: str = "",
    ) -> None:
        self.session = session
        self.mac = normalize_mac(mac)
        self.email = email
        self._password = password
        self.local_ip = normalize_ip(local_ip)
        self._key: bytes | None = None
        self._home_id: int | str | None = None
        self.devices: list[IcsDevice] = []
        self._command_lock = asyncio.Lock()

    async def _request(self, endpoint: str, *, decode_json: bool = True, **params: Any) -> Any:
        params.update(email=self.email, mac=self.mac, password_hash=self._password)
        try:
            async with self.session.post(
                f"{BASE_URL}/{endpoint}",
                data=params,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    raise IcsAuthError("Account credentials rejected")
                if response.status != 200:
                    raise IcsError(f"Cloud returned HTTP {response.status}")
                if not decode_json:
                    await response.read()
                    return None
                result = await response.json(content_type=None)
        except IcsError:
            raise
        except aiohttp.ClientError, TimeoutError, ValueError:
            raise IcsError("Cloud request failed or returned invalid data") from None
        if isinstance(result, dict) and result.get("error"):
            raise IcsError("Cloud returned an error response")
        return result

    async def async_login(self) -> None:
        result = await self._request(
            "account.php",
            action="login",
            device_unique_id="android",
            platform="Android",
        )
        homes = result.get("homes") if isinstance(result, dict) else None
        if not isinstance(homes, list) or not homes:
            raise IcsAuthError("No hub returned for these credentials")
        selected = None
        for home in homes:
            if not isinstance(home, dict):
                continue
            home_mac = home.get("mac") or home.get("mac_address")
            if home_mac and normalize_mac(str(home_mac)) == self.mac:
                selected = home
                break
        if selected is None and len(homes) == 1:
            selected = homes[0]
            home_mac = selected.get("mac") or selected.get("mac_address")
            if home_mac and normalize_mac(str(home_mac)) != self.mac:
                raise IcsAuthError("The requested hub does not belong to this account")
        if selected is None:
            raise IcsError("Could not identify the requested hub in the account")
        try:
            key = bytes.fromhex(selected["aes_key"])
            if len(key) not in (16, 24, 32):
                raise ValueError
            self._home_id = selected["home_id"]
        except (KeyError, TypeError, ValueError) as err:
            raise IcsError("Cloud returned an invalid hub key") from err
        self._key = key

    async def async_get_devices(self) -> list[IcsDevice]:
        result = await self._request("gateway.php", action="sync", home_id=self._home_id)
        if not isinstance(result, list) or self._key is None:
            raise IcsError("Cloud returned an invalid device inventory")
        devices: list[IcsDevice] = []
        try:
            for record in result:
                data = decrypt_json(record["data"], self._key)
                module = data.get("module", {})
                if "info" not in module:
                    continue
                devices.append(
                    IcsDevice(
                        int(module["id"]),
                        str(module["name"]),
                        int(module["device"]),
                    )
                )
        except (KeyError, TypeError, ValueError) as err:
            raise IcsError("Could not decode the device inventory") from err
        self.devices = devices
        return devices

    async def async_get_statuses(self) -> dict[int, list]:
        ids = [device.id for device in self.devices]
        if not ids:
            return {}
        result = await self._request(
            "entity.php",
            action="get-multiple",
            home_id=self._home_id,
            entity_id=json.dumps(ids, separators=(",", ":")),
        )
        if not isinstance(result, list) or not result or self._key is None:
            raise IcsError("Cloud returned an invalid status response")
        statuses: dict[int, list] = {}
        for record in result:
            if not isinstance(record, dict):
                raise IcsError("Cloud returned an invalid status record")
            if record.get("status") is None:
                continue
            try:
                module = decrypt_json(record["status"], self._key)["module"]
                entity_id = int(module.get("id", record.get("entity_id", record.get("id"))))
                functions = module["functions"]
                if not isinstance(functions, list):
                    raise ValueError
                if entity_id in ids:
                    statuses[entity_id] = functions
            except (KeyError, TypeError, ValueError) as err:
                raise IcsError("Could not decode a device status") from err
        return statuses

    async def async_discover(self) -> None:
        if self.local_ip:
            return
        loop = asyncio.get_running_loop()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.setblocking(False)
                await loop.sock_sendto(sock, DISCOVERY_PACKET, ("255.255.255.255", 2012))
                async with asyncio.timeout(2):
                    while True:
                        packet, address = await loop.sock_recvfrom(sock, 2048)
                        if len(packet) >= 9 and packet[3:9].hex() == self.mac:
                            self.local_ip = address[0]
                            return
        except OSError, TimeoutError:
            return

    async def async_send(
        self,
        entity: int,
        function: int,
        value: int,
        tries: int = 1,
        delay: int = 3,
    ) -> None:
        if self._key is None:
            raise IcsError("Hub is not authenticated")
        command = build_command(self.mac, self._key, entity, function, value)
        async with self._command_lock:
            for attempt in range(max(1, tries)):
                sent_locally = False
                if self.local_ip:
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                            sock.setblocking(False)
                            await asyncio.get_running_loop().sock_sendto(
                                sock,
                                command,
                                (self.local_ip, 2012),
                            )
                        sent_locally = True
                    except OSError:
                        pass
                if not sent_locally:
                    await self._request(
                        "command.php",
                        decode_json=False,
                        action="add",
                        device_unique_id="android",
                        command=command.hex(),
                    )
                if attempt < max(1, tries) - 1:
                    await asyncio.sleep(delay)
