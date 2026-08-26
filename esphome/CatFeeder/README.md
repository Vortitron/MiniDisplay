# Cat Feeder RFID Door

RFID-controlled door for a cat feeder. One cat is authorised initially; more tags can be added later.

## Hardware

| Part | Notes |
|------|-------|
| ESP32-32E dual MOS board | 12 V DC input recommended; onboard MOSFET switches for loads |
| RDM6300 (HW-205) | 125 kHz RFID, UART 9600 baud |
| Electromagnetic lock | **Pulse only** — energise briefly to unlock; spring re-locks when power off |
| Flyback diode | **Required** — e.g. 1N4007 or 1N5819 across the lock coil |

### Flyback diode (important)

The lock is an inductive coil. When current stops, the coil generates a voltage spike that can destroy the onboard MOSFET.

```
        12V ----[ MOS switched output ]----+
                                            |
                                      [ LOCK COIL ]
                                            |
        GND -------------------------------+

        Diode (1N4007): stripe (cathode) -> lock + side
                          no stripe (anode) -> lock - side
```

Place the diode **directly across the lock wires**, cathode on the positive side. Polarity of the lock power wires does not matter for the lock itself (per seller), but the diode orientation does.

### Power

- Run the ESP board from **12 V DC** on its DC input (recommended in the product manual).
- The MOS outputs switch at the input voltage (up to ~60 V), so the lock can be powered from the same 12 V rail through **OUT1**.
- RDM6300: **5 V** on VCC if you have a 5 V header; **3.3 V** also works on many modules but gives shorter read range.

## Wiring

### RDM6300 → ESP32 header

| RDM6300 | ESP32 board |
|---------|-------------|
| VCC | 5 V (or 3.3 V) |
| GND | GND |
| TX | **GPIO16** (`rfid_rx_gpio` in YAML) |
| RX | not connected |
| ANT1 / ANT2 | Coil antenna (included) |

Mount the antenna where the cat's collar tag passes close (a few cm).

### Electromagnetic lock → onboard MOS (channel 1)

| Lock wire | Board |
|-----------|-------|
| Either wire | OUT1 switched + |
| Other wire | OUT1 − / common return |

Add the flyback diode across the coil as above.

**Do not** leave the lock energised. The YAML pulses it for 600 ms then turns off.

### GPIO map (verify on your board)

This AliExpress ESP32-32E MOS board typically uses:

| Function | GPIO | Notes |
|----------|------|-------|
| MOS output 1 (lock) | **GPIO25** | “First output” on PCB |
| MOS output 2 (spare) | **GPIO27** | “Second output” |
| Status LED | GPIO23 | Onboard |
| Boot / mode button | GPIO0 | Short with GND for flash mode |

**Verify before mounting:** power from 12 V, press the mode button until the **first** MOS turns on (LED ~50 %). Measure which output is live, or temporarily set `lock_gpio` in the YAML and use the **Unlock Feeder Door** button in Home Assistant.

If GPIO25 is wrong, try GPIO27 and update `lock_gpio` in `CatFeeder.yaml`.

## ESPHome setup

1. Add secrets to `esphome/secrets.yaml`:

```yaml
catfeeder_encryption_key: "<generate with generate_keys.py>"
catfeeder_ota_password: "<your OTA password>"
```

2. Flash:

```bash
cd esphome
esphome run CatFeeder/CatFeeder.yaml
```

3. **Learn the cat's tag ID:** hold the collar tag near the reader and watch the **Last RFID Tag** entity or logs for `RFID tag XXXXX`.

4. Set `cat1_uid` in `CatFeeder.yaml` to that number (decimal, no quotes in the substitution value except the YAML string).

5. Reflash or OTA update.

## Behaviour

- Authorised tag scanned → 600 ms unlock pulse → lock de-energises → spring locks door.
- 3 s cooldown between unlocks (stops repeated reads while the cat eats).
- `Unlock Feeder Door` button in HA for manual testing.
- `homeassistant.tag_scanned` is sent for every tag (useful for HA automations later).
- `Authorised Cat Present` stays on while the tag is in the field (with 2 s delayed off).

## Tuning

| Setting | Location | Default |
|---------|----------|---------|
| Unlock pulse length | `unlock_pulse_ms` | 600 ms — increase if the bolt does not retract fully |
| Cooldown | `unlock_cooldown` | 3000 ms |
| RFID RX pin | `rfid_rx_gpio` | GPIO16 |

## Adding more cats later

Duplicate the `if` block in `rdm6300.on_tag` for each UID, or switch to a list in a `lambda` and add one `binary_sensor` per cat.

## Safety

- Electromagnetic locks **overheat** if powered continuously — the config enforces a short pulse only.
- Use a fuse on the 12 V feed if the lock draws significant current.
- Keep RFID antenna and lock wiring away from the 12 V switching paths where possible.
