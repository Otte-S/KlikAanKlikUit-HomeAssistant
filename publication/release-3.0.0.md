# KlikAanKlikUit 3.0.0

This release replaces the Git-installed client, fixes Zigbee command functions and corrects setup on current Home Assistant versions.

Cloud requests now have timeouts and retrieve all device statuses together. The options flow supports clearing a manual hub IP, and Home Assistant can request updated credentials when authentication fails.

The migration preserves existing supported entity IDs and custom names while making internal IDs unique per hub. Type 28 becomes a contact sensor. Unknown types, including type 53, are no longer exposed as generic lights. Review unavailable old entities and any automations using them.

Doorbell and wall-transmitter cloud states are experimental and disabled by default for new installations. They do not guarantee that every press is observed.

Requires Home Assistant 2026.9.3 or newer. See CHANGELOG.md for all changes.
