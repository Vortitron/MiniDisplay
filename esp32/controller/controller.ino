#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP_Knob.h>
#include <ArduinoJson.h>

// Include configuration and environment loader
#include "config.h"

// Include WeatherAnimations library for screensaver
#include "WeatherAnimations/src/WeatherAnimations.h"
#include "WeatherAnimations/src/WeatherAnimations.cpp"
#include "WeatherAnimations/src/WeatherAnimationsAnimations.h"
#include "WeatherAnimations/src/WeatherAnimationsAnimations.cpp"
#include "WeatherAnimations/src/WeatherAnimationsIcons.h"
#include "WeatherAnimations/src/WeatherAnimationsIcons.cpp"

// OLED settings
#define OLED_RESET -1
Adafruit_SSD1306 display(Config::getScreenWidth(), Config::getScreenHeight(), &Wire, OLED_RESET);

// Create WeatherAnimations instance for screensaver (will be initialised in setup)
WeatherAnimationsLib::WeatherAnimations* weatherAnim = nullptr;

// Screensaver settings
unsigned long lastUserActivityTime = 0;
bool isDisplayingWeatherScreensaver = false;

// Entity definitions
struct Entity {
	const char* entityId;
	const char* friendlyName;
	const char* domain; // "light", "media_player", or "computer"
};

const Entity entities[] = {
	{"light.gold_light", "Gold Light", "light"},
	{"light.led_flood_light", "Living Room Flood", "light"},
	{"light.bio_floodlight", "Bio Floodlight", "light"},
	{"media_player.lgnano_55", "LG Nano 55", "media_player"},
  {"media_player.lgnano_55", "LG Nano 55", "media_player"},
	{"computer.FelixLaptop", "Felix Laptop", "computer"},
	{"climate.sam", "Sam HVAC", "climate"}
};
const int numEntities = sizeof(entities) / sizeof(entities[0]);
int currentEntityIndex = 0;

// MQTT topics
struct MqttTopics {
	String command;
	String requestState;
	String brightness;
	String hs;
	String color_temp;
	String volume;
	String source;
	String update;
	String mute;      // For computer
	String lock;      // For computer
	String enforceLock; // For computer enforce lock toggle
	String setpoint;  // For climate temperature setpoint
};

MqttTopics topics;

void updateTopics() {
	const Entity& entity = entities[currentEntityIndex];
	String baseTopic = String("homeassistant/") + entity.domain + "/" + entity.entityId + "/";
	topics.command = baseTopic + "set";
	topics.requestState = baseTopic + "request_state";
	topics.update = baseTopic + "update";

	// Domain-specific topics
	if (strcmp(entity.domain, "light") == 0) {
		topics.brightness = baseTopic + "brightness";
		topics.hs = baseTopic + "hs";
		topics.color_temp = baseTopic + "color_temp";
		topics.volume = "";
		topics.source = "";
		topics.mute = "";
		topics.lock = "";
		topics.setpoint = "";
	} else if (strcmp(entity.domain, "media_player") == 0) {
		topics.volume = baseTopic + "volume";
		topics.source = baseTopic + "source";
		topics.brightness = "";
		topics.hs = "";
		topics.color_temp = "";
		topics.mute = "";
		topics.lock = "";
		topics.setpoint = "";
	} else if (strcmp(entity.domain, "climate") == 0) {
		// Climate control for HVAC
		topics.setpoint = "homeassistant/number/sam/setpoint/command";
		topics.update = "homeassistant/sensor/sam/temperature/state"; // Temperature updates
		topics.requestState = "homeassistant/climate/sam/state"; // Climate state requests
		topics.brightness = "";
		topics.hs = "";
		topics.color_temp = "";
		topics.volume = "";
		topics.source = "";
		topics.mute = "";
		topics.lock = "";
	} else if (strcmp(entity.domain, "computer") == 0) {
		// Extract computer name from entity.entityId (format is "computer.computername")
		String computerName = String(entity.entityId).substring(String(entity.entityId).indexOf(".") + 1);
		computerName.toLowerCase();
		
		// Use the computer domain for commands
		String computerBaseTopic = "homeassistant/computer/" + computerName + "/";
		topics.command = computerBaseTopic + "power/set";          // For ON/OFF
		topics.volume = computerBaseTopic + "volume/action";       // For setting volume value
		topics.mute = computerBaseTopic + "mute/press";          // For toggling mute
		topics.lock = computerBaseTopic + "lock/press";          // For locking
		topics.enforceLock = computerBaseTopic + "enforce_lock/set"; // For toggling enforce lock

		// State topics remain the same (using sensor/switch domains for HA entities)
		topics.requestState = "homeassistant/sensor/" + computerName + "/" + computerName + "_sessionstate/state"; // Or a more generic request?
		topics.update = "homeassistant/sensor/" + computerName + "/" + computerName + "_sessionstate/state"; // Or a more generic update?
		
		topics.brightness = "";
		topics.hs = "";
		topics.color_temp = "";
		topics.source = "";
		topics.setpoint = "";
	}
	Serial.print("Updated topics for entity: ");
	Serial.print(entity.entityId);
	Serial.print(", domain: ");
	Serial.println(entity.domain);
	Serial.print("Command topic: ");
	Serial.println(topics.command);
	Serial.print("Volume topic: ");
	Serial.println(topics.volume);
	Serial.print("Update topic: ");
	Serial.println(topics.update);
	if (strcmp(entity.domain, "light") == 0) {
		Serial.print("Color temp topic: ");
		Serial.println(topics.color_temp);
	}
}

// Pin definitions - will be loaded from config
int onboardLedPin;
int 
;
int buttonLedPin;
int encoderTRA;
int encoderTRB;
int encoderPUSH;
int backButton;
int leftButton;

// MQTT client
WiFiClient espClient;
PubSubClient client(espClient);

// Encoder
ESP_Knob *knob;

// Light colors (HS format: {hue, saturation})
// Color temperatures (mireds): 153-500 (6500K-2000K)
const float colors[][3] = {
	{0, 100, 0},      // Red
	{120, 100, 0},    // Green
	{240, 100, 0},    // Blue
	{60, 100, 0},     // Yellow
	{300, 100, 0},    // Magenta
	{180, 100, 0},    // Cyan
	{0, 0, 0},        // White (pure white - no color temp)
	{0, 0, 270},      // Warm White (270 mireds ≈ 3700K)
	{0, 0, 200},      // Cool White (200 mireds ≈ 5000K)
	{0, 0, 153},      // Daylight (153 mireds ≈ 6500K)
};
const char* colorNames[] = {
	"Red", "Green", "Blue", "Yellow", "Magenta", "Cyan", "White", "WarmWhite", "CoolWhite", "Daylight"
};
const int numColors = sizeof(colors) / sizeof(colors[0]);

// TV sources
const char* tvSources[] = {
	"Disney+", "Jellyfin", "Max", "Netflix", "Prime Video", "Roku",
	"SVT Play", "TV4 Play", "Telia Play", "YouTube", "HDMI 3"
};
const int numTvSources = sizeof(tvSources) / sizeof(tvSources[0]);
int currentTvSourceIndex = 0;
int currentTvTargetSourceIndex = -1;

// Entity states
bool entityStates[numEntities] = {false};
int displayBrightness[numEntities] = {128}; // For lights
int targetBrightness[numEntities] = {128};  // For lights
int colorIndices[numEntities] = {0};        // For lights
int colorTempValues[numEntities] = {270};   // For lights (mireds, 270 ≈ 3700K warm white)
int targetColorTempValues[numEntities] = {270}; // For lights
bool stateReceived[numEntities] = {false};
String pcActiveWindow = "";                 // For computer active window
String pcSessionState = "unknown";          // For computer lock state (locked/unlocked)

// Climate/HVAC states
float currentTemperature = 20.0;            // Current room temperature
float currentHumidity = 50.0;               // Current humidity
float targetTemperature = 20.0;             // Target temperature setpoint
float displayTemperature = 20.0;            // Display temperature setpoint
const float MIN_TEMP = 15.0;                // Minimum temperature
const float MAX_TEMP = 27.0;                // Maximum temperature
const float TEMP_STEP = 0.5;                // Temperature adjustment step
String hvacMode = "off";                    // HVAC mode (off, heat, cool, auto)
String hvacAction = "idle";                 // Current HVAC action

// Variables
bool connected = false;
unsigned long lastRequestTime = 0;
const unsigned long requestInterval = 5000;
unsigned long lastKnobActivity = 0;
const unsigned long knobIdleTimeout = 100;
bool lastButtonState = LOW;
bool lastPushButtonState = HIGH;
bool lastBackButtonState = HIGH;
bool lastLeftButtonState = HIGH;
bool oledAttached = false;
unsigned long lastOledCheck = 0;
const unsigned long oledCheckInterval = 1000;

// Debouncing for rotary encoder
int lastCount = 0;
int directionCounter = 0;
const int directionThreshold = 2;
bool lastDirection = true;

// Weather screensaver functions
void showWeatherScreensaver() {
	if (!isDisplayingWeatherScreensaver && oledAttached && weatherAnim != nullptr) {
		Serial.println("Starting weather screensaver");
		isDisplayingWeatherScreensaver = true;
		
		// Set to continuous weather mode with embedded animations
		weatherAnim->setMode(CONTINUOUS_WEATHER);
		weatherAnim->setAnimationMode(ANIMATION_EMBEDDED);
		
		// Display the animation - update() will fetch weather data automatically
		weatherAnim->update();
	}
}

void hideWeatherScreensaver() {
	if (isDisplayingWeatherScreensaver) {
		Serial.println("Exiting weather screensaver, returning to controller");
		isDisplayingWeatherScreensaver = false;
		
		// Return to normal controller display
		updateDisplay();
	}
}

void updateUserActivity() {
	lastUserActivityTime = millis();
	
	// If we were in screensaver mode, exit it
	if (isDisplayingWeatherScreensaver) {
		hideWeatherScreensaver();
	}
}

// Check if OLED is attached
bool checkOledAttached() {
  Wire.beginTransmission(Config::getOLEDI2CAddress());
  bool attached = Wire.endTransmission() == 0;
  if(!attached){
    Serial.print("Checking OLED attachment: ");
    Serial.println(attached ? "Attached" : "Not attached");
  }
  return attached;
}

// Encoder callbacks
void onKnobLeftEventCallback(int count, void *usr_data) {
  if (!oledAttached) {
    Serial.println("Knob left event ignored: OLED not attached");
    return;
  }

  // Update user activity (exits screensaver if active)
  updateUserActivity();

  const Entity& entity = entities[currentEntityIndex];
  // For computer, allow volume adjustment if unlocked, regardless of entityStates
  bool canAdjust = (strcmp(entity.domain, "computer") == 0 && pcSessionState == "unlocked") || 
                   (strcmp(entity.domain, "computer") != 0 && entityStates[currentEntityIndex]);
  if (!canAdjust) {
    Serial.print("Knob left event ignored for ");
    Serial.print(entity.entityId);
    Serial.print(": computer locked or entity state is off (");
    Serial.print(entityStates[currentEntityIndex] ? "on" : "off");
    Serial.println(")");
    return;
  }

	if (lastDirection && count < lastCount) {
		directionCounter = 0;
		lastDirection = false;
		Serial.println("Knob direction changed to left");
	}

	directionCounter--;
	lastCount = count;

	if (directionCounter <= -directionThreshold) {
		if (strcmp(entity.domain, "light") == 0) {
			// For color temperature colors (indices 7-9), adjust color temperature
			if (colorIndices[currentEntityIndex] >= 7 && colorIndices[currentEntityIndex] <= 9) {
				targetColorTempValues[currentEntityIndex] = max(153, targetColorTempValues[currentEntityIndex] - 10);
				Serial.printf("Knob left, color temperature for %s: %d mireds\n", entity.entityId, targetColorTempValues[currentEntityIndex]);
			} else {
			targetBrightness[currentEntityIndex] = max(0, targetBrightness[currentEntityIndex] - 5);
			Serial.printf("Knob left, brightness for %s: %d\n", entity.entityId, targetBrightness[currentEntityIndex]);
			}
		} else if (strcmp(entity.domain, "climate") == 0) {
			targetTemperature = max(MIN_TEMP, targetTemperature - TEMP_STEP);
			Serial.printf("Knob left, temperature setpoint for %s: %.1f°C\n", entity.entityId, targetTemperature);
		} else {
			targetVolumeLevels[currentEntityIndex] = max(0, targetVolumeLevels[currentEntityIndex] - 2);
			Serial.printf("Knob left, volume for %s: %d\n", entity.entityId, targetVolumeLevels[currentEntityIndex]);
		}
		lastKnobActivity = millis();
		updateDisplay();
		directionCounter = 0;
	}
}

void onKnobRightEventCallback(int count, void *usr_data) {
  if (!oledAttached) {
    Serial.println("Knob right event ignored: OLED not attached");
    return;
  }

  // Update user activity (exits screensaver if active)
  updateUserActivity();

  const Entity& entity = entities[currentEntityIndex];
  // For computer, allow volume adjustment if unlocked, regardless of entityStates
  bool canAdjust = (strcmp(entity.domain, "computer") == 0 && pcSessionState == "unlocked") || 
                   (strcmp(entity.domain, "computer") != 0 && entityStates[currentEntityIndex]);
  if (!canAdjust) {
    Serial.print("Knob right event ignored for ");
    Serial.print(entity.entityId);
    Serial.print(": computer locked or entity state is off (");
    Serial.print(entityStates[currentEntityIndex] ? "on" : "off");
    Serial.println(")");
    return;
  }

	if (!lastDirection && count > lastCount) {
		directionCounter = 0;
		lastDirection = true;
		Serial.println("Knob direction changed to right");
	}

	directionCounter++;
	lastCount = count;

	if (directionCounter >= directionThreshold) {
		if (strcmp(entity.domain, "light") == 0) {
			// For color temperature colors (indices 7-9), adjust color temperature
			if (colorIndices[currentEntityIndex] >= 7 && colorIndices[currentEntityIndex] <= 9) {
				targetColorTempValues[currentEntityIndex] = min(500, targetColorTempValues[currentEntityIndex] + 10);
				Serial.printf("Knob right, color temperature for %s: %d mireds\n", entity.entityId, targetColorTempValues[currentEntityIndex]);
			} else {
			targetBrightness[currentEntityIndex] = min(255, targetBrightness[currentEntityIndex] + 5);
			Serial.printf("Knob right, brightness for %s: %d\n", entity.entityId, targetBrightness[currentEntityIndex]);
			}
		} else if (strcmp(entity.domain, "climate") == 0) {
			targetTemperature = min(MAX_TEMP, targetTemperature + TEMP_STEP);
			Serial.printf("Knob right, temperature setpoint for %s: %.1f°C\n", entity.entityId, targetTemperature);
		} else {
			targetVolumeLevels[currentEntityIndex] = min(100, targetVolumeLevels[currentEntityIndex] + 2);
			Serial.printf("Knob right, volume for %s: %d\n", entity.entityId, targetVolumeLevels[currentEntityIndex]);
		}
		lastKnobActivity = millis();
		updateDisplay();
		directionCounter = 0;
	}
}

void onKnobZeroEventCallback(int count, void *usr_data) {
  if (!oledAttached) {
    Serial.println("Knob zero event ignored: OLED not attached");
    return;
  }
  
  // Update user activity (exits screensaver if active)
  updateUserActivity();
  
  directionCounter = 0;
  lastCount = 0;
  lastDirection = true;
  Serial.println("Knob zero event, resetting direction");
}

void setup() {
  Serial.begin(115200);
  Serial.println("Starting setup...");
  delay(1000);
  
  // Load configuration from SPIFFS
  Serial.println("Loading configuration...");
  EnvLoader::loadEnv("/config.txt");
  
  // Load pin configuration
  onboardLedPin = Config::getOnboardLEDPin();
  buttonPin = Config::getButtonPin();
  buttonLedPin = Config::getButtonLEDPin();
  encoderTRA = Config::getEncoderTRAPin();
  encoderTRB = Config::getEncoderTRBPin();
  encoderPUSH = Config::getEncoderPushPin();
  backButton = Config::getBackButtonPin();
  leftButton = Config::getLeftButtonPin();
  
  // Configure pins
  pinMode(onboardLedPin, OUTPUT);
  pinMode(buttonPin, INPUT_PULLDOWN);
  pinMode(buttonLedPin, OUTPUT);
  pinMode(backButton, INPUT_PULLUP);
  pinMode(leftButton, INPUT_PULLUP);
  pinMode(encoderPUSH, INPUT_PULLUP);

  digitalWrite(onboardLedPin, HIGH);
  digitalWrite(buttonLedPin, entityStates[currentEntityIndex]);

  Serial.println("Pin configuration loaded and set");

	Wire.begin();
	Serial.println("I2C bus initialized");

	  oledAttached = checkOledAttached();
  if (oledAttached && !display.begin(SSD1306_SWITCHCAPVCC, Config::getOLEDI2CAddress())) {
    Serial.println("OLED detected but failed to initialize!");
    oledAttached = false;
  } else if (oledAttached) {
    Serial.println("OLED successfully initialized");
  }

	if (oledAttached) {
		display.clearDisplay();
		display.setTextSize(1);
		display.setTextColor(SSD1306_WHITE);
		display.setCursor(0, 0);
		display.println(F("Connecting..."));
		display.display();
		Serial.println("OLED display set to 'Connecting...'");
	}

	knob = new ESP_Knob(encoderTRA, encoderTRB);
	knob->begin();
	knob->attachLeftEventCallback(onKnobLeftEventCallback);
	knob->attachRightEventCallback(onKnobRightEventCallback);
	knob->attachZeroEventCallback(onKnobZeroEventCallback);
	Serial.println("Rotary encoder initialized and callbacks attached");
	  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(Config::getWiFiSSID());
  WiFi.begin(Config::getWiFiSSID(), Config::getWiFiPassword());
	int attempts = 0;
	while (WiFi.status() != WL_CONNECTED && attempts < 30) {
		delay(500);
		Serial.print("WiFi attempt ");
		Serial.print(attempts + 1);
		Serial.print(": Status = ");
		Serial.println(WiFi.status());
		attempts++;
	}

	if (WiFi.status() != WL_CONNECTED) {
		Serial.println("Failed to connect to Wi-Fi");
		if (oledAttached) {
			display.clearDisplay();
			display.setCursor(0, 0);
			display.println(F("Wi-Fi Failed"));
			display.display();
			Serial.println("OLED display set to 'Wi-Fi Failed'");
		}
		return;
	}

	Serial.println("Connected to Wi-Fi");
	Serial.print("IP: ");
	Serial.println(WiFi.localIP());
	Serial.print("RSSI: ");
	Serial.println(WiFi.RSSI());

	  client.setServer(Config::getMQTTServer(), Config::getMQTTPort());
  client.setCallback(callback);
  Serial.print("Connecting to MQTT server: ");
  Serial.println(Config::getMQTTServer());
  reconnect();

	  updateTopics();
  
  // Initialise weather animations for screensaver
  if (oledAttached) {
    Serial.println("Initialising weather animations library...");
    weatherAnim = new WeatherAnimationsLib::WeatherAnimations(
      Config::getWiFiSSID(), 
      Config::getWiFiPassword(), 
      Config::getHAIP(), 
      Config::getHAToken()
    );
    weatherAnim->begin(OLED_SSD1306, Config::getOLEDI2CAddress(), false); // Don't manage WiFi - we already have it
    weatherAnim->setWeatherEntity(Config::getWeatherEntity());
    weatherAnim->setTemperatureEntities(Config::getIndoorTempEntity(), Config::getOutdoorTempEntity());
    weatherAnim->setAnimationMode(ANIMATION_EMBEDDED);
    
    if (strcmp(entities[currentEntityIndex].domain, "light") == 0) {
      publishColor();
    }
    updateDisplay();
    Serial.println("Initial display update completed");
  }
  
  // Initialise user activity tracking
  lastUserActivityTime = millis();
  isDisplayingWeatherScreensaver = false;
}

void loop() {
	unsigned long now = millis();
	if (now - lastOledCheck >= oledCheckInterval) {
		bool newOledState = checkOledAttached();
		if (newOledState != oledAttached) {
			oledAttached = newOledState;
			        if (oledAttached && display.begin(SSD1306_SWITCHCAPVCC, Config::getOLEDI2CAddress())) {
				Serial.println("OLED reattached and initialized!");
				updateDisplay();
				reconnect();
			} else if (!oledAttached) {
				Serial.println("OLED detached! Unsubscribing from topics...");
				for (int i = 0; i < numEntities; i++) {
					String subUpdateTopic = String("homeassistant/") + entities[i].domain + "/" + entities[i].entityId + "/update";
					client.unsubscribe(subUpdateTopic.c_str());
					Serial.print("Unsubscribed from: ");
					Serial.println(subUpdateTopic);
				}
			}
		}
		lastOledCheck = now;
	}

	  if (!oledAttached) {
    Serial.println("Loop skipped: OLED not attached");
    delay(100);
    return;
  }
  
  // Check for idle timeout and show weather screensaver
  if (!isDisplayingWeatherScreensaver && (now - lastUserActivityTime >= Config::getIdleTimeoutMS())) {
    showWeatherScreensaver();
  }
  
  // If in screensaver mode, update the animation and skip controller logic
  if (isDisplayingWeatherScreensaver && weatherAnim != nullptr) {
    weatherAnim->update();
    delay(50); // Reduce update frequency for animations
    return;
  }

	bool isConnected = (WiFi.status() == WL_CONNECTED) && client.connected();
	if (isConnected != connected) {
		connected = isConnected;
		digitalWrite(onboardLedPin, !connected);
		Serial.print("Connection status changed: ");
		Serial.println(connected ? "Connected (Wi-Fi and MQTT)" : "Disconnected (Wi-Fi or MQTT)");
		for (int i = 0; i < numEntities; i++) {
			if (connected && !stateReceived[i]) {
				stateReceived[i] = false;
				lastRequestTime = 0;
				Serial.print("Reset state received for entity ");
				Serial.print(entities[i].entityId);
				Serial.println(" due to connection change");
			}
		}
		updateDisplay();
	}

	if (!connected) {
		Serial.println("Attempting to reconnect...");
		delay(5000);
		reconnect();
	}

	client.loop();

	if (connected && !stateReceived[currentEntityIndex]) {
		if (now - lastRequestTime >= requestInterval) {
			Serial.print("Requesting state for ");
			Serial.print(entities[currentEntityIndex].entityId);
			Serial.print(" on topic: ");
			Serial.println(topics.requestState);
			client.publish(topics.requestState.c_str(), "REQUEST");
			lastRequestTime = now;
		}
	}

	if (lastKnobActivity > 0 && millis() - lastKnobActivity >= knobIdleTimeout) {
		const Entity& entity = entities[currentEntityIndex];
		if (strcmp(entity.domain, "light") == 0) {
			bool changed = false;
			if (targetBrightness[currentEntityIndex] != displayBrightness[currentEntityIndex]) {
				Serial.print("Brightness changed for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.print(displayBrightness[currentEntityIndex]);
				Serial.print(" -> ");
				Serial.println(targetBrightness[currentEntityIndex]);
				publishBrightness();
				displayBrightness[currentEntityIndex] = targetBrightness[currentEntityIndex];
				changed = true;
			}
			if (targetColorTempValues[currentEntityIndex] != colorTempValues[currentEntityIndex]) {
				Serial.print("Color temperature changed for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.print(colorTempValues[currentEntityIndex]);
				Serial.print(" -> ");
				Serial.println(targetColorTempValues[currentEntityIndex]);
				publishColorTemp();
				colorTempValues[currentEntityIndex] = targetColorTempValues[currentEntityIndex];
				changed = true;
			}
		} else if (strcmp(entity.domain, "climate") == 0) {
			if (abs(targetTemperature - displayTemperature) >= 0.1) {
				Serial.print("Temperature setpoint changed for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.print(displayTemperature);
				Serial.print("°C -> ");
				Serial.print(targetTemperature);
				Serial.println("°C");
				publishTemperatureSetpoint();
				displayTemperature = targetTemperature;
			}
		} else {
			if (targetVolumeLevels[currentEntityIndex] != volumeLevels[currentEntityIndex]) {
				Serial.print("Volume changed for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.print(volumeLevels[currentEntityIndex]);
				Serial.print(" -> ");
				Serial.println(targetVolumeLevels[currentEntityIndex]);
				publishVolume();
				volumeLevels[currentEntityIndex] = targetVolumeLevels[currentEntityIndex];
			}
		}
		lastKnobActivity = 0;
		Serial.println("Knob activity timeout, changes published");
	}

	  // Button and encoder push handling
  bool currentButtonState = digitalRead(buttonPin);
  bool currentPushButtonState = digitalRead(encoderPUSH);
  bool currentBackButtonState = digitalRead(backButton);
  bool currentLeftButtonState = digitalRead(leftButton);
  
  // Check for any button press and update user activity
  if (currentButtonState != lastButtonState || 
      currentPushButtonState != lastPushButtonState ||
      currentBackButtonState != lastBackButtonState ||
      currentLeftButtonState != lastLeftButtonState) {
    updateUserActivity();
  }

	const Entity& entity = entities[currentEntityIndex];
	if (strcmp(entity.domain, "computer") == 0) {
		// Computer-specific controls
		if (currentPushButtonState != lastPushButtonState && currentPushButtonState == LOW) {
			// Rotary push: toggle mute or turn on if computer is off
			if (!entityStates[currentEntityIndex]) {
				// Computer is off, turn it on
				Serial.print("Computer is off, turning on via ");
				Serial.println(topics.command);
				client.publish(topics.command.c_str(), "ON");
			} else {
				// Computer is on, toggle mute
				Serial.print("Dial push detected, publishing mute command");
				toggleComputerMute();
			}
			delay(50);
		}

		if (currentBackButtonState != lastBackButtonState && currentBackButtonState == LOW) {
			// Back button: toggle enforce_lock
			Serial.print("Back button press detected, toggling enforce lock");
			bool currentEnforceLockState = (pcSessionState == "locked");
			toggleComputerEnforceLock(!currentEnforceLockState);
			delay(50);
		}

		// Back + rotary push: power off
		if (currentBackButtonState == LOW && currentPushButtonState == LOW) {
			// Button + dial push: power off
			Serial.print("Back button + dial push detected, publishing power off command to ");
			Serial.println(topics.command);
			client.publish(topics.command.c_str(), "OFF");
			delay(50);
		}
		
		// Additional control: if the left button and back button are pressed together, lock the computer
		if (currentLeftButtonState == LOW && currentBackButtonState == LOW) {
			Serial.println("Left button + back button detected, locking computer");
			toggleComputerLock();
			delay(50);
		}
	} else {
		// Existing controls for lights and TV
		if (currentButtonState != lastButtonState) {
					if (currentButtonState == HIGH) {
			if (strcmp(entity.domain, "light") == 0) {
				// For color temperature colors (indices 7-9), adjust color temperature
				if (colorIndices[currentEntityIndex] >= 7 && colorIndices[currentEntityIndex] <= 9) {
					targetColorTempValues[currentEntityIndex] = min(500, targetColorTempValues[currentEntityIndex] + 20);
					Serial.print("Button press (HIGH), color temperature increased for ");
					Serial.print(entity.entityId);
					Serial.print(": ");
					Serial.println(targetColorTempValues[currentEntityIndex]);
				} else {
				targetBrightness[currentEntityIndex] = min(255, targetBrightness[currentEntityIndex] + 10);
				Serial.print("Button press (HIGH), brightness increased for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.println(targetBrightness[currentEntityIndex]);
				}
			} else if (strcmp(entity.domain, "climate") == 0) {
				targetTemperature = min(MAX_TEMP, targetTemperature + 1.0f);
				Serial.print("Button press (HIGH), temperature increased for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.print(targetTemperature);
				Serial.println("°C");
			} else {
				targetVolumeLevels[currentEntityIndex] = min(100, targetVolumeLevels[currentEntityIndex] + 5);
				Serial.print("Button press (HIGH), volume increased for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.println(targetVolumeLevels[currentEntityIndex]);
			}
		} else {
			if (strcmp(entity.domain, "light") == 0) {
				// For color temperature colors (indices 7-9), adjust color temperature
				if (colorIndices[currentEntityIndex] >= 7 && colorIndices[currentEntityIndex] <= 9) {
					targetColorTempValues[currentEntityIndex] = max(153, targetColorTempValues[currentEntityIndex] - 20);
					Serial.print("Button release (LOW), color temperature decreased for ");
					Serial.print(entity.entityId);
					Serial.print(": ");
					Serial.println(targetColorTempValues[currentEntityIndex]);
				} else {
				targetBrightness[currentEntityIndex] = max(0, targetBrightness[currentEntityIndex] - 10);
				Serial.print("Button release (LOW), brightness decreased for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.println(targetBrightness[currentEntityIndex]);
				}
			} else if (strcmp(entity.domain, "climate") == 0) {
				targetTemperature = max(MIN_TEMP, (float)(targetTemperature - 1.0));
				Serial.print("Button release (LOW), temperature decreased for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.print(targetTemperature);
				Serial.println("°C");
			} else {
				targetVolumeLevels[currentEntityIndex] = max(0, targetVolumeLevels[currentEntityIndex] - 5);
				Serial.print("Button release (LOW), volume decreased for ");
				Serial.print(entity.entityId);
				Serial.print(": ");
				Serial.println(targetVolumeLevels[currentEntityIndex]);
			}
		}
			lastKnobActivity = millis();
			updateDisplay();
			delay(50);
		}

		if (currentPushButtonState != lastPushButtonState && currentPushButtonState == LOW) {
			if (strcmp(entity.domain, "climate") == 0) {
				// For climate, cycle through HVAC modes instead of simple on/off
				cycleHvacMode();
				Serial.print("Dial push detected, cycling HVAC mode for ");
				Serial.print(entity.entityId);
				Serial.print(" to ");
				Serial.println(hvacMode);
			} else {
				entityStates[currentEntityIndex] = !entityStates[currentEntityIndex];
				Serial.print("Dial push detected, toggling state for ");
				Serial.print(entity.entityId);
				Serial.print(" to ");
				Serial.println(entityStates[currentEntityIndex] ? "ON" : "OFF");
				toggleEntity(currentBackButtonState);
			}
			updateDisplay();
			delay(50);
		}

		if (currentBackButtonState != lastBackButtonState && currentBackButtonState == LOW) {
			if (strcmp(entity.domain, "light") == 0 && entityStates[currentEntityIndex]) {
				colorIndices[currentEntityIndex] = (colorIndices[currentEntityIndex] - 1 + numColors) % numColors;
				Serial.print("Back button pressed, changing color for ");
				Serial.print(entity.entityId);
				Serial.print(" to ");
				Serial.println(colorNames[colorIndices[currentEntityIndex]]);

				// If color has color temperature (index 7-9), publish color temp, otherwise publish HS color
				if (colors[colorIndices[currentEntityIndex]][2] > 0) {
					targetColorTempValues[currentEntityIndex] = (int)colors[colorIndices[currentEntityIndex]][2];
					publishColorTemp();
				} else {
				publishColor();
				}
			} else if (strcmp(entity.domain, "media_player") == 0 && entityStates[currentEntityIndex]) {
				currentTvSourceIndex = (currentTvSourceIndex - 1 + numTvSources) % numTvSources;
				currentTvTargetSourceIndex = currentTvSourceIndex;
				Serial.print("Back button pressed, changing source for ");
				Serial.print(entity.entityId);
				Serial.print(" to ");
				Serial.println(tvSources[currentTvSourceIndex]);
				publishSource();
			}
			updateDisplay();
			delay(50);
		}
	}

	if (currentLeftButtonState != lastLeftButtonState && currentLeftButtonState == LOW) {
		currentEntityIndex = (currentEntityIndex + 1) % numEntities;
		Serial.print("Left button pressed, switching to entity: ");
		Serial.println(entities[currentEntityIndex].entityId);
		updateTopics();
		if (connected) {
			client.unsubscribe(topics.update.c_str());
			Serial.print("Unsubscribed from update topic: ");
			Serial.println(topics.update);
			client.subscribe(topics.update.c_str());
			Serial.print("Subscribed to update topic: ");
			Serial.println(topics.update);
			stateReceived[currentEntityIndex] = false;
			lastRequestTime = 0;
		}
		updateDisplay();
		delay(50);
	}

	lastButtonState = currentButtonState;
	lastPushButtonState = currentPushButtonState;
	lastBackButtonState = currentBackButtonState;
	lastLeftButtonState = currentLeftButtonState;
}

void callback(char* topic, byte* payload, unsigned int length) {
  if (!oledAttached) {
    Serial.println("MQTT callback ignored: OLED not attached");
    return;
  }
  
  // Don't process MQTT updates if weather screensaver is active
  if (isDisplayingWeatherScreensaver) {
    Serial.println("MQTT callback ignored: Weather screensaver is active");
    return;
  }

	String message;
	for (unsigned int i = 0; i < length; i++) {
		message += (char)payload[i];
	}

	Serial.print("Received MQTT message on topic: ");
	Serial.print(topic);
	Serial.print(", payload: ");
	Serial.println(message);

	String topicStr = String(topic);
	int entityIndex = -1;
	
	// Check if it's a traditional format (light or media_player)
	if (topicStr.startsWith("homeassistant/light/") || topicStr.startsWith("homeassistant/media_player/")) {
		for (int i = 0; i < numEntities; i++) {
			if (strcmp(entities[i].domain, "light") == 0 || strcmp(entities[i].domain, "media_player") == 0) {
				String expectedUpdateTopic = String("homeassistant/") + entities[i].domain + "/" + entities[i].entityId + "/update";
				if (topicStr == expectedUpdateTopic) {
					entityIndex = i;
					break;
				}
			}
		}
		
		if (entityIndex != -1) {
			// Process traditional format message with JSON
			StaticJsonDocument<200> doc;
			DeserializationError error = deserializeJson(doc, message);
			if (error) {
				Serial.print("deserializeJson() failed: ");
				Serial.println(error.c_str());
				return;
			}
			
			const char* entity_id = doc["entity_id"];
			if (strcmp(entity_id, entities[entityIndex].entityId) != 0) {
				Serial.println("Entity ID mismatch, ignoring message");
				return;
			}
			
			const char* state = doc["state"];
			if (state) {
				entityStates[entityIndex] = (strcmp(state, "on") == 0);
				Serial.print("State updated for ");
				Serial.print(entity_id);
				Serial.print(": ");
				Serial.println(entityStates[entityIndex] ? "on" : "off");
				if (entityIndex == currentEntityIndex) {
					digitalWrite(buttonLedPin, entityStates[entityIndex]);
					Serial.println("Updated button LED state");
				}
				stateReceived[entityIndex] = true;
			}
			
			// Handle domain-specific attributes
			const Entity& entity = entities[entityIndex];
			if (strcmp(entity.domain, "light") == 0) {
				if (doc.containsKey("brightness") && !doc["brightness"].isNull()) {
					displayBrightness[entityIndex] = doc["brightness"].as<int>();
					if (lastKnobActivity == 0) {
						targetBrightness[entityIndex] = displayBrightness[entityIndex];
					}
					Serial.print("Brightness updated for ");
					Serial.print(entity_id);
					Serial.print(": ");
					Serial.println(displayBrightness[entityIndex]);
				}
				if (doc.containsKey("hs_color") && !doc["hs_color"].isNull()) {
					float h = doc["hs_color"][0].as<float>();
					float s = doc["hs_color"][1].as<float>();
					bool matched = false;
					for (int i = 0; i < numColors; i++) {
						if (abs(colors[i][0] - h) < 5 && abs(colors[i][1] - s) < 5) {
							colorIndices[entityIndex] = i;
							matched = true;
							break;
						}
					}
					if (!matched) colorIndices[entityIndex] = 0;
					Serial.print("HS color updated for ");
					Serial.print(entity_id);
					Serial.print(": ");
					Serial.print(h);
					Serial.print(", ");
					Serial.println(s);
				}
				if (doc.containsKey("color_temp") && !doc["color_temp"].isNull()) {
					int ct = doc["color_temp"].as<int>();
					colorTempValues[entityIndex] = ct;
					if (lastKnobActivity == 0) {
						targetColorTempValues[entityIndex] = ct;
					}
					Serial.print("Color temperature updated for ");
					Serial.print(entity_id);
					Serial.print(": ");
					Serial.println(ct);
				}
			} else if (strcmp(entity.domain, "media_player") == 0) {
				if (doc.containsKey("volume_level") && !doc["volume_level"].isNull()) {
					volumeLevels[entityIndex] = (int)(doc["volume_level"].as<float>() * 100);
					if (lastKnobActivity == 0) {
						targetVolumeLevels[entityIndex] = volumeLevels[entityIndex];
					}
					Serial.print("Volume level updated for ");
					Serial.print(entity_id);
					Serial.print(": ");
					Serial.println(volumeLevels[entityIndex]);
				}
				if (doc.containsKey("source") && !doc["source"].isNull()) {
					const char* source = doc["source"];
					for (int i = 0; i < numTvSources; i++) {
						if (strcmp(source, tvSources[i]) == 0) {
							currentTvSourceIndex = i;
							currentTvTargetSourceIndex = -1;
							break;
						}
					}
					Serial.print("Source updated for ");
					Serial.print(entity_id);
					Serial.print(": ");
					Serial.println(source);
				}
			}
		}
	} 
	// Handle climate sensor updates
	else if (topicStr == "homeassistant/sensor/sam/temperature/state") {
		currentTemperature = message.toFloat();
		Serial.print("Current temperature updated: ");
		Serial.print(currentTemperature);
		Serial.println("°C");
		updateDisplay();
	}
	else if (topicStr == "homeassistant/sensor/sam/humidity/state") {
		currentHumidity = message.toFloat();
		Serial.print("Current humidity updated: ");
		Serial.print(currentHumidity);
		Serial.println("%");
		updateDisplay();
	}
	else if (topicStr == "homeassistant/number/sam/setpoint/state") {
		float newSetpoint = message.toFloat();
		if (abs(newSetpoint - targetTemperature) >= 0.1) {
			targetTemperature = newSetpoint;
			displayTemperature = targetTemperature;
			Serial.print("Temperature setpoint updated: ");
			Serial.print(targetTemperature);
			Serial.println("°C");
			updateDisplay();
		}
	}
	else if (topicStr == "homeassistant/climate/sam/state") {
		// Parse climate state JSON
		StaticJsonDocument<300> climateDoc;
		DeserializationError error = deserializeJson(climateDoc, message);
		if (!error) {
			if (climateDoc.containsKey("hvac_mode")) {
				hvacMode = climateDoc["hvac_mode"].as<String>();
			}
			if (climateDoc.containsKey("hvac_action")) {
				hvacAction = climateDoc["hvac_action"].as<String>();
			}
			if (climateDoc.containsKey("target_temperature")) {
				float newTarget = climateDoc["target_temperature"].as<float>();
				if (abs(newTarget - targetTemperature) >= 0.1) {
					targetTemperature = newTarget;
					displayTemperature = targetTemperature;
				}
			}
			if (climateDoc.containsKey("current_temperature")) {
				currentTemperature = climateDoc["current_temperature"].as<float>();
			}
			// Set entity state based on HVAC mode
			for (int i = 0; i < numEntities; i++) {
				if (strcmp(entities[i].domain, "climate") == 0) {
					entityStates[i] = (hvacMode != "off");
					stateReceived[i] = true;
					break;
				}
			}
			Serial.print("Climate state updated - Mode: ");
			Serial.print(hvacMode);
			Serial.print(", Action: ");
			Serial.print(hvacAction);
			Serial.print(", Target: ");
			Serial.print(targetTemperature);
			Serial.println("°C");
			updateDisplay();
		}
	}
	// Handle direct format messages for computer entities
	else if (topicStr.contains("_sessionstate/state") || 
			 topicStr.contains("_activewindow/state") || 
			 topicStr.contains("_currentvolume/state") ||
			 topicStr.contains("_enforce_lock/state")) {
		
		// Extract computer name from topic
		int firstSlash = topicStr.indexOf('/') + 1;
		int secondSlash = topicStr.indexOf('/', firstSlash + 1);
		int thirdSlash = topicStr.indexOf('/', secondSlash + 1);
		String domainType = topicStr.substring(firstSlash, secondSlash);
		String computerName = topicStr.substring(secondSlash + 1, thirdSlash);
		computerName = computerName.substring(0, computerName.indexOf('_'));
		
		// Find matching entity
		for (int i = 0; i < numEntities; i++) {
			if (strcmp(entities[i].domain, "computer") == 0) {
				String entityCompName = String(entities[i].entityId).substring(String(entities[i].entityId).indexOf(".") + 1).toLowerCase();
				if (entityCompName == computerName) {
					entityIndex = i;
					break;
				}
			}
		}
		
		if (entityIndex != -1) {
			// Process based on the sensor type
			if (topicStr.contains("_sessionstate/state")) {
				pcSessionState = message;
				entityStates[entityIndex] = (pcSessionState != "off");
				stateReceived[entityIndex] = true;
				Serial.print("Session state updated for computer ");
				Serial.print(computerName);
				Serial.print(": ");
				Serial.println(pcSessionState);
				
				if (entityIndex == currentEntityIndex) {
					digitalWrite(buttonLedPin, entityStates[entityIndex]);
				}
			}
			else if (topicStr.contains("_activewindow/state")) {
				pcActiveWindow = message;
				Serial.print("Active window updated for computer ");
				Serial.print(computerName);
				Serial.print(": ");
				Serial.println(pcActiveWindow);
			}
			else if (topicStr.contains("_currentvolume/state")) {
				int volume = message.toInt();
				volumeLevels[entityIndex] = volume;
				if (lastKnobActivity == 0) {
					targetVolumeLevels[entityIndex] = volumeLevels[entityIndex];
				}
				Serial.print("Volume updated for computer ");
				Serial.print(computerName);
				Serial.print(": ");
				Serial.println(volume);
			}
			else if (topicStr.contains("_enforce_lock/state")) {
				bool enforceLockState = (message == "ON" || message == "on");
				Serial.print("Enforce lock updated for computer ");
				Serial.print(computerName);
				Serial.print(": ");
				Serial.println(enforceLockState ? "enabled" : "disabled");
			}
		}
	}

	if (entityIndex == currentEntityIndex) {
		updateDisplay();
		Serial.println("Display updated after MQTT callback");
	}
}

void reconnect() {
	if (!oledAttached) {
		Serial.println("Reconnect skipped: OLED not attached");
		return;
	}

	while (!client.connected() && WiFi.status() == WL_CONNECTED) {
		Serial.println("Attempting MQTT connection...");
		String clientId = "ESP32-" + String(random(0xffff), HEX);
		    if (client.connect(clientId.c_str(), Config::getMQTTUser(), Config::getMQTTPassword())) {
			Serial.println("MQTT connected");
			
			// Subscribe to topics for all entities
			for (int i = 0; i < numEntities; i++) {
				if (strcmp(entities[i].domain, "light") == 0 || strcmp(entities[i].domain, "media_player") == 0) {
					// Traditional format for lights and media players
					String subUpdateTopic = String("homeassistant/") + entities[i].domain + "/" + entities[i].entityId + "/update";
					client.subscribe(subUpdateTopic.c_str());
					Serial.print("Subscribed to: ");
					Serial.println(subUpdateTopic);
				} 
				else if (strcmp(entities[i].domain, "climate") == 0) {
					// Climate control subscriptions
					client.subscribe("homeassistant/sensor/sam/temperature/state");
					Serial.println("Subscribed to: homeassistant/sensor/sam/temperature/state");
					
					client.subscribe("homeassistant/sensor/sam/humidity/state");
					Serial.println("Subscribed to: homeassistant/sensor/sam/humidity/state");
					
					client.subscribe("homeassistant/number/sam/setpoint/state");
					Serial.println("Subscribed to: homeassistant/number/sam/setpoint/state");
					
					client.subscribe("homeassistant/climate/sam/state");
					Serial.println("Subscribed to: homeassistant/climate/sam/state");
				}
				else if (strcmp(entities[i].domain, "computer") == 0) {
					// Direct format for computers
					String computerName = String(entities[i].entityId).substring(String(entities[i].entityId).indexOf(".") + 1).toLowerCase();
					
					// Subscribe to state topics
					String sessionStateTopic = "homeassistant/sensor/" + computerName + "/" + computerName + "_sessionstate/state";
					client.subscribe(sessionStateTopic.c_str());
					Serial.print("Subscribed to: ");
					Serial.println(sessionStateTopic);
					
					String activeWindowTopic = "homeassistant/sensor/" + computerName + "/" + computerName + "_activewindow/state";
					client.subscribe(activeWindowTopic.c_str());
					Serial.print("Subscribed to: ");
					Serial.println(activeWindowTopic);
					
					String currentVolumeTopic = "homeassistant/sensor/" + computerName + "/" + computerName + "_currentvolume/state";
					client.subscribe(currentVolumeTopic.c_str());
					Serial.print("Subscribed to: ");
					Serial.println(currentVolumeTopic);
					
					String enforceLockTopic = "homeassistant/switch/" + computerName + "/" + computerName + "_enforce_lock/state";
					client.subscribe(enforceLockTopic.c_str());
					Serial.print("Subscribed to: ");
					Serial.println(enforceLockTopic);
				}
			}
		} else {
			Serial.print("MQTT connection failed, rc=");
			Serial.print(client.state());
			Serial.println(" retrying in 5 seconds");
			digitalWrite(onboardLedPin, HIGH);
			delay(5000);
		}
	}
}

void publishBrightness() {
	if (!oledAttached || !connected) {
		Serial.println("publishBrightness skipped: OLED not attached or not connected");
		return;
	}
	String payload = String(targetBrightness[currentEntityIndex]);
	Serial.print("Publishing brightness to ");
	Serial.print(topics.brightness);
	Serial.print(": ");
	Serial.println(payload);
	client.publish(topics.brightness.c_str(), payload.c_str());
	if (!entityStates[currentEntityIndex]) {
		entityStates[currentEntityIndex] = true;
		Serial.println("Entity state set to ON due to brightness change");
		toggleEntity(HIGH);
	}
}

void publishColor() {
	if (!oledAttached || !connected) {
		Serial.println("publishColor skipped: OLED not attached or not connected");
		return;
	}

	const Entity& entity = entities[currentEntityIndex];
	if (strcmp(entity.domain, "light") != 0) {
		return;
	}

	String payload = String(colors[colorIndices[currentEntityIndex]][0]) + "," +
					 String(colors[colorIndices[currentEntityIndex]][1]);
	Serial.print("Publishing color to ");
	Serial.print(topics.hs);
	Serial.print(": ");
	Serial.println(payload);
	client.publish(topics.hs.c_str(), payload.c_str());
	if (!entityStates[currentEntityIndex]) {
		entityStates[currentEntityIndex] = true;
		Serial.println("Entity state set to ON due to color change");
		toggleEntity(HIGH);
	}
}

void publishColorTemp() {
	if (!oledAttached || !connected) {
		Serial.println("publishColorTemp skipped: OLED not attached or not connected");
		return;
	}

	const Entity& entity = entities[currentEntityIndex];
	if (strcmp(entity.domain, "light") != 0) {
		return;
	}

	String payload = String(targetColorTempValues[currentEntityIndex]);
	Serial.print("Publishing color temperature to ");
	Serial.print(topics.color_temp);
	Serial.print(": ");
	Serial.println(payload);
	client.publish(topics.color_temp.c_str(), payload.c_str());
	if (!entityStates[currentEntityIndex]) {
		entityStates[currentEntityIndex] = true;
		Serial.println("Entity state set to ON due to color temperature change");
		toggleEntity(HIGH);
	}
}

void publishVolume() {
	if (!oledAttached || !connected) {
		Serial.println("publishVolume skipped: OLED not attached or not connected");
		return;
	}
	
	const Entity& entity = entities[currentEntityIndex];
	
	// Handle volume differently for computer vs media player
	if (strcmp(entity.domain, "computer") == 0) {
		// For computer, send the volume value as the payload
		String payload = String(targetVolumeLevels[currentEntityIndex]);
		Serial.print("Publishing volume to ");
		Serial.print(topics.volume);
		Serial.print(": ");
		Serial.println(payload);
		client.publish(topics.volume.c_str(), payload.c_str());
		
		// No need to turn on the computer for volume changes
		// as volume control should work regardless of power state
	} else {
		// For media players, send as 0-1.0 float
		float volumeFloat = targetVolumeLevels[currentEntityIndex] / 100.0;
		String payload = String(volumeFloat, 2);
		Serial.print("Publishing volume to ");
		Serial.print(topics.volume);
		Serial.print(": ");
		Serial.println(payload);
		client.publish(topics.volume.c_str(), payload.c_str());
		
		if (!entityStates[currentEntityIndex]) {
			entityStates[currentEntityIndex] = true;
			Serial.println("Entity state set to ON due to volume change");
			toggleEntity(HIGH);
		}
	}
}

void publishSource() {
	if (!oledAttached || !connected) {
		Serial.println("publishSource skipped: OLED not attached or not connected");
		return;
	}
	String payload = tvSources[currentTvSourceIndex];
	Serial.print("Publishing source to ");
	Serial.print(topics.source);
	Serial.print(": ");
	Serial.println(payload);
	client.publish(topics.source.c_str(), payload.c_str());
	if (!entityStates[currentEntityIndex]) {
		entityStates[currentEntityIndex] = true;
		Serial.println("Entity state set to ON due to source change");
		toggleEntity(HIGH);
	}
}

void toggleEntity(bool currentBackButtonState) {
	if (!oledAttached || !connected) {
		Serial.println("toggleEntity skipped: OLED not attached or not connected");
		return;
	}
	String payload = entityStates[currentEntityIndex] ? "ON" : "OFF";
	const Entity& entity = entities[currentEntityIndex];
	if (strcmp(entity.domain, "media_player") == 0 && currentBackButtonState != LOW && !entityStates[currentEntityIndex]) {
		payload = "PLAYPAUSE";
	}
	Serial.print("Publishing toggle command to ");
	Serial.print(topics.command);
	Serial.print(": ");
	Serial.println(payload);
	client.publish(topics.command.c_str(), payload.c_str());
}

void toggleComputerLock() {
	if (!oledAttached || !connected) {
		Serial.println("toggleComputerLock skipped: OLED not attached or not connected");
		return;
	}
	
	const Entity& entity = entities[currentEntityIndex];
	if (strcmp(entity.domain, "computer") == 0) {
		Serial.print("Publishing lock command to ");
		Serial.println(topics.lock);
		client.publish(topics.lock.c_str(), "PRESS");
	}
}

void toggleComputerMute() {
	if (!oledAttached || !connected) {
		Serial.println("toggleComputerMute skipped: OLED not attached or not connected");
		return;
	}
	
	const Entity& entity = entities[currentEntityIndex];
	if (strcmp(entity.domain, "computer") == 0) {
		Serial.print("Publishing mute command to ");
		Serial.println(topics.mute);
		client.publish(topics.mute.c_str(), "PRESS");
	}
}

void toggleComputerEnforceLock(bool enforce) {
	if (!oledAttached || !connected) {
		Serial.println("toggleComputerEnforceLock skipped: OLED not attached or not connected");
		return;
	}
	
	const Entity& entity = entities[currentEntityIndex];
	if (strcmp(entity.domain, "computer") == 0) {
		String payload = enforce ? "ON" : "OFF";
		Serial.print("Publishing enforce lock command to ");
		Serial.print(topics.enforceLock);
		Serial.print(": ");
		Serial.println(payload);
		client.publish(topics.enforceLock.c_str(), payload.c_str());
	}
}

void publishTemperatureSetpoint() {
	if (!oledAttached || !connected) {
		Serial.println("publishTemperatureSetpoint skipped: OLED not attached or not connected");
		return;
	}
	
	String payload = String(targetTemperature, 1);
	Serial.print("Publishing temperature setpoint to ");
	Serial.print(topics.setpoint);
	Serial.print(": ");
	Serial.print(payload);
	Serial.println("°C");
	client.publish(topics.setpoint.c_str(), payload.c_str());
}

void cycleHvacMode() {
	if (hvacMode == "off") {
		hvacMode = "heat";
	} else if (hvacMode == "heat") {
		hvacMode = "cool";
	} else if (hvacMode == "cool") {
		hvacMode = "auto";
	} else {
		hvacMode = "off";
	}
	
	// Update entity state based on new mode
	for (int i = 0; i < numEntities; i++) {
		if (strcmp(entities[i].domain, "climate") == 0) {
			entityStates[i] = (hvacMode != "off");
			break;
		}
	}
	
	// Publish the mode change to Home Assistant
	if (connected) {
		String climateCommand = "homeassistant/climate/sam/set";
		String payload = "{\"hvac_mode\":\"" + hvacMode + "\"}";
		Serial.print("Publishing HVAC mode change to ");
		Serial.print(climateCommand);
		Serial.print(": ");
		Serial.println(payload);
		client.publish(climateCommand.c_str(), payload.c_str());
	}
}

void updateDisplay() {
  if (!oledAttached) {
    Serial.println("updateDisplay skipped: OLED not attached");
    return;
  }
  
  // Don't update display if weather screensaver is active
  if (isDisplayingWeatherScreensaver) {
    Serial.println("updateDisplay skipped: Weather screensaver is active");
    return;
  }

	display.clearDisplay();
	display.setTextSize(1);
	display.setTextColor(SSD1306_WHITE);
	display.setCursor(0, 0);

	const Entity& entity = entities[currentEntityIndex];
	display.print(entity.friendlyName);
	display.setCursor(0, 20);

	if (strcmp(entity.domain, "light") == 0) {
		display.print(F("Brightness: "));
		display.print(ceil(targetBrightness[currentEntityIndex] / 255.0 * 100));
		display.println('%');
		int barWidth = map(displayBrightness[currentEntityIndex], 0, 255, 0, 100);
		display.drawRect(0, 30, 100, 10, SSD1306_WHITE);
		display.fillRect(0, 30, barWidth, 10, SSD1306_WHITE);
		display.setCursor(0, 50);
		display.print(colorNames[colorIndices[currentEntityIndex]]);

		// Show color temperature if applicable
		if (colors[colorIndices[currentEntityIndex]][2] > 0) {
			display.setCursor(0, 60);
			display.print("Temp: ");
			display.print((int)colors[colorIndices[currentEntityIndex]][2]);
			display.print("K");
		}
	} else if (strcmp(entity.domain, "media_player") == 0) {
		display.print(F("Volume: "));
		display.print(targetVolumeLevels[currentEntityIndex]);
		display.println('%');
		int barWidth = map(volumeLevels[currentEntityIndex], 0, 100, 0, 100);
		display.drawRect(0, 30, 100, 10, SSD1306_WHITE);
		display.fillRect(0, 30, barWidth, 10, SSD1306_WHITE);
		display.setCursor(0, 50);
		if (currentTvTargetSourceIndex != -1) {
			display.print("[");
			display.print(tvSources[currentTvTargetSourceIndex]);
			display.print("]");
		} else {
			display.print(tvSources[currentTvSourceIndex]);
		}
	} else if (strcmp(entity.domain, "computer") == 0) {
		display.print(F("Volume: "));
		display.print(targetVolumeLevels[currentEntityIndex]);
		display.println('%');
		int barWidth = map(volumeLevels[currentEntityIndex], 0, 100, 0, 100);
		display.drawRect(0, 30, 100, 10, SSD1306_WHITE);
		display.fillRect(0, 30, barWidth, 10, SSD1306_WHITE);
		display.setCursor(0, 40);
		// Truncate active window name if too long
		if (pcActiveWindow.length() > 10) {
			display.print(pcActiveWindow.substring(0, 8));
			display.print("..");
		} else {
			display.print(pcActiveWindow);
		}
		
		display.setCursor(0, 50);
		display.setTextSize(1);
		display.print(pcSessionState == "locked" ? "LOCK " : "UNLOCK ");
		
		// Check if there's enforce_lock information in the payload
		bool enforceLockActive = false;
		for (int i = 0; i < numEntities; i++) {
			if (strcmp(entities[i].domain, "computer") == 0 && 
				strcmp(entities[i].entityId, entity.entityId) == 0) {
				// This is a match, check if enforce_lock is active
				enforceLockActive = (pcSessionState == "locked");
				break;
			}
		}
		
		display.print(enforceLockActive ? "(ENFORCED)" : "");
		
		display.setCursor(0, 60);
		display.setTextSize(2);
		display.println(entityStates[currentEntityIndex] ? " ON" : " OFF");
	} else if (strcmp(entity.domain, "climate") == 0) {
		// Climate/HVAC display
		display.print(F("Target: "));
		display.print(targetTemperature, 1);
		display.println(F("C"));
		
		// Temperature setpoint bar
		int barWidth = map((int)(targetTemperature * 10), (int)(MIN_TEMP * 10), (int)(MAX_TEMP * 10), 0, 100);
		display.drawRect(0, 30, 100, 8, SSD1306_WHITE);
		display.fillRect(0, 30, barWidth, 8, SSD1306_WHITE);
		
		// Current temperature and humidity
		display.setCursor(0, 42);
		display.setTextSize(1);
		display.print(F("Now: "));
		display.print(currentTemperature, 1);
		display.print(F("C "));
		display.print((int)currentHumidity);
		display.println(F("%"));
		
		// HVAC mode and action
		display.setCursor(0, 52);
		display.print(F("Mode: "));
		display.print(hvacMode.toUpperCase());
		if (hvacAction != "idle" && hvacAction != "") {
			display.print(F(" ("));
			display.print(hvacAction.toUpperCase());
			display.print(F(")"));
		}
		
		// Overall system status
		display.setCursor(0, 62);
		display.setTextSize(1);
		display.println(entityStates[currentEntityIndex] ? "SYSTEM ON" : "SYSTEM OFF");
	}
	display.display();
	Serial.print("Display updated for ");
	Serial.println(entity.entityId);
}
