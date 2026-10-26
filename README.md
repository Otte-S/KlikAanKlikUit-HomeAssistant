# KlikAanKlikUit for Home Assistant

Control KlikAanKlikUit / Trust devices through an ICS-2000 hub. Setup and options are available in the Home Assistant interface.

Requires Home Assistant 2026.9.3 or newer, an ICS-2000 hub and a KlikAanKlikUit / Trust account. Authentication, device discovery and status updates require access to the Trust cloud. Commands can use the local network after authentication.

## Installation

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/Otte-S/KlikAanKlikUit-HomeAssistant` as an **Integration**.
3. Download **KlikAanKlikUit** and restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration > KlikAanKlikUit**.
5. Enter the hub MAC address and the credentials used in the KlikAanKlikUit / Trust app. You can also enter the hub IPv4 address.

The hub and its supported devices appear automatically. Devices added or removed in the Trust app are synchronized when you reload the integration.

## Supported devices

| Device | Home Assistant entity | Support |
| --- | --- | --- |
| Classic switches and lights | Light | On/off |
| Classic dimmers, types 2 and 24 | Light | On/off and 15 brightness steps |
| Zigbee switches, types 33 and 41 | Light | On/off |
| Zigbee dimmers and lights, types 34, 35, 36 and 40 | Light | On/off and brightness |
| Gong, type 13 | Button | Send a chime command |
| Temperature and humidity, type 46 | Two sensors | Temperature and relative humidity |
| Contact sensor, type 28 | Binary sensor | Last cloud opening state |
| Doorbell and wall transmitters, types 21, 25 and 26 | Binary sensor | Experimental last cloud state, disabled by default |

Color, color temperature, covers and unknown device types are not exposed as controls. Unknown types are listed in diagnostics so support can be added with the correct protocol.

### Doorbells and remote controls

A cloud state is not a button-press event. Short presses can occur between polls, and some transmitters never update the cloud. Repeated presses may also leave the same stored state. Do not use these experimental entities as a reliable doorbell event source. A shorter polling interval does not remove this limitation.

A classic 433 MHz remote that sends directly to a receiver can change the physical device without changing the state known to the hub or Home Assistant.

## Local and cloud operation

The integration searches for a hub response matching the configured MAC address. A manually configured IPv4 address takes precedence, which is useful across VLANs. Allow UDP port 2012 between Home Assistant and the hub for local commands.

If no local address is available, commands go through the cloud. A local socket error also falls back to the cloud. UDP has no delivery acknowledgement, so a successful send does not prove that the hub or RF receiver received it. An unreachable hub can silently drop UDP traffic; clear or correct the manual IP if needed.

Status always comes from the cloud, in one request for all devices per polling cycle. After a command, the light briefly shows the requested state while waiting for the cloud. During a cloud outage, local light and gong commands remain available after a successful initial setup. Light states are marked as assumed until cloud updates resume; sensors become unavailable.

## Options

Open the integration's **Configure** menu.

| Option | Default | Meaning |
| --- | --- | --- |
| Cloud status interval | 30 seconds | One request for all device statuses; minimum 5 seconds |
| Hub IPv4 address | Automatic | Leave empty to discover the hub on the local network |
| Transmissions per command | 1 | Repeat the same command up to 5 times for RF reception |
| Seconds between transmissions | 3 | Delay between repeated transmissions |

These repetitions are not delivery confirmation. Repeating a gong command can ring the gong more than once.

If your account credentials change, use the reauthentication flow shown by Home Assistant.

## Upgrading from 2.x

Version 3.0 changes the API client and device identification. Existing supported entities retain their entity IDs and custom names through migration. The new internal IDs include the hub MAC address so multiple hubs cannot claim the same device.

Type 28 is a contact sensor rather than a controllable light. Unknown types, including type 53, are no longer offered as generic lights. Old entities for these controls may remain unavailable in the entity registry; review any automations using them before removing them.

If HACS still lists `Otte-S/KlikAanKlikUit-HA`, replace that old repository with the URL in the installation instructions. Keep the configured KlikAanKlikUit integration in **Devices & services**. After downloading the new repository, restart Home Assistant and check that the integration loads before removing old unavailable entities.

## Troubleshooting

- **Configuration cannot load:** install the current repository URL, restart Home Assistant and check the logs. The integration no longer installs a Python library directly from Git.
- **A Zigbee dimmer shows status but does not react:** version 3 uses the Zigbee power and brightness functions instead of the classic RF functions. Check the configured local IP and UDP access, then try cloud control by removing an unreachable manual IP.
- **Sensors are unavailable:** check your cloud connection and the diagnostic status arrays. Missing or invalid status data is not presented as a successful update.
- **New devices are missing:** reload the integration after adding them in the Trust app.

Download diagnostics from **Settings > Devices & services > KlikAanKlikUit > Download diagnostics**. Account credentials, MAC addresses, local IP addresses and device names are redacted. Include the device type, Home Assistant version and relevant logs in an issue. Never include passwords or AES keys.

## Development

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/pytest
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
```

GitHub Actions runs the regression suite, Hassfest and HACS validation. The release and HACS submission procedure is in [PUBLISHING.md](PUBLISHING.md). Release changes are in [CHANGELOG.md](CHANGELOG.md).

## License

MIT. The protocol implementation builds on the ICS2000-Python projects by Stijn Jacobs and contributors. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
