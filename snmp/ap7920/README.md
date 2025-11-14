# APC AP7920 PDU - Home Assistant Configuration

** Now HACS Integration https://github.com/Vortitron/HAAPC# **

> 🚀 **Quick Start**: Read [`SUMMARY.md`](SUMMARY.md) first for an overview and getting started guide!

## Device Information
- **Model**: APC AP7920 Switched Rack PDU
- **IP Address**: 192.168.1.28
- **SNMP Version**: v1
- **Community String**: 5stream
- **Firmware**: v3.7.3 (includes rPDU2 MIB support)
- **MIB Version**: PowerNet-MIB 3.0.2 + rPDU2 Extensions

## 📚 Documentation Files

| File | Purpose | Start Here? |
|------|---------|-------------|
| **[SUMMARY.md](SUMMARY.md)** | Overview, device details, quick start guide | ✅ **YES - Read this first!** |
| **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** | Command cheat sheet, common OIDs | 📌 Bookmark this |
| **[configuration.yaml](configuration.yaml)** | Basic HA config (control only) | Use if no power needed |
| **[configuration_with_power.yaml](configuration_with_power.yaml)** | Full HA config with power monitoring | ⭐ **Recommended** |
| **[LIMITATIONS.md](LIMITATIONS.md)** | SNMP integration limitations & workarounds | ⚠️ **Important - Read this** |
| **[POWER_MONITORING.md](POWER_MONITORING.md)** | Power monitoring testing guide | Read if power shows zero |
| **[TESTING.md](TESTING.md)** | SNMP testing commands and scripts | For troubleshooting |
| **[README.md](README.md)** | This file - Complete documentation | Reference guide |
| **[PowerNet-MIB.txt](PowerNet-MIB.txt)** | Official APC MIB file | For developers |

## Features Supported

### ✅ Available
- Outlet On/Off control (individual outlets)
- Outlet status monitoring
- PDU identification (model, serial, firmware)
- Outlet naming
- **rPDU2 MIB Support** (extended features at OID `.1.3.6.1.4.1.318.1.1.12`)
- Overall PDU voltage and current ratings
- Bank/Phase load monitoring

### ⚠️ May Be Available (Requires Testing)
- Individual outlet power consumption
- Individual outlet current monitoring
- Overall PDU power consumption
- Total power draw

**Note**: Your AP7920 has firmware v3.7.3 which includes the rPDU2 MIB with extended power monitoring OIDs. Power monitoring capability depends on your specific hardware variant. See `POWER_MONITORING.md` for testing instructions.

## Configuration Files

This directory contains three configuration files:

1. **`configuration.yaml`** - Basic outlet control and status monitoring (no power monitoring)
2. **`configuration_with_power.yaml`** - Includes power monitoring sensors using rPDU2 MIB OIDs
3. **`POWER_MONITORING.md`** - Testing guide to verify power monitoring capabilities

**Start with `configuration_with_power.yaml`** if you want power monitoring, or use `configuration.yaml` for basic control only.

## Installation

> ⚠️ **Important**: The Home Assistant SNMP integration has some limitations. See [`LIMITATIONS.md`](LIMITATIONS.md) for details about device grouping and UI management restrictions.

### 1. Add to Home Assistant Configuration

Add the contents of your chosen configuration file to your Home Assistant's main `configuration.yaml` file, or include it using:

```yaml
# In your main configuration.yaml
sensor: !include_dir_merge_list sensors/
switch: !include_dir_merge_list switches/
```

Then place the sensor and switch sections in separate files.

### 2. Verify SNMP Access

Before adding to Home Assistant, test SNMP access from your Home Assistant host:

```bash
# Install snmp tools (if not already installed)
sudo apt-get install snmp snmp-mibs-downloader

# Test connection - get outlet count
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.1.0

# Get outlet 1 status
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.2.1.3.1

# Get PDU model number
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.1.4.0
```

### 3. Adjust Outlet Count

The configuration assumes 8 outlets. To determine your actual outlet count:

```bash
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.1.0
```

Remove or add outlet configurations based on this number.

### 4. Restart Home Assistant

After adding the configuration:
```bash
# Check configuration
ha core check

# Restart
ha core restart
```

## Usage

### Individual Outlet Control

After restart, you'll have:
- **Switches**: `switch.apc_pdu_outlet_1` through `switch.apc_pdu_outlet_8`
- **Status Sensors**: `sensor.apc_pdu_outlet_1_status` through `sensor.apc_pdu_outlet_8_status`
- **Name Sensors**: `sensor.apc_pdu_outlet_1_name` through `sensor.apc_pdu_outlet_8_name`

### Example Automation - Scheduled Reboot

```yaml
automation:
  - alias: "Reboot Router Nightly"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.apc_pdu_outlet_1
      - delay: "00:00:30"
      - service: switch.turn_on
        target:
          entity_id: switch.apc_pdu_outlet_1
```

### Example Dashboard Card

```yaml
type: entities
title: APC PDU Outlets
entities:
  - entity: switch.apc_pdu_outlet_1
    name: Router
  - entity: switch.apc_pdu_outlet_2
    name: Switch
  - entity: switch.apc_pdu_outlet_3
    name: NAS
  - entity: switch.apc_pdu_outlet_4
    name: Server
  - entity: switch.apc_pdu_outlet_5
    name: Camera NVR
  - entity: switch.apc_pdu_outlet_6
    name: Access Point
  - entity: switch.apc_pdu_outlet_7
    name: Spare 1
  - entity: switch.apc_pdu_outlet_8
    name: Spare 2
```

## OID Reference

### Device Information (PowerNet MIB)
| Description | OID |
|-------------|-----|
| Hardware Revision | .1.3.6.1.4.1.318.1.1.4.1.1.0 |
| Firmware Revision | .1.3.6.1.4.1.318.1.1.4.1.2.0 |
| Model Number | .1.3.6.1.4.1.318.1.1.4.1.4.0 |
| Serial Number | .1.3.6.1.4.1.318.1.1.4.1.5.0 |
| Outlet Count | .1.3.6.1.4.1.318.1.1.4.4.1.0 |

### Device Information (rPDU2 MIB - Recommended)
| Description | OID |
|-------------|-----|
| PDU Name | .1.3.6.1.4.1.318.1.1.12.1.1.0 |
| Hardware Revision | .1.3.6.1.4.1.318.1.1.12.1.2.0 |
| Firmware Revision | .1.3.6.1.4.1.318.1.1.12.1.3.0 |
| Model Number | .1.3.6.1.4.1.318.1.1.12.1.5.0 |
| Serial Number | .1.3.6.1.4.1.318.1.1.12.1.6.0 |
| Outlet Count | .1.3.6.1.4.1.318.1.1.12.1.8.0 |
| Rated Voltage | .1.3.6.1.4.1.318.1.1.12.1.15.0 |
| Max Current (tenths) | .1.3.6.1.4.1.318.1.1.12.1.17.0 |

### Outlet Control (rPDU2 MIB - per outlet N)
| Description | OID |
|-------------|-----|
| Outlet N Control/Status | .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.N |
| Outlet N Name | .1.3.6.1.4.1.318.1.1.12.3.5.1.1.2.N |
| Outlet N Power (Watts) | .1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.N |

**Control Values:**
- 1 = On
- 2 = Off

### Master Control
| Description | OID | Values |
|-------------|-----|--------|
| Master Switch | .1.3.6.1.4.1.318.1.1.4.2.1.0 | 1=All On Now, 2=All On Seq, 3=All Off, 4=Reboot All, 5=Reboot Seq |

### Power Monitoring (rPDU2 MIB)
| Description | OID |
|-------------|-----|
| Phase/Bank Count | .1.3.6.1.4.1.318.1.1.12.2.1.1.0 |
| Bank 1 Load State | .1.3.6.1.4.1.318.1.1.12.2.3.1.1.3.1 |
| Outlet N Power | .1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.N |

**Load State Values:**
- 1 = Low Load
- 2 = Normal
- 3 = Near Overload
- 4 = Overload

## Troubleshooting

### Switches Don't Work
1. Verify SNMP community string is correct (case-sensitive)
2. Check that SNMP write access is enabled on the PDU
3. Ensure firewall allows UDP port 161 (SNMP)
4. Try manual SNMP set command:
   ```bash
   snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.2.1.3.1 i 1
   ```

### Sensors Show "Unknown"
1. Verify outlet exists (check outlet count)
2. Some outlets may be unavailable if PDU is in an error state
3. Check Home Assistant logs for SNMP errors

### Power Monitoring Shows Zero or Unavailable
1. **Check if outlets have load**: Power monitoring only works with devices connected and powered on
2. **Verify hardware variant**: Some AP7920 variants don't support per-outlet metering
3. **Test with the power monitoring guide**: See `POWER_MONITORING.md` for detailed testing
4. **Try alternative OIDs**: Some power data may be base64 encoded at `.1.3.6.1.4.1.318.1.4.2.6.1.4.N`
5. **Check bank-level monitoring**: Even without per-outlet metering, bank/phase power should work:
   ```bash
   snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.2.3.1.1.3.1
   ```

## Advanced Configuration

### Using SNMP to Reboot All Outlets

```yaml
# Create a script to reboot all outlets
script:
  pdu_reboot_all:
    alias: "Reboot All PDU Outlets"
    sequence:
      - service: shell_command.snmp_pdu_reboot_all

shell_command:
  snmp_pdu_reboot_all: 'snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.2.1.0 i 4'
```

### Setting Outlet Names via SNMP

You can set outlet names directly on the PDU:
```bash
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.5.2.1.3.1 s "Router"
```

OID format: `.1.3.6.1.4.1.318.1.1.4.5.2.1.3.N` where N is outlet number

## Security Recommendations

1. **Change Default Community**: Use a strong, unique community string
2. **Network Segmentation**: Place PDU on management VLAN
3. **Firewall Rules**: Restrict SNMP access to Home Assistant IP only
4. **Use SNMPv3**: If supported by your PDU, upgrade to SNMPv3 for encryption
5. **Read-Only Community**: Consider separate read-only community for monitoring

## Support & Resources

- [APC PowerNet MIB Documentation](http://www.apc.com)
- [Home Assistant SNMP Integration](https://www.home-assistant.io/integrations/snmp/)
- MIB File: `PowerNet-MIB.txt` (included in this directory)

## License

This configuration is provided as-is under the same license as the main MiniDisplay project.

