# Downstairs Allrum

ESP32-C3 node that reads the MQ2 gas sensor and exposes a Bluetooth proxy for
Home Assistant coverage near the downstairs allrum area.

## LD2410 BLE Keep-Alive Monitor

- The node tracks LD2410 BLE advertisements from `23:69:7C:F1:5F:83` (configurable via `ld2410_mac` substitution in `DownstairsAllrum.yaml`).
- Exposes two entities in Home Assistant:
  - **LD2410 Connected** (binary sensor): Shows connectivity status
  - **LD2410 Connection Status** (text sensor): Shows detailed status with time since last seen
- If the LD2410 stops advertising for more than 3 minutes, the status changes to "Missing" and logs a warning.
- After 10 minutes without contact it's marked as "Stale".

### Automatic recovery (new)

- **Important note**: Some BLE devices reduce/stop advertisements while they are actively connected. For that reason, “not seen” does **not always** mean “disconnected”.

#### HA watchdog-based recovery (recommended)

- If you enable the HA watchdog (`ld2410_ha_watchdog_enabled: "true"`) and point it at the affected HA entity (`ld2410_ha_watchdog_entity_id`), the node will trigger recovery **only when Home Assistant marks that entity `unavailable`**.
- Recovery is rate-limited to once per 10 minutes to avoid loops.

#### Optional HA integration reload

- If you set `ld2410_ha_entry_id` (in `DownstairsAllrum.yaml`) to your LD2410 integration `entry_id`, the node will also call `homeassistant.reload_config_entry` as part of recovery.
  - **How to find `entry_id`**: Open the LD2410 integration in Home Assistant and copy the `config_entry=...` value from the URL.

- Update the MAC in `DownstairsAllrum.yaml` if the sensor is replaced.

This provides visibility into LD2410 connectivity issues and adds lightweight auto-recovery to avoid manual HA reloads in common failure cases.

