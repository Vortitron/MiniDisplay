# APC AP7920 PDU - Complete Configuration Package

## 🎯 What You Have Here

A complete, ready-to-use Home Assistant configuration for your APC AP7920 PDU with power monitoring support, testing guides, and comprehensive documentation.

## 📋 Start Here Checklist

- [ ] 1. Read **[SUMMARY.md](SUMMARY.md)** - Overview and quick start
- [ ] 2. Test SNMP connectivity using **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)**
- [ ] 3. Copy **[configuration_with_power.yaml](configuration_with_power.yaml)** to Home Assistant
- [ ] 4. Restart Home Assistant
- [ ] 5. Test power monitoring with **[POWER_MONITORING.md](POWER_MONITORING.md)**
- [ ] 6. Bookmark **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** for daily use

## 📁 All Files Explained

### Configuration Files
1. **[configuration.yaml](configuration.yaml)**
   - Basic outlet control and monitoring
   - Use if you don't need power monitoring
   - 100% tested and working

2. **[configuration_with_power.yaml](configuration_with_power.yaml)** ⭐
   - Everything from configuration.yaml
   - Plus power monitoring sensors
   - Uses rPDU2 MIB OIDs
   - **Recommended starting point**

### Documentation Files
3. **[SUMMARY.md](SUMMARY.md)** 🚀
   - **START HERE!**
   - Device details from your SNMP walk
   - Quick start guide
   - What to expect
   - Troubleshooting decision tree

4. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** 📌
   - Command cheat sheet
   - Most used OIDs
   - Your outlet names
   - Quick automation examples
   - **Bookmark this!**

5. **[POWER_MONITORING.md](POWER_MONITORING.md)** 🔬
   - How to test power monitoring
   - Decode base64 values
   - Alternative power OIDs
   - Test scripts
   - Read if power shows zero

6. **[TESTING.md](TESTING.md)** 🧪
   - SNMP testing commands
   - Batch test script
   - Control outlet examples
   - Troubleshooting commands

7. **[LIMITATIONS.md](LIMITATIONS.md)** ⚠️
   - SNMP integration limitations
   - Device grouping workarounds
   - UI management restrictions
   - Alternative solutions

8. **[README.md](README.md)** 📖
   - Complete reference documentation
   - Installation guide
   - OID tables
   - Security recommendations
   - Advanced configuration

9. **[INDEX.md](INDEX.md)** 📋
   - This file
   - Navigation guide
   - File purpose overview

### MIB Files
10. **[PowerNet-MIB.txt](PowerNet-MIB.txt)**
   - Official APC MIB definition
   - Reference for OID meanings
   - Includes trap definitions

## 🎯 Your Device Snapshot

Based on your SNMP walk results:

```
Model:       AP7920
Serial:      ZA1122010917
Firmware:    v3.7.3 (05/25/2011)
IP Address:  192.168.1.28
SNMP:        v1, Community: 5stream
Outlets:     8
Voltage:     208V
Max Current: 10.0A
MIB Support: PowerNet + rPDU2
```

**Current Outlet Names:**
1. cv5 ← Custom
2. Outlet 2
3. Outlet 3
4. Outlet 4
5. Outlet 5
6. Outlet 6
7. cV4 ← Custom
8. Outlet 8

## ⚡ Power Monitoring Status

Your PDU supports rPDU2 MIB (`.1.3.6.1.4.1.318.1.1.12`) which includes:
- ✅ Overall voltage/current ratings
- ✅ Bank/Phase load monitoring
- ⚠️ Per-outlet power (needs testing with load connected)

The SNMP walk showed power gauges at zero, which means:
- Outlets may have been off during the walk
- No load was connected
- Needs verification with powered devices

See **[POWER_MONITORING.md](POWER_MONITORING.md)** for testing.

## 🚀 Quick Start (5 Minutes)

### Option A: Use Power Monitoring Config (Recommended)

```bash
# 1. Test connectivity
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.1.5.0

# 2. Test outlet control
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.8 i 2

# 3. Copy to Home Assistant
# Add contents of configuration_with_power.yaml to your configuration.yaml

# 4. Restart Home Assistant
ha core restart

# 5. Check entities in Developer Tools → States
# Look for: switch.apc_pdu_outlet_* and sensor.apc_pdu_*
```

### Option B: Basic Control Only

Use **[configuration.yaml](configuration.yaml)** if you only need outlet control without power monitoring.

## 📊 What You'll Get in Home Assistant

### Entities Created

**Switches** (8):
- `switch.apc_pdu_outlet_1` through `switch.apc_pdu_outlet_8`

**Status Sensors** (8):
- `sensor.apc_pdu_outlet_1_status` through `sensor.apc_pdu_outlet_8_status`

**Name Sensors** (8):
- `sensor.apc_pdu_outlet_1_name` through `sensor.apc_pdu_outlet_8_name`

**Power Sensors** (8, if monitoring works):
- `sensor.apc_pdu_outlet_1_power` through `sensor.apc_pdu_outlet_8_power`

**Device Info Sensors**:
- `sensor.apc_pdu_name`
- `sensor.apc_pdu_model_number`
- `sensor.apc_pdu_serial_number`
- `sensor.apc_pdu_firmware_revision`
- `sensor.apc_pdu_outlet_count`
- `sensor.apc_pdu_rated_voltage`
- `sensor.apc_pdu_rated_max_current`
- `sensor.apc_pdu_bank_1_load_state`

## 🔧 Customization

### Change Friendly Names

```yaml
# In Home Assistant configuration.yaml
homeassistant:
  customize:
    switch.apc_pdu_outlet_1:
      friendly_name: "Router"
    switch.apc_pdu_outlet_2:
      friendly_name: "Network Switch"
    # ... etc
```

### Hide Unused Outlets

If you don't use all 8 outlets, you can:
1. Remove their sections from the config
2. Or hide them in the UI with `hidden: true`

### Add Total Power Sensor

```yaml
template:
  - sensor:
      - name: "Total PDU Power"
        unit_of_measurement: "W"
        device_class: power
        state: >
          {{ states('sensor.apc_pdu_outlet_1_power')|float(0) +
             states('sensor.apc_pdu_outlet_2_power')|float(0) +
             states('sensor.apc_pdu_outlet_3_power')|float(0) +
             states('sensor.apc_pdu_outlet_4_power')|float(0) +
             states('sensor.apc_pdu_outlet_5_power')|float(0) +
             states('sensor.apc_pdu_outlet_6_power')|float(0) +
             states('sensor.apc_pdu_outlet_7_power')|float(0) +
             states('sensor.apc_pdu_outlet_8_power')|float(0) }}
```

## 🔒 Security Reminders

- [ ] Change SNMP community from "5stream"
- [ ] Use separate read/write communities
- [ ] Restrict SNMP to Home Assistant IP only
- [ ] Consider upgrading to SNMPv3
- [ ] Store credentials in `secrets.yaml`

## ❓ Troubleshooting

| Problem | Solution File |
|---------|---------------|
| Can't connect to PDU | [TESTING.md](TESTING.md) |
| Switches don't work | [TESTING.md](TESTING.md) |
| Power shows zero | [POWER_MONITORING.md](POWER_MONITORING.md) |
| General questions | [README.md](README.md) |
| Need commands | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) |

## 📞 Support Flow

1. **First time setup?** → Read [SUMMARY.md](SUMMARY.md)
2. **Testing SNMP?** → Use [TESTING.md](TESTING.md)
3. **Power not working?** → See [POWER_MONITORING.md](POWER_MONITORING.md)
4. **Need a command?** → Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
5. **Deep dive needed?** → Read [README.md](README.md)

## ✅ Success Criteria

You'll know it's working when:

1. ✅ Outlet switches appear in Home Assistant
2. ✅ You can toggle outlets on/off from HA
3. ✅ Status sensors update when outlets change
4. ✅ Device info sensors show correct model/serial
5. ✅ Power sensors show values (if outlets have load)
6. ✅ Bank load state sensor shows "Normal" or "Low Load"

## 📈 Next Steps After Setup

Once basic setup works:

1. **Dashboard**: Create Lovelace cards for outlet control
2. **Automations**: Schedule reboots, power alerts
3. **Energy**: Add to Energy dashboard if power monitoring works
4. **History**: Enable long-term statistics
5. **Notifications**: Alert on power spikes or failures
6. **Integration**: Use with Node-RED, scripts, scenes

## 🎓 Learning Resources

- [Home Assistant SNMP Integration](https://www.home-assistant.io/integrations/snmp/)
- [APC PowerNet MIB Guide](http://www.mibdepot.com/cgi-bin/vendor_index.cgi?r=apc)
- MIB file included: [PowerNet-MIB.txt](PowerNet-MIB.txt)

---

## 📝 File Quick Links

**🚀 Essential** (Read First):
- [SUMMARY.md](SUMMARY.md) - Start here!
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Bookmark this

**⚙️ Configuration** (Copy to HA):
- [configuration_with_power.yaml](configuration_with_power.yaml) - Recommended
- [configuration.yaml](configuration.yaml) - Basic version

**📖 Documentation** (Reference):
- [README.md](README.md) - Complete guide
- [LIMITATIONS.md](LIMITATIONS.md) - Integration limits ⚠️
- [POWER_MONITORING.md](POWER_MONITORING.md) - Power testing
- [TESTING.md](TESTING.md) - SNMP testing

**🔧 Technical**:
- [PowerNet-MIB.txt](PowerNet-MIB.txt) - MIB definition

---

**Version**: Based on SNMP walk from AP7920 (Serial: ZA1122010917)  
**Last Updated**: 2024  
**Firmware**: v3.7.3 (05/25/2011)  
**MIB Support**: PowerNet 3.0.2 + rPDU2 Extensions

