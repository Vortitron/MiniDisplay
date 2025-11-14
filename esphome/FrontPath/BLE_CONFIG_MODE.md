# BLE Configuration Mode for FrontPath LD2410 Sensors

## Purpose

This temporary configuration disables the UART connection to the LD2410 sensors, allowing them to broadcast Bluetooth Low Energy (BLE) advertisements. This lets you configure them using the **HLKRadarTool** Android app.

## Why Use This?

- **Direct access to all sensor settings** via the official app
- **Visual feedback** while adjusting gates and sensitivity
- **Real-time testing** - see detection zones as you configure
- **Persistent settings** - configuration is saved to the sensor's internal memory

## Step-by-Step Instructions

### 1. Flash BLE Configuration Mode

```bash
# From the esphome directory
esphome run FrontPath_BLE_Config.yaml
```

Or use the ESPHome dashboard in Home Assistant to flash `FrontPath_BLE_Config.yaml`.

**Important:** The LD2410 sensors remain powered by the ESP32 (via 5V pins), but the UART communication is disabled. This allows them to broadcast BLE.

### 2. Install HLKRadarTool App

- **Android only** (no iOS version available)
- Download from Google Play Store: Search "HLKRadarTool" or "HiLink Radar"
- Alternative: Download APK from HiLink's website

### 3. Connect to Sensors via BLE

1. Open HLKRadarTool app
2. Tap "Scan" or "Search Device"
3. You should see two LD2410 sensors appear (they'll have MAC addresses like `B8:BE:51:XX:XX:XX`)
4. Tap one sensor to connect

**Tip:** If sensors don't appear:
- Make sure you're within ~5m of the sensors
- Check that FrontPath device shows "BLE Configuration Mode" in Home Assistant
- Try restarting the ESP32 (power cycle or reboot button in HA)

### 4. Configure Sensor Settings

Once connected, you'll see the sensor's current configuration:

#### Basic Settings (Recommended for 12m Path)

**Max Move Distance Gate:**
- Set to **6-8** (covers ~4.5-6m range from each sensor)
- Each gate = ~0.75m
- Gate 6 = 4.5m, Gate 7 = 5.25m, Gate 8 = 6m

**Max Still Distance Gate:**
- Set to **3-4** (~2-3m range)
- Still targets are unreliable outdoors, keep this short

**Timeout:**
- Set to **3-5 seconds**
- How long sensor stays "triggered" after target leaves
- Shorter = lights turn off faster (but might flicker)
- Longer = smoother operation (but false triggers last longer)

#### Per-Gate Sensitivity (Advanced - Optional)

The app shows a grid of sensitivity values for each gate (0-8):

**Motion Sensitivity:**
- Range: 0-100
- **Higher = less sensitive** (needs stronger signal)
- **Lower = more sensitive** (triggers on weaker signals)
- Default is usually 50

**When to Adjust:**
- If a specific distance range gets false triggers (bush, fence, etc.)
- Increase that gate's sensitivity threshold
- Example: Gate 3 (2.25-3m) has a bush → increase gate 3 from 50 to 75

**Still Sensitivity:**
- Usually leave at default or increase (less sensitive)
- Still targets don't work well outdoors anyway

### 5. Test Your Settings

The app shows real-time detection:
- Walk the path and watch the gates light up
- Adjust sensitivity if needed
- Check that detection range covers the path properly

### 6. Save Settings

**IMPORTANT:** Tap "Save" or "Write Config" in the app!

The settings are stored in the LD2410's **non-volatile memory** - they persist even after power loss or reflashing the ESP32.

### 7. Configure Second Sensor

Disconnect from the first sensor and repeat steps 3-6 for the second sensor.

**Tip:** You can use different settings for each sensor if needed (e.g., if one side has more foliage).

### 8. Restore Full Configuration

Once both sensors are configured, flash the full configuration:

```bash
# From the esphome directory
esphome run FrontPath.yaml
```

Or use the ESPHome dashboard to flash `FrontPath.yaml`.

The ESP32 will reconnect via UART and your custom settings will be preserved!

## Verification

After flashing the full config:

1. Check Home Assistant for the FrontPath device
2. Look at the gate controls:
   - "Sensor 1/2 Max Move Distance Gate" should show your configured values
   - "Sensor 1/2 Timeout" should match what you set
3. Walk the path and verify detection works as expected

## Troubleshooting

### Sensors Don't Appear in App

**Check ESP32 is in BLE mode:**
- Home Assistant → FrontPath device → "FrontPath Mode" should say "BLE Configuration Mode"

**Check Bluetooth on phone:**
- Enable Bluetooth
- Grant location permissions (required for BLE scanning on Android)

**Try power cycling:**
- Unplug ESP32, wait 5 seconds, plug back in
- Wait 30 seconds for boot, then scan again

### Can't Connect to Sensor

**Another device might be connected:**
- Close any other instances of HLKRadarTool
- Restart the app
- Power cycle the ESP32

**Sensor might be in a weird state:**
- Power cycle the ESP32
- Try connecting immediately after boot (within first 30 seconds)

### Settings Don't Save

**Make sure you tapped "Save" or "Write Config":**
- Look for a confirmation message in the app
- Some versions have "Write" button instead of "Save"

**Try disconnecting and reconnecting:**
- If settings revert, they weren't saved properly
- Connect again and re-save

### Sensors Work in BLE Mode but Not After Reflashing

**UART wiring issue:**
- Check TX/RX connections (TX → RX, RX → TX)
- Verify baud rate is 256000 in FrontPath.yaml

**Sensor firmware issue:**
- Some LD2410 firmware versions have bugs
- Try updating firmware via the app (if available)

## Notes

- **Settings persist across flashes** - you only need to do this once (unless you want to change settings)
- **BLE range is limited** - stay within ~5m of the sensors while configuring
- **No iOS support** - HLKRadarTool is Android-only
- **Bluetooth Proxy still works** - the ESP32 will proxy other BLE devices to Home Assistant while in this mode

## When to Use BLE Config Mode Again

- Adjusting detection range (max gates)
- Fine-tuning per-gate sensitivity after observing false triggers
- Testing different timeout values
- Resetting to factory defaults (if needed)

## Reverting to Normal Operation

Simply flash `FrontPath.yaml` again - no special steps needed. The UART connection will be restored and the ESP32 will communicate with the sensors normally.

