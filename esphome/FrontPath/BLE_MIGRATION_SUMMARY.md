# FrontPath BLE Migration Summary

## What Changed

The FrontPath configuration has been reworked to support **Bluetooth Low Energy (BLE)** operation mode alongside the original UART mode.

### Before (UART Mode Only)
- ESP32 connected to sensors via UART (TX/RX pins)
- All detection logic ran on ESP32
- Complex adaptive baseline and gate calibration on-device
- Limited sensor visibility in Home Assistant
- 1000+ lines of sophisticated filtering code

### After (BLE Mode Available)
- ESP32 acts as Bluetooth proxy
- Sensors communicate directly with Home Assistant via BLE
- Detection logic runs in HA automations (flexible)
- Full sensor diagnostics visible in HA
- Simple 300-line ESP32 configuration
- **Original UART mode still available as backup**

## Files Overview

### Active Configuration
- **`FrontPath.yaml`** - BLE proxy mode (current/recommended)
  - Simple configuration
  - Bluetooth proxy active
  - Light sensor + LED
  - BLE connection monitoring

### Backup Configuration
- **`FrontPathUART.yaml`** - Original UART mode (backup)
  - Full copy of previous configuration
  - All adaptive baseline logic
  - Automatic gate calibration
  - On-device person detection

### Documentation
- **`QUICK_START_BLE.md`** - Get started in 10 minutes
- **`BLE_SETUP.md`** - Detailed BLE setup guide
- **`HA_AUTOMATIONS.md`** - Home Assistant automation examples
- **`MODE_COMPARISON.md`** - BLE vs UART feature comparison
- **`README.md`** - Updated with both modes explained

### Legacy Files (Still Valid)
- **`FrontPath_BLE_Config.yaml`** - Minimal config for sensor configuration via HLKRadarTool app
- **`BLE_CONFIG_MODE.md`** - Instructions for using HLKRadarTool
- **`FILTERING_CHANGES.md`** - History of UART mode filtering improvements
- **`LIGHTS_SETUP.md`** - Light automation setup (applies to both modes)

## Migration Path

### You're Already Migrated If:
- ✅ `FrontPath.yaml` is now the BLE proxy version
- ✅ TX/RX pins are disconnected from sensors
- ✅ Sensors are broadcasting BLE
- ✅ LD2410 integration added in Home Assistant

### To Complete Migration:
1. **Test BLE mode thoroughly** (1-2 weeks recommended)
2. **Create HA automations** (see `HA_AUTOMATIONS.md`)
3. **Tune detection thresholds** in HA
4. **Monitor for false triggers**

### To Revert to UART Mode:
If BLE doesn't work well:
1. Flash `FrontPathUART.yaml`
2. Reconnect TX/RX pins to sensors
3. Power cycle ESP32
4. Original functionality restored

## Sensor MAC Addresses

Documented in configuration:
- **Sensor 1**: `B8:BE:51:7D:71:44` (points towards house)
- **Sensor 2**: `14:AA:8C:58:66:02` (points away from house)

These are used for:
- BLE advertisement tracking
- Home Assistant integration
- Automation entity IDs

## Key Advantages of BLE Mode

1. **Flexibility**: Change detection logic without reflashing ESP32
2. **Visibility**: All sensor parameters visible in HA
3. **Simplicity**: Cleaner ESP32 code, easier to maintain
4. **Debugging**: Better diagnostics and logging in HA
5. **Experimentation**: Easy to test different detection strategies
6. **GPIO Freedom**: All pins available (except GPIO0 for light sensor)

## What You Lose (vs UART Mode)

1. **Autonomous Operation**: Requires HA to be running
2. **On-Device Logic**: No adaptive baseline on ESP32
3. **Auto Calibration**: No automatic gate threshold adjustments
4. **Position Tracking**: Must implement in HA if needed
5. **Instant Response**: Slight latency through WiFi/HA

## Recommended Next Steps

### Week 1: Basic Testing
- ✅ Verify sensors connect to HA
- ✅ Create simple motion automation
- ✅ Monitor for false triggers
- ✅ Tune darkness threshold

### Week 2: Advanced Setup
- ✅ Implement energy-based detection
- ✅ Add direction-based lighting
- ✅ Create adaptive baseline (optional)
- ✅ Fine-tune gate thresholds

### Week 3: Optimisation
- ✅ Adjust for weather conditions
- ✅ Optimise automation delays
- ✅ Add notification on sensor offline
- ✅ Document final configuration

### After 1 Month: Decision Point
- ✅ If BLE works well: Keep it, delete UART backup
- ✅ If issues persist: Revert to UART mode
- ✅ If mixed: Use BLE for testing, UART for production

## Support Resources

### Quick Help
- **Can't see sensors in HA?** → Check `BLE_SETUP.md` troubleshooting section
- **False triggers?** → See `HA_AUTOMATIONS.md` for tuning tips
- **Want UART back?** → Flash `FrontPathUART.yaml` and reconnect TX/RX
- **Need automation ideas?** → Browse `HA_AUTOMATIONS.md` examples

### Documentation Index
1. **Getting Started**: `QUICK_START_BLE.md`
2. **Detailed Setup**: `BLE_SETUP.md`
3. **Automations**: `HA_AUTOMATIONS.md`
4. **Comparison**: `MODE_COMPARISON.md`
5. **Main README**: `README.md`

## Testing Checklist

Before committing to BLE mode, verify:

- ✅ Both sensors reliably detected in HA
- ✅ Connection status sensors accurate
- ✅ Moving target detection works
- ✅ Light sensor functioning correctly
- ✅ Darkness detection triggers properly
- ✅ Automations respond to motion
- ✅ No excessive false triggers
- ✅ Acceptable latency for your use case
- ✅ Stable over 24+ hours
- ✅ Works in various weather conditions

## Rollback Plan

If BLE mode doesn't work:

1. **Immediate Rollback** (5 minutes):
   ```bash
   esphome run FrontPathUART.yaml
   ```
   - Reconnect TX/RX pins
   - Power cycle ESP32
   - Done!

2. **Clean Rollback** (10 minutes):
   - Remove LD2410 BLE integration from HA
   - Delete BLE automations
   - Flash UART config
   - Reconnect pins
   - Verify person detection sensor works

3. **Hybrid Approach**:
   - Keep BLE for diagnostics
   - Use UART for actual detection
   - Run both configs on different ESP32s

## Conclusion

The BLE migration provides a more flexible, maintainable approach to the FrontPath sensor system. The original UART configuration remains available as a proven fallback. Test thoroughly and choose the mode that works best for your environment.

**Current Status**: ✅ BLE mode active, UART backup available  
**Recommended**: Test BLE for 1-2 weeks before deciding  
**Fallback**: `FrontPathUART.yaml` ready if needed

