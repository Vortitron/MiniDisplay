# Quick SNMP Testing Guide for AP7920

## Prerequisites
```bash
# Install SNMP tools on your system
sudo apt-get install snmp snmp-mibs-downloader
```

## Quick Test Commands

Replace `192.168.1.28` and `5stream` with your device IP and community string.

### Get Device Info
```bash
# Get PDU model
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.1.4.0

# Get serial number
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.1.5.0

# Get firmware version
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.1.2.0

# Get number of outlets
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.1.0
```

### Check Outlet Status
```bash
# Get outlet 1 status (1=On, 2=Off, 3=Reboot, 4=Unknown)
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.2.1.3.1

# Get outlet 1 name
snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.2.1.4.1

# Get all outlet statuses
for i in {1..8}; do
  echo "Outlet $i:"
  snmpget -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.2.1.3.$i
done
```

### Control Outlets
```bash
# Turn ON outlet 1
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.2.1.3.1 i 1

# Turn OFF outlet 1
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.2.1.3.1 i 2

# REBOOT outlet 1
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4.2.1.3.1 i 3
```

### Master Controls
```bash
# Turn ALL outlets ON immediately
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.2.1.0 i 1

# Turn ALL outlets OFF immediately
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.2.1.0 i 3

# REBOOT all outlets immediately
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.2.1.0 i 4
```

### Set Outlet Names
```bash
# Set outlet 1 name to "Router"
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.5.2.1.3.1 s "Router"

# Set outlet 2 name to "Switch"
snmpset -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.5.2.1.3.2 s "Switch"
```

### Browse All Available OIDs
```bash
# Walk the entire APC tree (will show all available OIDs)
snmpwalk -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318

# Walk just the PDU outlets
snmpwalk -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318.1.1.4.4

# Look for any power monitoring OIDs (if they exist)
snmpwalk -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318 | grep -i power
snmpwalk -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318 | grep -i current
snmpwalk -v1 -c 5stream 192.168.1.28 .1.3.6.1.4.1.318 | grep -i watt
```

## Batch Testing Script

Create a file `test_pdu.sh`:

```bash
#!/bin/bash
PDU_IP="192.168.1.28"
COMMUNITY="5stream"

echo "=== APC PDU Information ==="
echo "Model: $(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.4.1.4.0 -Oqv)"
echo "Serial: $(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.4.1.5.0 -Oqv)"
echo "Firmware: $(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.4.1.2.0 -Oqv)"
echo "Outlet Count: $(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.4.4.1.0 -Oqv)"

echo ""
echo "=== Outlet Status ==="
for i in {1..8}; do
  NAME=$(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.4.4.2.1.4.$i -Oqv 2>/dev/null)
  STATUS=$(snmpget -v1 -c $COMMUNITY $PDU_IP .1.3.6.1.4.1.318.1.1.4.4.2.1.3.$i -Oqv 2>/dev/null)
  
  if [ ! -z "$STATUS" ]; then
    case $STATUS in
      1) STATUS_TEXT="ON" ;;
      2) STATUS_TEXT="OFF" ;;
      3) STATUS_TEXT="REBOOT" ;;
      4) STATUS_TEXT="UNKNOWN" ;;
      *) STATUS_TEXT="ERROR" ;;
    esac
    echo "Outlet $i [$NAME]: $STATUS_TEXT"
  fi
done
```

Make it executable and run:
```bash
chmod +x test_pdu.sh
./test_pdu.sh
```

## Expected Output Examples

### Successful Connection
```
SNMPv2-SMI::enterprises.318.1.1.4.1.4.0 = STRING: "AP7920"
```

### Connection Failed
```
Timeout: No Response from 192.168.1.28
```

### Write Access Denied
```
Error in packet.
Reason: (noSuchName) There is no such variable name in this MIB.
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Timeout | Check IP address, firewall, network connectivity |
| No Response | Verify SNMP is enabled on PDU |
| Write fails | Check community string has write permissions |
| OID not found | Outlet number may exceed device capacity |
| Wrong value type | Ensure using 'i' for integer, 's' for string |

## Notes

- All SET operations require write-enabled community string
- Some PDUs may have different outlet numbering (0-based vs 1-based)
- Always verify critical outlets before automation
- Test during maintenance window

