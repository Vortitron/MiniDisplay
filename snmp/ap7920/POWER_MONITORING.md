# APC AP7920 Power Monitoring Guide

Based on your SNMP walk, your AP7920 supports the **rPDU2 MIB** (OID tree `.1.3.6.1.4.1.318.1.1.12`) which has power monitoring capabilities!

## Testing Power Monitoring

### 1. Check Overall PDU Power Capability

```bash
# Get rated voltage (should return 208V based on your SNMP walk)
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.1.15.0

# Get max current rating (1000 = 10.0A)
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.1.17.0

# Get phase/bank count
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.2.1.1.0
```

### 2. Check Per-Outlet Power (Gauges)

Your SNMP walk showed these as `Gauge32: 0` which means either:
- The outlets have no load connected
- This PDU variant doesn't support per-outlet metering
- Values are encoded differently

Test with an outlet that has load:

```bash
# Outlet 1 power (in watts or tenths of watts)
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.1

# Test all 8 outlets
for i in {1..8}; do
  echo "Outlet $i Power:"
  snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.$i
done
```

### 3. Decode Base64 Power Values

Your SNMP walk showed base64-encoded values at `.1.3.6.1.4.1.318.1.4.2.6.1.4.X`:

```bash
# Get base64 values for all outlets
for i in {1..8}; do
  VALUE=$(snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.4.2.6.1.4.$i -Oqv | tr -d '"')
  DECODED=$(echo $VALUE | base64 -d 2>/dev/null)
  echo "Outlet $i: Base64=$VALUE, Decoded=$DECODED"
done
```

From your SNMP walk, these decode to:
- Outlet 1: "161" 
- Outlet 2: "23"
- Outlet 3: "80"
- Outlet 4: "9950"
- Outlet 5: "9950"
- Outlet 6: "443"
- Outlet 7: "22"
- Outlet 8: "22"

These might be:
- Power in watts
- Current in tenths of amps (161 = 16.1A seems too high though)
- Some other metric

### 4. Check Bank/Phase Power

```bash
# Bank 1 load state (1=low, 2=normal, 3=near overload, 4=overload)
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.2.3.1.1.3.1

# Bank 1 current (if available)
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.2.3.1.1.2.1
```

## Common rPDU2 Power OIDs

Based on APC's rPDU2 MIB, try these OIDs:

### Device-Level Power
```bash
# Total PDU power consumption
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.1.16.0

# Phase/Bank power
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.2.3.1.1.2.1
```

### Outlet-Level Power
```bash
# Outlet N power (OID pattern from rPDU2 MIB)
# Try these patterns for outlet 1:

# Pattern 1: Direct power reading
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.1

# Pattern 2: Outlet current (might need to calculate power)
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.5.1.1.6.1

# Pattern 3: Outlet state and power combined table
snmpwalk -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.12.3.5.1.1
```

## Interpreting Results

### If Power Values Are In Tenths
If you get a value like `1234`, the actual power might be `123.4W`:

```yaml
value_template: "{{ (value | int / 10) | round(1) }}"
```

### If Power Values Are In Hundredths  
If you get a value like `12345`, the actual power might be `123.45W`:

```yaml
value_template: "{{ (value | int / 100) | round(2) }}"
```

### If Using Current Instead of Power
Calculate power from current and voltage:

```yaml
# Assuming 208V from your PDU
value_template: "{{ ((value | int / 10) * 208) | round(0) }}"
```

## Test Script

Save this as `test_power.sh`:

```bash
#!/bin/bash
PDU_IP="192.168.1.28"
COMMUNITY="5stream"

echo "=== APC PDU Power Information ==="
echo ""
echo "Device Info:"
echo "Rated Voltage: $(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.12.1.15.0 -Oqv)V"
echo "Max Current: $(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.12.1.17.0 -Oqv | awk '{print $1/100}')A"
echo ""

echo "Bank/Phase Power:"
BANK_STATE=$(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.12.2.3.1.1.3.1 -Oqv)
echo "Bank 1 State: $BANK_STATE (1=Low, 2=Normal, 3=NearOverload, 4=Overload)"
echo ""

echo "=== Outlet Power Readings ==="
for i in {1..8}; do
  NAME=$(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.12.3.5.1.1.2.$i -Oqv 2>/dev/null | tr -d '"')
  STATUS=$(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.12.3.5.1.1.4.$i -Oqv 2>/dev/null)
  POWER=$(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.12.3.5.1.1.7.$i -Oqv 2>/dev/null)
  
  # Try to decode base64 value
  B64=$(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.4.2.6.1.4.$i -Oqv 2>/dev/null | tr -d '"')
  if [ ! -z "$B64" ]; then
    DECODED=$(echo "$B64" | base64 -d 2>/dev/null)
  else
    DECODED="N/A"
  fi
  
  STATUS_TEXT="Unknown"
  case $STATUS in
    1) STATUS_TEXT="ON" ;;
    2) STATUS_TEXT="OFF" ;;
  esac
  
  echo "Outlet $i [$NAME]:"
  echo "  Status: $STATUS_TEXT"
  echo "  Power (Gauge): $POWER"
  echo "  Power (Base64 Decoded): $DECODED"
  echo ""
done

echo "=== Additional Power OIDs to Check ==="
echo "Try these manually to find working power OIDs:"
echo "  snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.12.1.16.0"
echo "  snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.12.2.3.1.1.2.1"
```

Make it executable:
```bash
chmod +x test_power.sh
./test_power.sh
```

## Home Assistant Template Sensor for Total Power

If individual outlet power works, create a total power sensor:

```yaml
template:
  - sensor:
      - name: "APC PDU Total Power"
        unit_of_measurement: "W"
        device_class: power
        state: >
          {{
            (states('sensor.apc_pdu_outlet_1_power') | float(0)) +
            (states('sensor.apc_pdu_outlet_2_power') | float(0)) +
            (states('sensor.apc_pdu_outlet_3_power') | float(0)) +
            (states('sensor.apc_pdu_outlet_4_power') | float(0)) +
            (states('sensor.apc_pdu_outlet_5_power') | float(0)) +
            (states('sensor.apc_pdu_outlet_6_power') | float(0)) +
            (states('sensor.apc_pdu_outlet_7_power') | float(0)) +
            (states('sensor.apc_pdu_outlet_8_power') | float(0))
          }}
```

## Next Steps

1. Run the test script to see which OIDs return power data
2. Identify the correct value scaling (tenths, hundredths, etc.)
3. Update the Home Assistant configuration with the working OIDs
4. Share your findings if you want me to update the configuration!

## Model Variants

**Note**: The AP7920 comes in different variants:
- **AP7920** - Switched Rack PDU (no metering)
- **AP7920B** - With environmental monitoring
- **AP8953** - Switched, metered variant

If your power gauges all show 0, your specific unit might not support per-outlet metering, but should still support overall PDU current/power monitoring at the bank level.

