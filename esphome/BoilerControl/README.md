# Boiler Control - ESP32 Relay Board

## Hardware
- ESP32 SMD module
- Dual 5V relays
- AC power input (90-250V AC)
- No built-in USB programming port

## Programming the Board (Without USB Port)

Since this board doesn't have a USB port, you'll need an **FTDI or USB-to-TTL adapter** (3.3V logic level).

### Required Hardware
- FTDI/USB-to-TTL adapter (CP2102, CH340, FT232RL, etc.)
- Jumper wires (female-to-female recommended)

### Wiring Connection

Connect your FTDI adapter to the IO pins on the left side of the board:

| FTDI Adapter | ESP32 Board Pin |
|--------------|-----------------|
| GND          | GND             |
| 3.3V         | 3.3V            |
| TX           | RX              |
| RX           | TX              |

**IMPORTANT:** Cross the TX/RX lines! FTDI TX goes to ESP32 RX and vice versa.

### Entering Flash Mode

1. **Connect the FTDI adapter** as described above
2. **Hold down the "IO0" button** (labelled "100" or "Programmable Keys" - this is GPIO0 boot mode)
3. **Press the Reset key** briefly whilst still holding the IO0 button
4. **Release both buttons**
5. The ESP32 is now in flash mode

### First Time Setup

1. Make sure you have ESPHome installed:
   ```bash
   pip install esphome
   ```

2. Create/update your `secrets.yaml` file in the esphome directory with:
   ```yaml
   wifi_ssid: "YourWiFiSSID"
   wifi_password: "YourWiFiPassword"
   esphome_password: "YourOTAPassword"
   boiler_control_api_key: "generate_a_key_here"
   ```

3. Generate an API key:
   ```bash
   esphome wizard BoilerControl.yaml
   ```
   Or generate one manually and add it to secrets.yaml

### Upload Firmware

From the esphome/BoilerControl directory:

```bash
esphome run BoilerControl.yaml
```

Or from the main esphome directory:
```bash
esphome run BoilerControl/BoilerControl.yaml
```

Select your FTDI adapter's COM port when prompted.

### Subsequent Updates (OTA)

Once the initial flash is complete and the device is connected to WiFi, you can upload updates wirelessly:

```bash
esphome run BoilerControl.yaml
```

Then select the wireless option (boiler-control.local).

## GPIO Pin Configuration

**Note:** The relay GPIO pins (currently set to GPIO16 and GPIO17) may need adjustment based on your specific board variant. Common alternatives are:

- GPIO26, GPIO27
- GPIO16, GPIO17
- GPIO32, GPIO33
- GPIO21, GPIO22

### Finding the Correct GPIO Pins

If the relays don't respond:

1. Add this test code to your configuration:
   ```yaml
   interval:
     - interval: 5s
       then:
         - switch.toggle: relay_1
         - delay: 1s
         - switch.toggle: relay_2
   ```

2. Try different GPIO pin combinations until you hear the relays clicking

3. Update the pin numbers in the switch configuration

4. Remove the test interval once confirmed

## Safety Warnings

⚠️ **WARNING:** This device controls mains voltage (90-250V AC)!

- **NEVER** work on the relay connections whilst powered
- Ensure all wiring is done by a qualified electrician
- Use appropriate wire gauges for your load
- Follow local electrical codes and regulations
- Test with low-voltage loads first if possible
- The relays are rated for 10A maximum - do not exceed this

## Troubleshooting

### Can't Enter Flash Mode
- Ensure the FTDI adapter is 3.3V logic level (5V may damage the ESP32)
- Try holding the IO0 button for longer before pressing reset
- Check all wiring connections
- Try swapping TX/RX if not working

### Button Not Responding
- The button only works after firmware is loaded (not in flash mode)
- Check logs to see if button presses are detected
- The button has a 10ms debounce filter to prevent accidental triggers
- If still not working, try adding `inverted: false` instead of `inverted: true` to the button pin configuration

### No WiFi Connection
- Check your secrets.yaml credentials
- Connect to the fallback AP: "Boiler-Control-Fallback" (password: changeme123)
- Configure WiFi through the captive portal

### Relays Not Switching
- Verify GPIO pin numbers (see above)
- Check logs: `esphome logs BoilerControl.yaml`
- The relay may use inverted logic - try changing `inverted: false` to `inverted: true`

### Serial Monitor
To view logs during initial setup:
```bash
esphome logs BoilerControl.yaml
```

## Physical Button Control

The **IO0 button** (labelled "100" or "Programmable Keys") on the board now controls the relays:

1. **First press**: Relay 1 ON, Relay 2 OFF
2. **Second press**: Both relays ON
3. **Third press**: Both relays OFF
4. **Cycle repeats**

The onboard LED (GPIO2) lights up whenever either relay is on.

This allows you to control the relays without Home Assistant!

## Home Assistant Integration

Once running, the device should automatically appear in Home Assistant:

1. Go to Settings → Devices & Services
2. Look for the ESPHome integration
3. The "Boiler Control" device should appear with:
   - Boiler Relay 1 (switch)
   - Boiler Relay 2 (switch)
   - Restart button
   - Bluetooth Proxy
   - Diagnostic sensors

## Customisation

You can modify the relay names, icons, and behaviour in `BoilerControl.yaml`:

- Change `name:` for different display names in HA
- Change `icon:` for different icons (see [Material Design Icons](https://pictogrammers.com/library/mdi/))
- Modify `restore_mode:` behaviour:
  - `RESTORE_DEFAULT_OFF` - Always off on boot
  - `RESTORE_DEFAULT_ON` - Always on on boot
  - `ALWAYS_OFF` - Always off, ignore previous state
  - `ALWAYS_ON` - Always on, ignore previous state
