# ESPHome Security Setup - IMPORTANT!

## ⚠️ CRITICAL: Your Credentials Were Compromised!

Since your ESPHome configs were in a **public GitHub repository**, all your API encryption keys and OTA passwords are now **COMPROMISED**. Anyone with network access could potentially control your devices or upload malicious firmware.

I've refactored all your configurations to use a `secrets.yaml` file, but you **MUST** generate new keys before deploying!

---

## 🔒 Step 1: Generate New Keys

Run the Python script I created:

```bash
cd c:\dev\MiniDisplay\esphome
python generate_keys.py
```

This will output fresh encryption keys and OTA passwords. **Copy the entire output** and proceed to Step 2.

### Alternative Methods (if Python script doesn't work):

**For API Encryption Keys:**
```bash
# Using ESPHome CLI
esphome wizard dummy.yaml
# Copy the generated encryption key

# OR using Python directly
python3 -c "import secrets; import base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

**For OTA Passwords:**
```bash
# Using OpenSSL
openssl rand -hex 16

# OR using Python
python3 -c "import secrets; print(secrets.token_hex(16))"
```

You need to generate:
- **10 encryption keys** (one per device)
- **10 OTA passwords** (one per device)

---

## 📝 Step 2: Update secrets.yaml

Open `c:\dev\MiniDisplay\esphome\secrets.yaml` and replace ALL the `GENERATE_NEW_KEY_X` and `GENERATE_NEW_OTA_X` placeholders with the values you generated in Step 1.

**Example:**
```yaml
# Before:
boilercontrol_encryption_key: "GENERATE_NEW_KEY_1"

# After (use YOUR generated key!):
boilercontrol_encryption_key: "xK8vN2pQ7mR4tY9wZ3aB6cD1eF5gH0iJ8kL4mN7oP2qR="
```

---

## 🚀 Step 3: Flash Updated Configs to Each Device

For each device, you need to compile and upload the updated configuration:

```bash
# Example for BoilerControl
cd c:\dev\MiniDisplay\esphome\BoilerControl
esphome run BoilerControl.yaml
```

**Devices to update:**
1. BoilerControl (`BoilerControl/BoilerControl.yaml`)
2. BedroomLights (`BedroomLights/BedroomLights.yaml`)
3. LoftC3 (`LoftWay/NewLoftWayC3.yaml`)
4. Downstairs (`Downstairs/DownstairsAllrum.yaml`)
5. FrontPath (`FrontPath/FrontPath.yaml`)
6. MiniDisplay (`MiniDisplay/minidisplay.yaml`)
7. ManifoldTemperature (`ManifoldTemperature/ManifoldTemperature.yaml`)
8. KitchenDetectorer (`KitchenDetectorer/KitchenDetectorer.yaml`)
9. Loft Display (`Loft/loft.yaml`)
10. BioOfficeC3 (`BioOffice/BioOfficeC3.yaml`)

### First Upload Requires USB/Serial Connection

⚠️ **IMPORTANT**: Because the API encryption key has changed, you'll need to upload via USB/serial for the first time. After that, OTA updates will work normally.

---

## 🔐 Step 4: Update Home Assistant

After flashing each device, Home Assistant will show an error because the encryption key changed.

For each device:
1. Go to **Settings → Devices & Services → ESPHome**
2. Find the device showing an error
3. Click **RECONFIGURE**
4. Enter the **new encryption key** from your `secrets.yaml`
5. Submit

---

## 🛡️ Step 5: Secure Your GitHub Repository

### Option A: Keep Repository Public (Recommended Setup)

1. **Verify `.gitignore` is working:**
   ```bash
   cd c:\dev\MiniDisplay
   git status
   ```
   Make sure `secrets.yaml` is **NOT** listed (if it is, it's being tracked!)

2. **If secrets.yaml is already tracked, remove it:**
   ```bash
   git rm --cached esphome/secrets.yaml
   git commit -m "Remove secrets.yaml from tracking"
   ```

3. **Add and commit the security changes:**
   ```bash
   git add esphome/.gitignore
   git add esphome/SECURITY_SETUP.md
   git add esphome/generate_keys.py
   git add esphome/*/*.yaml  # All the refactored configs
   git commit -m "Security: Refactor all configs to use secrets.yaml"
   git push
   ```

### Option B: Make Repository Private

If this is personal infrastructure, consider making your GitHub repo private:
1. Go to repository Settings
2. Scroll to "Danger Zone"
3. Click "Change visibility" → "Make private"

---

## 📋 What Changed?

### Before (INSECURE):
```yaml
api:
  encryption:
    key: "FpSU4uWfdjSNc0dAxtMGojEgLKCgl6bhTWJxpMT6mXE="  # Exposed!
```

### After (SECURE):
```yaml
api:
  encryption:
    key: !secret boilercontrol_encryption_key  # Protected!
```

All sensitive credentials are now in `secrets.yaml`, which is:
- ✅ Excluded from Git via `.gitignore`
- ✅ Stored only on your local machine
- ✅ Used by ESPHome via `!secret` references

---

## ⚡ Quick Reference

### Devices and Their Secret Names

| Device | Encryption Key | OTA Password |
|--------|---------------|--------------|
| BoilerControl | `boilercontrol_encryption_key` | `boilercontrol_ota_password` |
| BedroomLights | `bedroomlights_encryption_key` | `bedroomlights_ota_password` |
| LoftC3 | `loftc3_encryption_key` | `loftc3_ota_password` |
| Downstairs | `downstairs_encryption_key` | `downstairs_ota_password` |
| FrontPath | `frontpath_encryption_key` | `frontpath_ota_password` |
| MiniDisplay | `minidisplay_encryption_key` | `minidisplay_ota_password` |
| ManifoldTemp | `manifoldtemp_encryption_key` | `manifoldtemp_ota_password` |
| KitchenDetectorer | `kitchendetectorer_encryption_key` | `kitchendetectorer_ota_password` |
| Loft Display | `loft_encryption_key` | `loft_ota_password` |
| BioOfficeC3 | `bioofficec3_encryption_key` | `bioofficec3_ota_password` |

---

## 🆘 Troubleshooting

### "File secrets.yaml not found"
Make sure `secrets.yaml` is in `c:\dev\MiniDisplay\esphome\` (same directory as your device folders).

### "Connection refused" or "Invalid encryption key"
You need to flash via USB first after changing the encryption key, then reconfigure in Home Assistant.

### Device won't connect after update
1. Double-check you copied the correct encryption key into Home Assistant
2. Verify secrets.yaml has no typos in the key name
3. Try compiling with `esphome compile <file>.yaml` to check for errors

### Git is still tracking secrets.yaml
```bash
# Remove from Git tracking (keeps local file)
git rm --cached esphome/secrets.yaml
git commit -m "Stop tracking secrets.yaml"
git push
```

---

## ✅ Security Checklist

- [ ] Generated new encryption keys for all devices
- [ ] Generated new OTA passwords for all devices
- [ ] Updated secrets.yaml with all new credentials
- [ ] Flashed all 10 devices via USB with new configs
- [ ] Reconfigured all devices in Home Assistant
- [ ] Verified secrets.yaml is NOT in git tracking
- [ ] Committed and pushed the refactored configs (without secrets.yaml)
- [ ] Deleted old compromised keys from GitHub history (optional, advanced)

---

## 🎯 Why This Matters

**API Encryption Keys** protect communication between your ESP devices and Home Assistant. A compromised key allows an attacker to:
- Read sensor data
- Control lights, switches, and other devices
- Potentially exploit vulnerabilities

**OTA Passwords** protect firmware updates. A compromised password allows an attacker to:
- Upload malicious firmware
- Permanently brick devices
- Create backdoors in your network

**Now your credentials are:**
- ✅ Not in your public GitHub repo
- ✅ Fresh and uncompromised
- ✅ Properly secured via secrets.yaml

---

Good luck! Once you've completed all steps, your ESPHome setup will be properly secured. 🔒

