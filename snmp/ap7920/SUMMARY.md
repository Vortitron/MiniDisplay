# APC AP7920 Configuration Summary

## 🎉 Great News!

Your AP7920 PDU has **advanced features** via the rPDU2 MIB! The SNMP walk revealed OID tree `.1.3.6.1.4.1.318.1.1.12` which provides extended monitoring capabilities beyond the basic PowerNet MIB.

## Your Device Details

- **Model**: AP7920
- **Serial**: ZA1122010917
- **Firmware**: v3.7.3 (dated 05/25/2011)
- **Outlets**: 8
- **Rated Voltage**: 208V
- **Max Current**: 10.0A (1000 in raw SNMP = tenths of amps)

## What's Included

### 📁 Configuration Files

1. **`configuration.yaml`**
   - Basic outlet control (on/off/reboot)
   - Outlet status monitoring
   - Device information
   - **Use this if**: You only need outlet control

2. **`configuration_with_power.yaml`** ⭐ **RECOMMENDED TO TRY**
   - Everything from configuration.yaml
   - Power monitoring sensors (per-outlet and overall)
   - Bank/Phase load monitoring
   - Voltage and current ratings
   - **Use this if**: You want power monitoring (may require testing)

3. **`POWER_MONITORING.md`**
   - Detailed testing guide
   - How to verify power monitoring works
   - Instructions to decode base64 power values
   - Test scripts

4. **`TESTING.md`**
   - Quick SNMP command reference
   - Testing scripts for outlet control
   - Troubleshooting tips

5. **`LIMITATIONS.md`** ⚠️ **IMPORTANT**
   - Home Assistant SNMP integration limitations
   - Device grouping workarounds
   - UI management restrictions
   - Alternative solutions

6. **`README.md`**
   - Complete documentation
   - Installation instructions
   - OID reference tables
   - Security recommendations

## Quick Start Guide

### Step 1: Test Basic Connectivity

```bash
# Verify SNMP is working
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.1.5.0

# Should return: STRING: "AP7920"
```

### Step 2: Test Outlet Control

```bash
# Turn outlet 1 ON
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.1 i 1

# Turn outlet 1 OFF
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.1 i 2
```

### Step 3: Test Power Monitoring (Optional)

```bash
# Check if power monitoring is available
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.1

# Check bank load state
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.2.3.1.1.3.1
```

### Step 4: Add to Home Assistant

> ⚠️ **Note**: The SNMP integration doesn't support device grouping. See `LIMITATIONS.md` for workarounds.

1. Choose your configuration file:
   - Start with `configuration_with_power.yaml` 
   - Fall back to `configuration.yaml` if power monitoring doesn't work

2. Copy the contents to your Home Assistant `configuration.yaml`

3. Restart Home Assistant

4. Check for new entities in Developer Tools → States

## Expected Entities in Home Assistant

### With Basic Configuration (configuration.yaml)
- 8 × Switches: `switch.apc_pdu_outlet_1` through `switch.apc_pdu_outlet_8`
- 8 × Status Sensors: `sensor.apc_pdu_outlet_1_status` through `sensor.apc_pdu_outlet_8_status`
- 8 × Name Sensors: `sensor.apc_pdu_outlet_1_name` through `sensor.apc_pdu_outlet_8_name`
- Device Info Sensors: Model, Serial, Firmware, etc.

### With Power Configuration (configuration_with_power.yaml)
All of the above PLUS:
- 8 × Power Sensors: `sensor.apc_pdu_outlet_1_power` through `sensor.apc_pdu_outlet_8_power`
- PDU Voltage: `sensor.apc_pdu_rated_voltage`
- PDU Max Current: `sensor.apc_pdu_rated_max_current`
- Bank Load State: `sensor.apc_pdu_bank_1_load_state`

## Power Monitoring Status

Your SNMP walk showed:
- ✅ rPDU2 MIB is present (`.1.3.6.1.4.1.318.1.1.12`)
- ✅ Voltage rating available (208V)
- ✅ Current rating available (10.0A)
- ✅ Bank load monitoring available
- ⚠️ Per-outlet power shows as `Gauge32: 0` in the walk
- ⚠️ Base64-encoded values present (may contain power data)

**Possible reasons for zero power readings:**
1. Outlets were off during SNMP walk
2. No load connected to outlets
3. This hardware variant doesn't support per-outlet metering
4. Power values are encoded in the base64 strings

**To verify**: Connect a device to an outlet, turn it on, then check the power OID again.

## What the Base64 Values Might Mean

From your SNMP walk, these base64 values were found:
- Outlet 1: "161" (decoded from "MTYx")
- Outlet 2: "23" (decoded from "MjM=")
- Outlet 3: "80" (decoded from "ODA=")

These could be:
- Power in watts (if outlets were on during walk)
- Historical/cached values
- Different measurement unit

See `POWER_MONITORING.md` to decode and test these values.

## Your Outlet Names (from SNMP walk)

Current configuration on your PDU:
1. **Outlet 1**: "cv5" ← Custom name
2. **Outlet 2**: "Outlet 2" ← Default
3. **Outlet 3**: "Outlet 3" ← Default
4. **Outlet 4**: "Outlet 4" ← Default
5. **Outlet 5**: "Outlet 5" ← Default
6. **Outlet 6**: "Outlet 6" ← Default
7. **Outlet 7**: "cV4" ← Custom name
8. **Outlet 8**: "Outlet 8" ← Default

## Recommended Next Steps

### Immediate (Do This First)
1. ✅ Copy `configuration_with_power.yaml` to Home Assistant
2. ✅ Restart Home Assistant
3. ✅ Test outlet switches in Home Assistant UI
4. ✅ Check if power sensors show values

### If Power Monitoring Works
1. 🎉 You're done! Enjoy your fully monitored PDU
2. Consider creating dashboard cards (examples in README.md)
3. Set up energy monitoring in Home Assistant
4. Create automations based on power consumption

### If Power Shows Zero
1. 📖 Read `POWER_MONITORING.md`
2. 🧪 Run the test script with outlets under load
3. 🔍 Try the base64 decoding methods
4. 💬 Report findings (update this summary if you want)
5. 🔄 Fall back to `configuration.yaml` if no power data available

### Optional Enhancements
1. Set up SNMP v3 for better security
2. Configure trap receivers for alerts
3. Create energy dashboard in Home Assistant
4. Add outlet grouping/scenes

## Important OID Differences

### Old PowerNet MIB (what I initially used):
- Base: `.1.3.6.1.4.1.318.1.1.4`
- Limited to basic control
- No power monitoring

### rPDU2 MIB (what you actually have):
- Base: `.1.3.6.1.4.1.318.1.1.12`
- Advanced features
- Power monitoring capable
- Better outlet management

**Always use rPDU2 OIDs** (the `.1.1.12` tree) for best results!

## Support Resources

- **Testing Commands**: See `TESTING.md`
- **Power Monitoring**: See `POWER_MONITORING.md`
- **Full Documentation**: See `README.md`
- **MIB Reference**: See `PowerNet-MIB.txt`

## Questions to Answer (For Best Configuration)

1. **Do you see power values in Home Assistant after adding the config?**
   - YES → Perfect! You have full monitoring
   - NO → Follow power monitoring testing guide

2. **Are all 8 outlets used?**
   - If not, you can remove unused outlet sensors

3. **Do you want total PDU power consumption?**
   - Available via template sensor if individual outlets work
   - Or use bank-level monitoring

4. **Do you need historical energy data?**
   - Enable Home Assistant's Energy dashboard
   - Consider InfluxDB for long-term storage

## Security Checklist

- [ ] Change SNMP community from "5stream" to something unique
- [ ] Consider upgrading to SNMPv3
- [ ] Restrict SNMP access to Home Assistant IP only (PDU firewall/ACL)
- [ ] Keep separate read-only community for monitoring
- [ ] Document your configuration changes

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Can't connect | Check IP, community string, firewall |
| Switches don't work | Verify write permissions on community |
| Power shows zero | See POWER_MONITORING.md |
| All sensors unknown | Check Home Assistant logs |
| Entities not appearing | Restart HA, check YAML syntax |

---

**Last Updated**: Based on SNMP walk from your AP7920
**Firmware**: v3.7.3 (05/25/2011)
**SNMP Community**: 5stream (change this for security!)

