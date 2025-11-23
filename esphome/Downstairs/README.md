# Downstairs Allrum

ESP32-C3 node that reads the MQ2 gas sensor and exposes a Bluetooth proxy for
Home Assistant coverage near the downstairs allrum area.

## LD2410 BLE Keep-Alive Monitor

- The node tracks LD2410 BLE advertisements from `23:69:7C:F1:5F:83`.
- Exposes two entities in Home Assistant:
  - **LD2410 Connected** (binary sensor): Shows connectivity status
  - **LD2410 Connection Status** (text sensor): Shows detailed status with time since last seen
- If the LD2410 stops advertising for more than 3 minutes, the status changes to "Missing" and logs a warning.
- After 10 minutes without contact it's marked as "Stale".
- **No automatic recovery/reboots** - when the sensor goes missing you'll need to manually reload the LD2410 BLE integration in Home Assistant.
- Update the MAC in `DownstairsAllrum.yaml` if the sensor is replaced.

This provides visibility into LD2410 connectivity issues without automatically restarting components that don't need restarting.

