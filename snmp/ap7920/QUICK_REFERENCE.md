# APC AP7920 - Quick Reference Card

**Device**: 192.168.1.28 | **Community**: 5stream | **SNMP**: v1

## Most Common Commands

### Check PDU Status
```bash
# Get model
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.1.5.0

# Get all outlet status
for i in {1..8}; do echo "Outlet $i: $(snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.$i -Oqv)"; done
```

### Control Outlets
```bash
# Turn ON outlet 1
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.1 i 1

# Turn OFF outlet 1
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.1 i 2

# Turn OFF all outlets
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.2.1.0 i 3
```

### Check Power
```bash
# Outlet 1 power
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.1

# Bank load state (1=Low, 2=Normal, 3=NearOverload, 4=Overload)
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.2.3.1.1.3.1
```

## Essential OIDs

| What | OID | Notes |
|------|-----|-------|
| **Model** | `.1.3.6.1.4.1.318.1.1.12.1.5.0` | AP7920 |
| **Serial** | `.1.3.6.1.4.1.318.1.1.12.1.6.0` | ZA1122010917 |
| **Firmware** | `.1.3.6.1.4.1.318.1.1.12.1.3.0` | v3.7.3 |
| **Outlet Count** | `.1.3.6.1.4.1.318.1.1.12.1.8.0` | 8 |
| **Voltage** | `.1.3.6.1.4.1.318.1.1.12.1.15.0` | 208V |

## Per-Outlet OIDs (Replace N with 1-8)

| What | OID Pattern | Values |
|------|------------|--------|
| **Control** | `.1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.N` | 1=On, 2=Off |
| **Status** | `.1.3.6.1.4.1.318.1.1.12.3.5.1.1.4.N` | 1=On, 2=Off |
| **Name** | `.1.3.6.1.4.1.318.1.1.12.3.5.1.1.2.N` | String |
| **Power** | `.1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.N` | Watts |

## Your Current Outlets

1. cv5
2. Outlet 2
3. Outlet 3
4. Outlet 4
5. Outlet 5
6. Outlet 6
7. cV4
8. Outlet 8

## Home Assistant Entity Names

### Switches
- `switch.apc_pdu_outlet_1` through `switch.apc_pdu_outlet_8`

### Sensors
- `sensor.apc_pdu_outlet_1_status` through `sensor.apc_pdu_outlet_8_status`
- `sensor.apc_pdu_outlet_1_name` through `sensor.apc_pdu_outlet_8_name`
- `sensor.apc_pdu_outlet_1_power` through `sensor.apc_pdu_outlet_8_power`

### Device Info
- `sensor.apc_pdu_model_number`
- `sensor.apc_pdu_serial_number`
- `sensor.apc_pdu_firmware_revision`
- `sensor.apc_pdu_rated_voltage`
- `sensor.apc_pdu_bank_1_load_state`

## Quick Automation Examples

### Reboot Router Daily
```yaml
automation:
  - alias: "Reboot Router at 3am"
    trigger:
      platform: time
        at: "03:00:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.apc_pdu_outlet_1
      - delay: 30
      - service: switch.turn_on
        target:
          entity_id: switch.apc_pdu_outlet_1
```

### Alert on High Power
```yaml
automation:
  - alias: "Alert High Power Outlet 1"
    trigger:
      platform: numeric_state
      entity_id: sensor.apc_pdu_outlet_1_power
      above: 1500
    action:
      service: notify.mobile_app
      data:
        message: "Outlet 1 power is {{ states('sensor.apc_pdu_outlet_1_power') }}W!"
```

## Troubleshooting One-Liners

```bash
# Test connectivity
ping 192.168.1.28

# Test SNMP read
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.1.5.0

# Test SNMP write (toggle outlet 8 which seems unused)
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.8 i 2

# Get all data (walk)
snmpwalk -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12 > pdu_walk.txt

# Check Home Assistant config
ha core check
```

## Files in This Directory

| File | Purpose |
|------|---------|
| **SUMMARY.md** | Start here! Overview and quick start |
| **configuration.yaml** | Basic HA config (control only) |
| **configuration_with_power.yaml** | Full HA config with power |
| **POWER_MONITORING.md** | Testing guide for power features |
| **TESTING.md** | SNMP testing commands |
| **README.md** | Complete documentation |
| **QUICK_REFERENCE.md** | This file! |

## Remember

- ⚠️ **Change your SNMP community** from "5stream" to something secure
- 🔒 **Restrict SNMP** access to Home Assistant IP only
- 📊 **Test power monitoring** before relying on it
- 💾 **Backup** your PDU configuration
- 📖 **Read SUMMARY.md** first if you're new

---

**Save this file** for quick command reference!

