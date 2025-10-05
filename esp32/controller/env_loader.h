#ifndef ENV_LOADER_H
#define ENV_LOADER_H

#include <Arduino.h>
#include <SPIFFS.h>
#include <map>

class EnvLoader {
private:
	static std::map<String, String> envVars;
	static bool loaded;

public:
	// Load environment variables from SPIFFS config file
	static bool loadEnv(const char* filename = "/config.txt") {
		if (loaded) return true;
		
		if (!SPIFFS.begin(true)) {
			Serial.println("Failed to mount SPIFFS");
			return false;
		}
		
		File file = SPIFFS.open(filename, "r");
		if (!file) {
			Serial.println("No config file found, using defaults");
			return false;
		}
		
		Serial.println("Loading configuration from SPIFFS...");
		
		while (file.available()) {
			String line = file.readStringUntil('\n');
			line.trim();
			
			// Skip empty lines and comments
			if (line.length() == 0 || line.startsWith("#")) {
				continue;
			}
			
			// Parse key=value pairs
			int equalPos = line.indexOf('=');
			if (equalPos > 0) {
				String key = line.substring(0, equalPos);
				String value = line.substring(equalPos + 1);
				key.trim();
				value.trim();
				
				// Remove quotes if present
				if (value.startsWith("\"") && value.endsWith("\"")) {
					value = value.substring(1, value.length() - 1);
				}
				
				envVars[key] = value;
				Serial.println("Loaded: " + key + " = " + value);
			}
		}
		
		file.close();
		loaded = true;
		Serial.println("Configuration loaded successfully");
		return true;
	}
	
	// Get environment variable value
	static String getEnv(const String& key, const String& defaultValue = "") {
		if (!loaded) {
			loadEnv();
		}
		
		auto it = envVars.find(key);
		if (it != envVars.end()) {
			return it->second;
		}
		return defaultValue;
	}
	
	// Get environment variable as integer
	static int getEnvInt(const String& key, int defaultValue = 0) {
		String value = getEnv(key);
		if (value.length() > 0) {
			return value.toInt();
		}
		return defaultValue;
	}
	
	// Check if environment variable exists
	static bool hasEnv(const String& key) {
		if (!loaded) {
			loadEnv();
		}
		return envVars.find(key) != envVars.end();
	}
	
	// Print all loaded environment variables (for debugging)
	static void printEnv() {
		if (!loaded) {
			loadEnv();
		}
		
		Serial.println("Loaded environment variables:");
		for (const auto& pair : envVars) {
			Serial.println(pair.first + " = " + pair.second);
		}
	}
};

// Static member definitions
std::map<String, String> EnvLoader::envVars;
bool EnvLoader::loaded = false;

#endif // ENV_LOADER_H 