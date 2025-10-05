# MiniDisplay
Node-RED flow and ESP32 sketch to control devices with one of them little OLED screens with a built-in rotary controller.

## Features

### Device Control
- Control lights (brightness, colour)
- Control media players (volume, source)
- Control computers (volume, mute, lock, power)
- Multi-entity switching with left button

### Weather Screensaver
After 30 seconds of inactivity, the display automatically switches to a weather screensaver showing:
- Current weather conditions with animated icons
- Temperature readings (indoor/outdoor)
- Automatic updates from Home Assistant

The screensaver exits immediately when any button is pressed or the rotary encoder is turned, returning to the normal controller interface.

## Hardware Requirements
- ESP32 board
- 128x64 OLED display (I2C, SSD1306)
- Rotary encoder with push button
- Additional control buttons (back, left)

## Configuration

### Using Configuration File (Recommended)
1. Copy `esp32/config_template.txt` to `esp32/config.txt` in your ESP32's SPIFFS storage
2. Update the values in `config.txt` with your specific settings:
   - WiFi credentials
   - MQTT server settings
   - Home Assistant IP and token
   - Weather and temperature sensor entities
   - Display and pin configuration
   - Idle timeout for screensaver

### Fallback Configuration
If no config file is found, the controller will use default values defined in `esp32/config.h`. You can modify these defaults if needed.

### Configuration Variables
- `WIFI_SSID` / `WIFI_PASSWORD` - WiFi credentials
- `MQTT_SERVER` / `MQTT_PORT` / `MQTT_USER` / `MQTT_PASSWORD` - MQTT settings
- `HA_IP` / `HA_PORT` / `HA_TOKEN` - Home Assistant connection
- `WEATHER_ENTITY` / `INDOOR_TEMP_ENTITY` / `OUTDOOR_TEMP_ENTITY` - Weather data sources
- `IDLE_TIMEOUT_SECONDS` - Screensaver activation delay (default: 30 seconds)
- Pin assignments and display configuration

## Dependencies
- WiFi
- PubSubClient
- Wire
- Adafruit_GFX
- Adafruit_SSD1306
- ESP_Knob
- ArduinoJson
- WeatherAnimations library (included)

## Installation
1. Install required Arduino libraries
2. Copy the WeatherAnimations library to your sketch folder
3. Create `config.txt` from the template and upload to ESP32 SPIFFS:
   - Copy `esp32/config_template.txt` to `esp32/config.txt`
   - Update values with your specific configuration
   - Upload to ESP32 SPIFFS using Arduino IDE or PlatformIO
4. Upload the sketch to your ESP32
5. Set up corresponding Node-RED flows (in `nodered/` directory)

### SPIFFS Upload
To upload the configuration file to ESP32 SPIFFS:
- **Arduino IDE**: Use the ESP32 Sketch Data Upload tool
- **PlatformIO**: Use `pio run --target uploadfs`
- Place `config.txt` in the `data/` folder before uploading
