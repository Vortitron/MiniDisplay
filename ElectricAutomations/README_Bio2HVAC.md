# Bio2 HVAC (bio hall) — temporary heat pump, same tricks as Sam

`Bio2Hvac.yaml` drives **`climate.bio2`**, a Panasonic heat pump (same cloud
integration as Sam) wired in temporarily in the bio hall — the room next to
Sam that the circulation fan blows Sam's warm air into. One automation does
the job of Sam's pair (`DaytimeCheapHeat.yaml` + `sam.yaml`), without the
electricity-price ladder: a film room is either in use or it is not.

## Room temperature

The unit's own sensor sits near the ceiling and reads what it is blowing, so
the room is read from the ESPHome wall sensor there,
**`sensor.bedroomlights_bedroomlights_temperature`** (the "bedroom" sensor of
`sam.yaml` and the circulation fan — same room, older name).

Bio2's setpoint is placed relative to its **own** reading so that it heats
while the wall sensor is below target and idles when the room is there —
exactly `sam.yaml`'s heating maths (`internal + max(1, need)` when cold,
`internal − 2` or lower when at/above target, `fan_only` more than 3 °C above
target or when it is warmer outside than wanted, clamped to the unit's 16–30 °C
on its 0.5 step). With the wall sensor down it runs as its own thermostat at
target + 2 (`Bio2 sensor only`).

## What it wants — `input_number.bio2_desired_temperature`

| Condition (in order) | Desired |
|---|---|
| **Holiday mode** | **10 °C** (`heat_8_15` preset, frost protection) |
| **You set it** (helper differs from `input_number.bio2_automation_set_value`, or `input_datetime.bio2_desired_lock_until` is in the future) | **Kept as-is for 90 min** — same lock as Sam |
| **Projector playing or paused** (`input_select.bio_projector`, from `BioProjectorLights.yaml`) | **20 °C** |
| **Andy's phone in the bio, 07:00–23:00** (`input_select.phone_zone` = `bio`, from `PhoneZone.yaml`) | **20 °C** |
| **Pre-warm run-up**: within `hours_needed` of `input_datetime.bio_film_time` (20:00) | **20 °C**, whatever the price |
| **Bank heat** (spot feed only): earlier than that, power now ≥ 15 % cheaper than the run-up average, and the banked heat still 20 °C at film time | **up to 26 °C** |
| Otherwise — evening included | **16 °C** |

## Pre-warming for film time (Oct 2026)

One heater takes hours to lift this room, and on spot days the run-up to
20:00 is the dearest part of the day. So Bio2 plans backwards from
**`input_datetime.bio_film_time`** (20:00; `input_boolean.bio_prewarm_enabled`
switches the planning off):

1. **`BioThermalModel.yaml`** learns the room the way `HouseThermalModel.yaml`
   learns the house — every 10 minutes, **k** (loss, 1/h) while Bio2 is idle and
   **h** (°C/h) while it reports heating, EMA α 0.05 — into
   `input_number.bio_heat_loss_k` / `bio_heat_rate` / `bio_thermal_tau` and
   `bio_hours_to_target` (hours of heating to reach 20 °C at the 4 h forecast).
   Seeded at k 0.2, h 2.0; give it a few days of films and idle nights.
2. **Plain run-up.** `hours_needed = ln((Teq − T)/(Teq − 20))/k` with
   `Teq = Tout_forecast + h/k`. Inside that lead (capped at
   `prewarm_max_lead_h` 4 h when the model says 20 °C is out of reach) the
   desired is 20 °C regardless of price. Reason `Pre-warm for 20:00`.
3. **Banking on cheap power.** Earlier than the run-up, if the price now is at
   least `bank_margin` (15 %) below the average 15-minute price over the plain
   run-up window, Bio2 heats to `bank_target = Tout + (20 − Tout)·e^(k·t)`
   (capped at `prewarm_max` 26 °C), the temperature that leaks back to exactly
   20 °C at film time. This is only offered while `t ≤ bank_horizon_h =
   ln((26 − Tout)/(20 − Tout))/k`: heat banked earlier is gone by 20:00.
   **With the seed k of 0.2 and 8 °C out that horizon is about two hours**
   (four at k 0.1), so how far back banking reaches depends on what the model
   learns. The cap was 23 °C on day one; 26 °C doubles the reach for about a
   third more leakage over a couple of hours, at a fraction of the price.
   Reason `Bank heat 22°C (cheap)`.

**Only on the spot feed.** Banking is gated on
`input_boolean.on_fixed_price_feed` being **off** (`FeedDetect.yaml` sets it from
the two P1 meters — see `README_FixedPriceSwap.md`). On the monthly fixed price
the timing of a kWh buys nothing and holding 26 °C leaks more than holding
20 °C, so banking would be pure loss. The **run-up is price-blind and runs on
either feed**: being warm by film time is comfort, not economy. Flip
**`input_boolean.bio_bank_test_on_fixed`** to exercise banking on the fixed feed
anyway (`fixed=True+test` in the working line); turn it off afterwards.

`input_text.bio2_preheat_calc` shows the working on the dashboard (hours,
prices, horizon, feed, which rule fired). Tests: `test_prewarm_window_*`,
`test_bank_heat_*` in `tests/test_bio2_hvac_templates.py`.

Sam's living room goes to 20 °C every evening; the bio hall does not. With
the projector off nobody is in there, so it goes low whatever the time.

**Super-expensive electricity** (`input_boolean.super_expensive_active`):
Bio2 is switched **off** while the room is above its target (it would only be
idling). At or below target, or with the room sensor down, it keeps going.

## When Bio2 is not there — Sam's job

`climate.bio2` goes `unavailable` on cloud drops (01:03–03:20 on 20 Oct 2026)
and when the unit is unplugged again. Then:

- `Bio2Hvac.yaml` keeps the desired helper and headline up to date
  (`Bio2 unavailable · Sam covers`) and touches nothing.
- `sam.yaml` reads **min(living, bio hall)** with the circulation fan running,
  as before, so Sam warms the room from next door.
- `BioProjectorLights.yaml` raises **Sam's** desired to 20 °C on film start.

While Bio2 **is** available, `sam.yaml` reads the living room alone
(`bio2_live`; status says `via living (Bio2 live)`), and the projector raises
Bio2's room instead through its own trigger. Sam's heating is otherwise
unchanged — the `BILRESA` bio button still bumps Sam when the bio lights go on.

If the Panasonic cloud keeps reporting the unit after it has been unplugged,
disable the `Bio2 HVAC (bio hall)` automation; `states('climate.bio2')` is the
only "is it there" signal.

## Helpers (storage, made over MCP — not in `helpers.yaml`)

| Helper | Settings |
|---|---|
| `input_number.bio2_desired_temperature` | 10–30, step 1, °C |
| `input_number.bio2_automation_set_value` | 10–30, step 0.1, °C — last value the automation wrote; hide it |
| `input_datetime.bio2_desired_lock_until` | date + time |
| `input_text.bio2_hvac_headline` | max 64 — `reason · action` |
| `input_text.bio2_hvac_status` | max 255 — diagnostic detail |
| `input_text.bio2_preheat_calc` | max 255 — pre-warm working |
| `input_datetime.bio_film_time` | time only, 20:00 |
| `input_boolean.bio_prewarm_enabled` | on |
| `input_boolean.bio_bank_test_on_fixed` | off — lets banking run on the fixed feed, for testing |
| `input_number.bio_heat_loss_k`, `bio_heat_rate`, `bio_thermal_tau`, `bio_thermal_last_inside`, `bio_thermal_last_outside`, `bio_hours_to_target`, `input_datetime.bio_thermal_last_sample`, `input_text.bio_thermal_status` | the bio thermal model (no `initial:` — learned values must survive restarts) |

## Dashboards

- **Sam & Energy** (`dashboard_sam_energy.yaml`): a *Bio2 — bio hall heat pump*
  section (headline, thermostat, desired/lock/projector/energy today, the three
  temperatures), and the bio hall on the temperature graph.
- **Energy dashboard**: device *Bio2 HVAC* on `sensor.bio2_daily_energy`
  (the integration's own kWh counter; its power sensor is `unavailable`, so the
  generated `sensor.bio2_current_energy` never counted).

## Files

- `Bio2Hvac.yaml` — the automation (`id: bio2_hvac`), `mode: queued`.
- `BioThermalModel.yaml` — the room's k / h / τ learner (`id: bio_thermal_model`).
- `tests/test_bio2_hvac_templates.py` — renders the desired ladder and heat
  maths straight out of the YAML (HA-style `round`, pinned `now()`).
- `deploy_bio2_hvac.py` — deploy via VomeHome.
