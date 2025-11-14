# Device Info & Unique ID Update

## ✅ What's Been Fixed

I've updated both configuration files to add:

1. **Unique IDs** for all entities (required for UI management)
2. **Device grouping** - all entities now appear under one device: **"APC PDU cAPC3"**
3. **Device identifiers** using your serial number: `apc_pdu_za1122010917`
4. **Manufacturer and model** info for proper device display

## 📋 Updated Files

### ✅ `configuration.yaml` - FULLY UPDATED
- All sensors have unique IDs
- All switches have unique IDs
- All entities grouped under device "APC PDU cAPC3"
- Ready to use!

### ⚠️ `configuration_with_power.yaml` - PARTIALLY UPDATED
- Device info sensors: ✅ Updated
- Power monitoring sensors: ✅ Updated
- Outlet sensors: ⏳ Needs completion
- Outlet switches: ⏳ Needs completion

## 🚀 Quick Start

### Option 1: Use Basic Config (Recommended for Now)
Use **`configuration.yaml`** - it's fully updated and will work perfectly:
```yaml
# Copy entire contents of configuration.yaml to your Home Assistant
```

This gives you:
- ✅ All 8 outlet controls
- ✅ All status monitoring
- ✅ Device info
- ✅ Full UI management
- ✅ Grouped under one device

### Option 2: Complete Power Config

If you need power monitoring, I can:
1. Continue updating `configuration_with_power.yaml` (will take a few more updates)
2. Or you can use the pattern below to add unique IDs yourself

## 🔧 Pattern for Adding Unique IDs

If you want to finish `configuration_with_power.yaml` yourself, here's the pattern:

### For Sensors:
```yaml
- platform: snmp
  name: "cAPC3 Outlet 1 Name"  # Changed from "APC PDU" to "cAPC3"
  unique_id: apc_pdu_capc3_outlet_1_name_power  # Add this line
  host: 192.168.1.28
  community: 5stream
  baseoid: .1.3.6.1.4.1.318.1.1.12.3.5.1.1.2.1
  version: "1"
  device:  # Add this block
    identifiers: "apc_pdu_za1122010917"
    name: "APC PDU cAPC3"
    manufacturer: "APC"
    model: "AP7920"
```

### For Switches:
```yaml
- platform: snmp
  name: "cAPC3 Outlet 1"  # Changed from "APC PDU" to "cAPC3"
  unique_id: apc_pdu_capc3_outlet_1_switch_power  # Add this line
  host: 192.168.1.28
  community: 5stream
  baseoid: .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.1
  version: "1"
  payload_on: 1
  payload_off: 2
  device:  # Add this block
    identifiers: "apc_pdu_za1122010917"
    name: "APC PDU cAPC3"
    manufacturer: "APC"
    model: "AP7920"
```

## 📊 What You'll See in Home Assistant

After adding the updated config and restarting:

### Device View
- **Device Name**: APC PDU cAPC3
- **Manufacturer**: APC
- **Model**: AP7920
- **Identifier**: apc_pdu_za1122010917

### Entities Under This Device
- 8 switches: `switch.capc3_outlet_1` through `switch.capc3_outlet_8`
- 8 status sensors: `sensor.capc3_outlet_1_status` through `sensor.capc3_outlet_8_status`
- 8 name sensors: `sensor.capc3_outlet_1_name` through `sensor.capc3_outlet_8_name`
- Plus device info sensors

## ✅ Verification

After restarting Home Assistant:

1. Go to **Settings → Devices & Services**
2. Find **"APC PDU cAPC3"**
3. Click on it to see all entities
4. All entities should now be manageable from the UI (no more warnings!)

## 🔄 Next Steps

### If Using `configuration.yaml` (Basic)
1. Copy contents to your Home Assistant `configuration.yaml`
2. Restart Home Assistant
3. Check Device page for "APC PDU cAPC3"
4. Done! ✅

### If You Want Power Monitoring
Let me know and I'll:
1. Complete updating `configuration_with_power.yaml` with all unique IDs
2. Add proper device info to all 40+ entities
3. Make it production-ready

## 📝 Notes

- **Device Identifier**: Uses your PDU's serial number `ZA1122010917`
- **Unique ID Format**: `apc_pdu_capc3_[entity]_[type]`
- **Names**: All changed from "APC PDU" to "cAPC3" for clarity
- **Grouping**: All entities will appear under one device in HA

## 🆘 Troubleshooting

### Still See "No Unique ID" Warning?
1. Delete the entity from Home Assistant
2. Restart Home Assistant
3. Entity will be recreated with unique ID

### Entities Not Grouped?
- Make sure `device` block is identical in all entities
- The `identifiers` field groups entities together
- All should use: `identifiers: "apc_pdu_za1122010917"`

### Want Different Device Name?
Change this in each entity:
```yaml
device:
  identifiers: "apc_pdu_za1122010917"  # Keep this the same
  name: "Your Custom Name Here"        # Change this
  manufacturer: "APC"
  model: "AP7920"
```

---

**Current Status**: `configuration.yaml` is complete and ready to use!  
**Need Power Monitoring?**: Let me know and I'll finish `configuration_with_power.yaml`

