#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>
#include "env_loader.h"

// Configuration class to handle environment variables and defaults
class Config {
private:
	// Static storage for string values to ensure lifetime
	static String wifiSSID;
	static String wifiPassword;
	static String mqttServer;
	static String mqttUser;
	static String mqttPassword;
	static String haIP;
	static String haToken;
	static String weatherEntity;
	static String indoorTempEntity;
	static String outdoorTempEntity;
	static bool initialized;
	
	static void initialize() {
		if (initialized) return;
		
		EnvLoader::loadEnv("/config.txt");
		
		wifiSSID = EnvLoader::getEnv("WIFI_SSID", "GeeGee");
		wifiPassword = EnvLoader::getEnv("WIFI_PASSWORD", "LilyLola");
		mqttServer = EnvLoader::getEnv("MQTT_SERVER", "192.168.1.15");
		mqttUser = EnvLoader::getEnv("MQTT_USER", "devices");
		mqttPassword = EnvLoader::getEnv("MQTT_PASSWORD", "LilyLola");
		haIP = EnvLoader::getEnv("HA_IP", "192.168.1.15");
		haToken = EnvLoader::getEnv("HA_TOKEN", "your_ha_token_here");
		weatherEntity = EnvLoader::getEnv("WEATHER_ENTITY", "weather.forecast_home");
		indoorTempEntity = EnvLoader::getEnv("INDOOR_TEMP_ENTITY", "sensor.indoor_temperature");
		outdoorTempEntity = EnvLoader::getEnv("OUTDOOR_TEMP_ENTITY", "sensor.outdoor_temperature");
		
		initialized = true;
	}

public:
	// WiFi Configuration
	static const char* getWiFiSSID() {
		initialize();
		return wifiSSID.c_str();
	}
	
	static const char* getWiFiPassword() {
		initialize();
		return wifiPassword.c_str();
	}
	
	// MQTT Configuration
	static const char* getMQTTServer() {
		initialize();
		return mqttServer.c_str();
	}
	
	static int getMQTTPort() {
		initialize();
		return EnvLoader::getEnvInt("MQTT_PORT", 1883);
	}
	
	static const char* getMQTTUser() {
		initialize();
		return mqttUser.c_str();
	}
	
	static const char* getMQTTPassword() {
		initialize();
		return mqttPassword.c_str();
	}
	
	// Home Assistant Configuration
	static const char* getHAIP() {
		initialize();
		return haIP.c_str();
	}
	
	static int getHAPort() {
		initialize();
		return EnvLoader::getEnvInt("HA_PORT", 8123);
	}
	
	static const char* getHAToken() {
		initialize();
		return haToken.c_str();
	}
	
	// Weather Configuration
	static const char* getWeatherEntity() {
		initialize();
		return weatherEntity.c_str();
	}
	
	static const char* getIndoorTempEntity() {
		initialize();
		return indoorTempEntity.c_str();
	}
	
	static const char* getOutdoorTempEntity() {
		initialize();
		return outdoorTempEntity.c_str();
	}
	
	// Display Configuration
	static int getOLEDI2CAddress() {
		initialize();
		return EnvLoader::getEnvInt("OLED_I2C_ADDRESS", 0x3C);
	}
	
	static int getScreenWidth() {
		initialize();
		return EnvLoader::getEnvInt("SCREEN_WIDTH", 128);
	}
	
	static int getScreenHeight() {
		initialize();
		return EnvLoader::getEnvInt("SCREEN_HEIGHT", 64);
	}
	
	// Screensaver Configuration
	static unsigned long getIdleTimeoutMS() {
		initialize();
		return EnvLoader::getEnvInt("IDLE_TIMEOUT_SECONDS", 30) * 1000UL;
	}
	
	// Pin Configuration
	static int getOnboardLEDPin() {
		initialize();
		return EnvLoader::getEnvInt("ONBOARD_LED_PIN", 2);
	}
	
	static int getButtonPin() {
		initialize();
		return EnvLoader::getEnvInt("BUTTON_PIN", 4);
	}
	
	static int getButtonLEDPin() {
		initialize();
		return EnvLoader::getEnvInt("BUTTON_LED_PIN", 5);
	}
	
	static int getEncoderTRAPin() {
		initialize();
		return EnvLoader::getEnvInt("ENCODER_TRA_PIN", 25);
	}
	
	static int getEncoderTRBPin() {
		initialize();
		return EnvLoader::getEnvInt("ENCODER_TRB_PIN", 26);
	}
	
	static int getEncoderPushPin() {
		initialize();
		return EnvLoader::getEnvInt("ENCODER_PUSH_PIN", 27);
	}
	
	static int getBackButtonPin() {
		initialize();
		return EnvLoader::getEnvInt("BACK_BUTTON_PIN", 14);
	}
	
	static int getLeftButtonPin() {
		initialize();
		return EnvLoader::getEnvInt("LEFT_BUTTON_PIN", 12);
	}
};

// Static member definitions
String Config::wifiSSID;
String Config::wifiPassword;
String Config::mqttServer;
String Config::mqttUser;
String Config::mqttPassword;
String Config::haIP;
String Config::haToken;
String Config::weatherEntity;
String Config::indoorTempEntity;
String Config::outdoorTempEntity;
bool Config::initialized = false;

#endif // CONFIG_H 