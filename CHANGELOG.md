# Changelog

## 3.0.0

- Replace the Git-installed client with an asynchronous client using Home Assistant's HTTP session.
- Bound cloud requests to 15 seconds and send account fields in HTTPS form bodies.
- Fetch all device statuses in one request per update.
- Use separate command functions and brightness ranges for classic and Zigbee dimmers.
- Send a power-on command after setting brightness, and treat brightness zero as off.
- Preserve optimistic brightness until both power and brightness match the cloud response.
- Create type-46 temperature and humidity sensors consistently.
- Report cloud failures and missing sensor data rather than successful empty updates.
- Keep local light and gong commands available during cloud outages after initial setup.
- Correct the options flow for current Home Assistant and add reauthentication.
- Validate MAC and IPv4 addresses and match the MAC during hub discovery.
- Introduce hub-scoped entity and device identities, with migration for existing entities.
- Make momentary input states experimental and disabled by default for new installations.
- Stop treating unknown device types as controllable lights; classify type 28 as a contact sensor.
- Redact account information, addresses and device names in diagnostics.
- Add regression tests, release documentation and publication checks.
