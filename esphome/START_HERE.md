# 🚨 URGENT: SECURITY UPDATE REQUIRED 🚨

## Your ESPHome credentials were exposed in a public GitHub repo!

### ⚡ Quick Start (5 minutes to secure):

1. **Generate new keys:**
   ```bash
   cd c:\dev\MiniDisplay\esphome
   python generate_keys.py
   ```

2. **Copy output into `secrets.yaml`** (replace all GENERATE_NEW_* placeholders)

3. **Flash ONE device via USB to test:**
   ```bash
   cd BoilerControl
   esphome run BoilerControl.yaml
   ```

4. **Reconfigure in Home Assistant:**
   - Settings → Devices & Services → ESPHome
   - Find "BoilerControl"
   - Click RECONFIGURE
   - Enter the new encryption key from secrets.yaml

5. **Repeat for remaining 9 devices**

---

📖 **Full instructions:** See [SECURITY_SETUP.md](SECURITY_SETUP.md)

---

## What was fixed?

✅ Created `secrets.yaml` for all sensitive credentials  
✅ Updated all 10 device configs to use secrets  
✅ Created `.gitignore` to prevent future exposure  
✅ Provided key generation script  

## What YOU must do:

⚠️ Generate fresh encryption keys (old ones are compromised)  
⚠️ Flash updated configs to all devices  
⚠️ Update Home Assistant with new keys  
⚠️ Commit changes to GitHub (secrets.yaml will be excluded)  

---

**Time required:** ~5 min setup + ~5 min per device = ~1 hour total

**Don't panic!** Your devices still work with old keys temporarily. But update them ASAP to prevent potential security issues.

