# Super-Expensive load shedding

Demand-response "super expensive" mode. When the electricity **base price**
rises above a threshold it switches off non-essential loads, and releases them
when the price drops back.

- Automation: `SuperExpensive.yaml` (entity `automation.super_expensive_load_shedding`)
- Guard in `sam.yaml` switches the heat pump off when it is just idling.
- Tests: `tests/test_super_expensive.py`
- Tunables/state are Home Assistant helpers (created via the API, like the other
  helpers here — `helpers.yaml` is reference only).
- **Disabled on the fixed-price feed:** when `input_boolean.on_fixed_price_feed`
  is on, this mode never activates (and releases if active). See
  `README_FixedPriceSwap.md`.

## Price signal

| Setting | Value |
| --- | --- |
| Base-price sensor | `sensor.nordpool_kwh_se4_sek_3_10_0` (Nordpool SE4 spot **ex-VAT**, +0.10 markup) |
| Threshold | `input_number.super_expensive_threshold` (default **2.0 SEK/kWh**) |
| Hysteresis | latches on at/above the threshold; only releases below `threshold − 0.15` |

The threshold is the *ex-VAT* base price ("2 SEK base price"). For the
VAT-inclusive price use `sensor.nordpool_kwh_se4_sek_3_10_025`, or the all-in
`sensor.adjusted_nordpool_se4`.

## Helpers

| Entity | Purpose | Default |
| --- | --- | --- |
| `input_number.super_expensive_threshold` | base-price trip point (SEK/kWh) | 2.0 |
| `input_boolean.super_expensive_active` | current mode state (auto-set) | off |

`input_boolean.super_expensive_active` is the single source of truth — set by the
automation, read by `sam.yaml` and the dashboard.

## What it sheds while active

Everything in `shed_entities` is switched off (re-asserted every 5 min in case
another automation switches it back on), via `homeassistant.turn_off` so it works
across domains (climate → off, lights/switches → off):

| Entity | What |
| --- | --- |
| `switch.t34_smart_plug_switch_1` | Loft Wet humidifier |
| `switch.smart_plug_5_socket_1` | circulation fan (Tuya plug; `sam.yaml` drives it directly during cooling, so we shed the switch, not the `climate.circulation_fan` thermostat) |
| `switch.smart_plug_4_socket_1` | pool pump + heater (`PoolPump.yaml`) |
| `climate.bio_office_heat` | Bio office heater (often unplugged) |
| `light.led_flood_light` | LED flood light |
| `light.bio_floodlight` | Bio flood light |

Plus **`climate.sam`** — handled by `sam.yaml`'s own guard: Sam is switched off
**only when it is just idling**, i.e. the living room is **above 19 °C**
(`super_expensive_off_above`). At/below 19 °C — or if the living temperature is
unknown — Sam is left running, because it may be actively heating. Holiday mode
still wins over super-expensive.

Already-off or unavailable entities are skipped (no error, no log noise).

## On exit

Loads are simply **released** — nothing is forced back on. Their own
automations/schedules (CirculationFan, BioOffice heating, Loft Wet on/off, light
schedules) restore them when actually needed, so nothing is spuriously energised.

## Not shed

- **Hot water** (`switch.smart_plug_2_socket_1`): already price-gated by
  `HotWater.yaml` (heats only in the cheapest hours), so effectively off when
  expensive. (Edge case: a uniformly expensive day — add a hard price-cap to
  `HotWater.yaml` if that ever matters.)
- **The server**: not currently sheddable. It is no longer on a switched plug,
  ESXi 6.5 SNMP is intentionally disabled (a known 6.5 vulnerability; 6.5 is the
  newest the Dell R620 supports), and the iDRAC (`192.168.1.223`) can only power
  the whole host — it cannot selectively drop one PSU's mains feed. Revisit if a
  PSU feed goes back on a switched outlet (then a smart-plug cut, gated on a
  "≥2 healthy PSUs" read, could shift the server load to the fixed-price PSU).

## Tests

```
python3 ElectricAutomations/tests/test_super_expensive.py
```

Covers the hysteresis (enter/hold/release), the shed-list filter (only switches
off what is currently on, across domains), and the `sam.yaml` "off only when
idling (>19 °C)" guard.

## Files
- `ElectricAutomations/SuperExpensive.yaml` — the automation
- `ElectricAutomations/sam.yaml` — the heat-pump guard
- `ElectricAutomations/tests/test_super_expensive.py` — unit tests
