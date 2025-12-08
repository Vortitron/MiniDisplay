# FrontPath BLE Migration Checklist

Use this checklist to track your migration from UART to BLE mode.

## Pre-Migration

- [ ] Read `MODE_COMPARISON.md` to understand differences
- [ ] Backup current working configuration (already done: `FrontPathUART.yaml`)
- [ ] Note current detection thresholds and settings
- [ ] Document any custom automations using UART sensors
- [ ] Ensure Home Assistant is updated to latest version
- [ ] Verify ESPHome integration is working

## Hardware Preparation

- [ ] Identify sensor MAC addresses (documented: `B8:BE:51:7D:71:44` and `14:AA:8C:58:66:02`)
- [ ] Verify TEMT6000 light sensor is connected to GPIO0
- [ ] **Disconnect TX/RX pins from both LD2410 sensors**
- [ ] Verify sensors still have 5V power and GND connected
- [ ] Power cycle sensors (disconnect 5V for 10 seconds)

## ESP32 Configuration

- [ ] Flash `FrontPath.yaml` (BLE proxy mode)
- [ ] Verify ESP32 connects to WiFi
- [ ] Check ESPHome logs for "advertisements resumed" messages
- [ ] Confirm both sensors appear in BLE tracker logs
- [ ] Verify light sensor readings are working
- [ ] Check "Path Is Dark" binary sensor responds correctly

## Home Assistant Integration

- [ ] Go to Settings → Devices & Services
- [ ] Add LD2410 BLE integration
- [ ] Configure Sensor 1 (`B8:BE:51:7D:71:44`)
  - [ ] Rename to "FrontPath Sensor 1 (House Side)"
  - [ ] Verify all entities appear
  - [ ] Check moving target detection works
- [ ] Configure Sensor 2 (`14:AA:8C:58:66:02`)
  - [ ] Rename to "FrontPath Sensor 2 (Far Side)"
  - [ ] Verify all entities appear
  - [ ] Check moving target detection works
- [ ] Verify FrontPath device entities:
  - [ ] `binary_sensor.frontpath_path_is_dark`
  - [ ] `sensor.frontpath_light_level`
  - [ ] `binary_sensor.frontpath_ld2410_sensor_1_ble_connected`
  - [ ] `binary_sensor.frontpath_ld2410_sensor_2_ble_connected`

## Basic Automation Setup

- [ ] Create simple motion-activated automation (see `QUICK_START_BLE.md`)
- [ ] Test automation triggers on motion
- [ ] Test automation respects darkness condition
- [ ] Verify lights turn off after timeout
- [ ] Check for false triggers during calm weather

## Sensor Configuration

- [ ] Set Max Move Distance Gate to 6-8 for both sensors
- [ ] Set Max Still Distance Gate to 3-4 for both sensors
- [ ] Set Timeout to 3-5 seconds for both sensors
- [ ] Test detection range by walking the path
- [ ] Adjust gate thresholds if needed (higher = less sensitive)

## Testing Phase (Week 1)

- [ ] Day 1: Monitor for basic functionality
  - [ ] Motion detection working
  - [ ] No obvious false triggers
  - [ ] Light sensor working correctly
- [ ] Day 2-3: Monitor during different weather
  - [ ] Test in rain (if applicable)
  - [ ] Test in wind
  - [ ] Adjust thresholds if needed
- [ ] Day 4-5: Fine-tune automation
  - [ ] Adjust delays
  - [ ] Tune energy thresholds
  - [ ] Test edge cases
- [ ] Day 6-7: Stability check
  - [ ] Verify sensors stay connected
  - [ ] Check for any disconnections
  - [ ] Monitor WiFi signal strength

## Advanced Setup (Week 2)

- [ ] Implement energy-based detection (see `HA_AUTOMATIONS.md`)
- [ ] Add direction-based lighting (if desired)
- [ ] Create template sensor for combined detection
- [ ] Add sensor offline notifications
- [ ] Implement adaptive baseline (optional)
- [ ] Add distance-based progressive lighting (optional)

## Optimisation (Week 3)

- [ ] Review false trigger patterns
- [ ] Adjust thresholds based on observations
- [ ] Fine-tune automation delays
- [ ] Optimise for weather conditions
- [ ] Document final configuration
- [ ] Create input_number helpers for easy tuning

## Final Validation

- [ ] Test in various weather conditions
  - [ ] Clear/calm
  - [ ] Windy
  - [ ] Rainy
  - [ ] At dusk/dawn
- [ ] Verify no false triggers over 24 hours
- [ ] Check sensor connection stability
- [ ] Confirm acceptable latency
- [ ] Test all automations work as expected
- [ ] Verify light sensor accuracy

## Decision Point (After 1 Month)

### If BLE Works Well:
- [ ] Document final configuration
- [ ] Clean up any test automations
- [ ] Consider removing UART backup (or keep for safety)
- [ ] Share learnings in documentation

### If BLE Has Issues:
- [ ] Document specific problems encountered
- [ ] Attempt troubleshooting (see `BLE_SETUP.md`)
- [ ] Consider hybrid approach (BLE for diagnostics, UART for detection)
- [ ] Revert to UART if necessary (flash `FrontPathUART.yaml`)

## Rollback Procedure (If Needed)

- [ ] Flash `FrontPathUART.yaml`
- [ ] Reconnect TX/RX pins to sensors:
  - [ ] Sensor 1: TX→GPIO21, RX→GPIO20
  - [ ] Sensor 2: TX→GPIO7, RX→GPIO6
- [ ] Power cycle ESP32
- [ ] Remove LD2410 BLE integration from HA
- [ ] Delete BLE-based automations
- [ ] Verify UART person detection sensor works
- [ ] Restore any custom UART automations

## Documentation Updates

- [ ] Document final sensor settings
- [ ] Save working automation configurations
- [ ] Note any environment-specific tuning
- [ ] Update README with lessons learned
- [ ] Create notes for future reference

## Success Criteria

Mark migration as successful when:
- [ ] ✅ Both sensors reliably detected in HA for 7+ days
- [ ] ✅ False trigger rate acceptable (< 1 per day in calm weather)
- [ ] ✅ True detection rate good (> 95% of actual person passages)
- [ ] ✅ Latency acceptable for use case (< 2 seconds)
- [ ] ✅ No sensor disconnections over 7 days
- [ ] ✅ Light sensor working accurately
- [ ] ✅ Automations reliable and predictable
- [ ] ✅ Easy to tune and maintain

## Notes Section

Use this space to document observations, issues, and solutions:

```
Date: ___________
Weather: ___________
Observations:
- 
- 
- 

Issues Encountered:
- 
- 
- 

Solutions Applied:
- 
- 
- 

Threshold Settings:
- Max Move Distance Gate: ___
- Energy Threshold: ___
- Darkness Threshold: ___
- Automation Delays: ___

```

## Quick Reference

**Flash BLE Mode:**
```bash
esphome run FrontPath.yaml
```

**Flash UART Mode (Rollback):**
```bash
esphome run FrontPathUART.yaml
```

**View Logs:**
```bash
esphome logs FrontPath.yaml
```

**Entity ID Pattern:**
- Sensor 1: `ld2410_b8be517d7144_*`
- Sensor 2: `ld2410_14aa8c586602_*`
- FrontPath: `frontpath_*`

