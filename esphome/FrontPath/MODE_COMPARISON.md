# FrontPath Operating Mode Comparison

## Quick Decision Guide

**Choose BLE Mode if:**
- ✅ You want simpler ESP32 code
- ✅ You prefer managing detection logic in Home Assistant
- ✅ You want full sensor diagnostics visible in HA
- ✅ You need flexible automation without reflashing
- ✅ You have good WiFi coverage for the ESP32
- ✅ You're comfortable with HA automations

**Choose UART Mode if:**
- ✅ You want autonomous on-device detection
- ✅ You prefer the ESP32 to handle all logic
- ✅ You need the adaptive baseline system on-device
- ✅ You want automatic gate calibration
- ✅ You have limited HA automation experience
- ✅ You prefer the "set and forget" approach

---

## Feature Comparison

| Feature | BLE Mode | UART Mode |
|---------|----------|-----------|
| **Wiring Complexity** | Simple (power only) | Complex (UART + power) |
| **ESP32 Code Size** | Small (~300 lines) | Large (~1000 lines) |
| **Detection Logic** | Home Assistant | ESP32 on-device |
| **Sensor Visibility** | Full HA integration | Limited (via ESPHome) |
| **Configuration Changes** | HA UI or automations | Reflash ESP32 |
| **Adaptive Baseline** | Optional (in HA) | Built-in (on ESP32) |
| **Gate Calibration** | Manual or HA automation | Automatic (every 20 min) |
| **Person Detection** | HA template sensors | On-device binary sensor |
| **Position Tracking** | HA calculations | On-device sensor |
| **GPIO Availability** | All free (except GPIO0) | GPIO20/21, 6/7 used |
| **Memory Usage** | Low | Higher (complex logic) |
| **Latency** | WiFi + HA processing | Instant (on-device) |
| **Debugging** | HA logs + ESPHome logs | ESPHome logs only |
| **Range Extension** | ESP32 is BLE proxy | N/A |

---

## Performance Comparison

### BLE Mode
**Pros:**
- Cleaner separation of concerns (ESP32 = proxy, HA = logic)
- Easy to tune thresholds without reflashing
- Full access to all sensor parameters in HA
- Can create complex multi-condition automations
- Better for experimentation and tuning
- Lower memory footprint on ESP32
- All GPIO pins available for expansion

**Cons:**
- Requires HA to be running for detection
- Slight latency (WiFi + HA processing)
- More HA automation configuration needed
- Depends on stable WiFi connection
- Need to learn HA automation syntax

### UART Mode
**Pros:**
- Autonomous operation (works even if HA is down)
- Instant on-device detection
- Sophisticated adaptive baseline built-in
- Automatic gate calibration
- Position tracking on-device
- Proven, tested detection logic
- "Set and forget" operation

**Cons:**
- Complex ESP32 code (harder to modify)
- Uses 4 GPIO pins for UART
- Higher memory usage
- Changes require reflashing
- Limited sensor visibility in HA
- More difficult to tune thresholds

---

## Sensor Data Available

### BLE Mode (via HA Integration)
From each LD2410 sensor:
- ✅ Has target (binary)
- ✅ Has moving target (binary)
- ✅ Has still target (binary)
- ✅ Moving distance (cm)
- ✅ Still distance (cm)
- ✅ Moving energy (0-100%)
- ✅ Still energy (0-100%)
- ✅ Detection distance (cm)
- ✅ All gate thresholds (configurable)
- ✅ Max distance gates (configurable)
- ✅ Timeout (configurable)

From ESP32:
- ✅ Light level (%)
- ✅ Light voltage (V)
- ✅ Path is dark (binary)
- ✅ Darkness threshold (configurable)
- ✅ BLE connection status per sensor
- ✅ WiFi signal strength

### UART Mode (via ESPHome)
From combined system:
- ✅ Path person detected (binary, adaptive)
- ✅ Path person position (metres)
- ✅ Sensor 1/2 moving target (binary)
- ✅ Sensor 1/2 presence (binary)
- ✅ Sensor 1/2 moving distance (cm)
- ✅ Sensor 1/2 moving energy (%)
- ✅ Sensor 1/2 moving energy RAW (%)
- ✅ Sensor 1/2 moving energy smoothed (%)
- ✅ Sensor 1/2 baseline (%)
- ✅ Detection activity score
- ✅ Light level (%)
- ✅ Path is dark (binary)
- ✅ All gate thresholds (configurable)
- ✅ Gate calibration controls
- ⚠️ Limited per-sensor visibility

---

## Migration Path

### From UART to BLE
1. Flash `FrontPath.yaml` (BLE mode)
2. Disconnect TX/RX pins from sensors (leave power connected)
3. Power cycle sensors (disconnect 5V for 10 seconds)
4. Add LD2410 BLE integration in Home Assistant
5. Create automations (see `HA_AUTOMATIONS.md`)
6. Test and tune

### From BLE to UART
1. Flash `FrontPathUART.yaml` (UART mode)
2. Connect TX/RX pins to sensors:
   - Sensor 1: TX→GPIO21, RX→GPIO20
   - Sensor 2: TX→GPIO7, RX→GPIO6
3. Power cycle ESP32
4. Remove LD2410 BLE integration from HA (optional)
5. Use on-device person detection sensor

---

## Recommended Approach

**Start with BLE Mode** for these reasons:
1. Easier to set up and test
2. More flexibility for tuning
3. Better visibility into what's happening
4. Can always fall back to UART if needed

**Switch to UART Mode if:**
- BLE connectivity is unreliable
- You prefer autonomous operation
- You want the proven adaptive baseline system
- You're happy with the default detection logic

Both configurations are fully functional and production-ready. The choice depends on your preferences and requirements.

