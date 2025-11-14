# Home Assistant SNMP Integration Limitations

## Device Grouping Not Supported

Unfortunately, the Home Assistant SNMP integration does **not support** the following features that many other integrations provide:

### ❌ Not Supported by SNMP Integration

1. **`device` parameter** - Cannot group entities under a single device in the UI
2. **`unique_id` for switches** - Switches cannot be configured from the UI (sensors support `unique_id`)

### What This Means

- **Sensors** (like Outlet 1 Name, Outlet 1 Status, power readings) can be managed from the UI because they support `unique_id`
- **Switches** (like outlet controls) cannot be customized from the UI - you must edit YAML to change their settings
- All entities appear as individual items rather than being grouped under a single "APC PDU cAPC3" device

## Alternative Solutions

If you need device grouping and full UI management, consider these alternatives:

### Option 1: Use Areas in Home Assistant

Group your PDU entities by assigning them to a Home Assistant Area:

1. Go to **Settings** → **Areas**
2. Create an area called "Rack PDU" or "cAPC3"
3. Assign all PDU entities to this area from the entity settings

### Option 2: Use Groups

Create a group in your `configuration.yaml`:

```yaml
group:
  apc_pdu_capc3:
    name: "APC PDU cAPC3"
    entities:
      - sensor.capc3_outlet_1_name
      - sensor.capc3_outlet_1_status
      - switch.capc3_outlet_1
      - sensor.capc3_outlet_2_name
      - sensor.capc3_outlet_2_status
      - switch.capc3_outlet_2
      # ... add all other entities
```

### Option 3: Use MQTT Bridge (Advanced)

For full device support with grouping:

1. Set up an MQTT broker
2. Create a Python script that:
   - Polls SNMP values
   - Publishes them via MQTT with Home Assistant discovery
   - Supports full device grouping

This requires more setup but provides the best integration experience.

### Option 4: Custom Integration

Develop a custom Home Assistant integration specifically for APC PDUs that uses SNMP internally but provides proper device entities. This is the most complex option but would provide the best user experience.

## What We've Done

To work within these limitations:

- ✅ Removed all `device` blocks from the configuration (they were causing errors)
- ✅ Removed `unique_id` from all switches (not supported)
- ✅ Kept `unique_id` for all sensors (these work and allow UI management)
- ✅ Used descriptive names with "cAPC3" prefix for easy identification

## Configuration Files

- **`configuration.yaml`** - Basic configuration (control + status only)
- **`configuration_with_power.yaml`** - Extended configuration with power monitoring

Both files are now compatible with Home Assistant's SNMP integration limitations.

## Future Improvements

The Home Assistant SNMP integration may add these features in the future. Monitor these resources:

- [Home Assistant SNMP Integration Documentation](https://www.home-assistant.io/integrations/snmp/)
- [Home Assistant Feature Requests](https://community.home-assistant.io/c/feature-requests/13)

If device grouping is added to the SNMP integration, we can update these configuration files to use it.

