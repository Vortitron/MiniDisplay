# SNMP Device Configurations

This directory contains SNMP configurations for various network devices integrated with Home Assistant.

## Devices

### APC AP7920 Rack PDU
**Location**: [`ap7920/`](ap7920/)

A complete Home Assistant integration for the APC AP7920 Switched Rack PDU with power monitoring capabilities.

**Features**:
- ✅ Individual outlet control (8 outlets)
- ✅ Outlet status monitoring
- ✅ Power monitoring (per-outlet and overall)
- ✅ Bank/Phase load monitoring
- ✅ Device identification and status

**Quick Start**: See [`ap7920/SUMMARY.md`](ap7920/SUMMARY.md)

**Device Info**:
- Model: AP7920
- IP: 192.168.1.28
- SNMP: v1
- Firmware: v3.7.3 with rPDU2 MIB support

**Files**:
- Configuration files for Home Assistant
- Power monitoring testing guides
- SNMP testing commands
- Complete documentation

---

## Adding New Devices

To add a new SNMP device:

1. Create a directory: `snmp/device-name/`
2. Add configuration file: `configuration.yaml`
3. Add MIB file if applicable: `device-MIB.txt`
4. Document with `README.md`
5. Include testing guide

## SNMP Resources

### General SNMP Commands

```bash
# Get a single OID value
snmpget -v1 -c COMMUNITY IP_ADDRESS OID

# Get all values under an OID tree
snmpwalk -v1 -c COMMUNITY IP_ADDRESS OID

# Set a value
snmpset -v1 -c COMMUNITY IP_ADDRESS OID TYPE VALUE

# Types: i=integer, s=string, a=ipaddress
```

### Common Enterprise OIDs

- **APC**: `.1.3.6.1.4.1.318`
- **Cisco**: `.1.3.6.1.4.1.9`
- **HP**: `.1.3.6.1.4.1.11`
- **Dell**: `.1.3.6.1.4.1.674`
- **Netgear**: `.1.3.6.1.4.1.4526`

### MIB Resources

- [IANA Enterprise Numbers](https://www.iana.org/assignments/enterprise-numbers/)
- [MIB Depot](http://www.mibdepot.com/)
- [CIRCITOR MIB Database](http://www.circitor.fr/Mibs/)

## Security Best Practices

1. **Use SNMPv3** when possible (encryption + authentication)
2. **Change default community strings** to something unique
3. **Use separate read-only communities** for monitoring
4. **Restrict SNMP access** by IP address (firewall/ACL)
5. **Disable SNMP write** if not needed
6. **Monitor SNMP access logs** for unauthorized attempts
7. **Keep community strings in secrets** (not in git)

### Home Assistant Secrets

Store SNMP credentials in `secrets.yaml`:

```yaml
# secrets.yaml
apc_pdu_ip: 192.168.1.28
apc_pdu_community: your_secret_community_string
```

Then use in configuration:

```yaml
# configuration.yaml
sensor:
  - platform: snmp
    host: !secret apc_pdu_ip
    community: !secret apc_pdu_community
    baseoid: .1.3.6.1.4.1.318.1.1.12.1.5.0
```

## Home Assistant SNMP Integration

- [Official SNMP Documentation](https://www.home-assistant.io/integrations/snmp/)
- Supports sensors, switches, and binary sensors
- Poll-based (configurable scan interval)
- Template support for value transformation

## Contributing

When adding device configurations to this directory:

- Include complete working examples
- Document all OIDs used
- Provide testing instructions
- Include MIB files when possible
- Add security recommendations
- Create troubleshooting guides

## License

These configurations are provided as-is. Refer to the main project LICENSE file.

