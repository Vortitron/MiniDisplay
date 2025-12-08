#!/usr/bin/env python3
"""
Generate new encryption keys and OTA passwords for ESPHome devices
Run this script to generate secure keys, then copy them into secrets.yaml
"""

import secrets
import base64

print("=" * 70)
print("ESPHome Security Credentials Generator")
print("=" * 70)
print("\nIMPORTANT: Copy these values into your secrets.yaml file")
print("Then delete this output for security!\n")

# Generate 10 encryption keys (32 bytes each, base64 encoded)
print("\n# ===== API ENCRYPTION KEYS =====")
print("# Copy these into secrets.yaml\n")

devices_encryption = [
    "boilercontrol_encryption_key",
    "bedroomlights_encryption_key",
    "loftc3_encryption_key",
    "downstairs_encryption_key",
    "frontpath_encryption_key",
    "minidisplay_encryption_key",
    "manifoldtemp_encryption_key",
    "kitchendetectorer_encryption_key",
    "loft_encryption_key",
    "bioofficec3_encryption_key"
]

for device in devices_encryption:
    # Generate 32 random bytes and base64 encode
    key_bytes = secrets.token_bytes(32)
    key_b64 = base64.b64encode(key_bytes).decode('utf-8')
    print(f'{device}: "{key_b64}"')

# Generate 10 OTA passwords (16 bytes hex)
print("\n\n# ===== OTA PASSWORDS =====")
print("# Copy these into secrets.yaml\n")

devices_ota = [
    "boilercontrol_ota_password",
    "bedroomlights_ota_password",
    "loftc3_ota_password",
    "downstairs_ota_password",
    "frontpath_ota_password",
    "minidisplay_ota_password",
    "manifoldtemp_ota_password",
    "kitchendetectorer_ota_password",
    "loft_ota_password",
    "bioofficec3_ota_password"
]

for device in devices_ota:
    password = secrets.token_hex(16)
    print(f'{device}: "{password}"')

print("\n" + "=" * 70)
print("NEXT STEPS:")
print("1. Copy the above values into your secrets.yaml file")
print("2. Replace the GENERATE_NEW_KEY_X and GENERATE_NEW_OTA_X placeholders")
print("3. Delete this script output from your terminal")
print("4. Compile and upload the updated configs to each device")
print("=" * 70)

