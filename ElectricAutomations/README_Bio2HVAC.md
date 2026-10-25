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
| **Bank heat** (opt-in, spot feed only, empty room): earlier than that, power now ≥ 15 % cheaper than a run-up that is itself expensive, and the banked heat still 20 °C at film time | **up to 22 °C** |
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
3. **Banking on cheap power — opt-in, and deliberately hard to fire.** Earlier
   than the run-up, Bio2 may heat to `bank_target = floor + (20 − floor)·e^(k·t)`
   (capped at `prewarm_max` **22 °C**), the temperature that leaks back to
   exactly 20 °C at film time, while `t ≤ bank_horizon_h =
   ln((22 − floor)/(20 − floor))/k`. Every one of these must hold:

   - **`input_boolean.bio_bank_enabled` is on.** Default **off** — see the
     25 Oct incident below.
   - **The room is empty**: projector off and `input_select.phone_zone` not
     `bio`. Banking exists to be coasted down from, not sat in.
   - **The run-up is genuinely expensive**: its average ≥ `bank_min_window_avg`
     (0.6 SEK/kWh), as well as the 15 % `bank_margin` below it.
   - **The spot feed** (or the test switch).

   **`floor` is the coast-down floor, `max(outdoor forecast, living room)`.**
   The bio hall is an internal room: it cools toward the heated house, not
   outdoors. With the living room at the 20 °C film target the horizon is zero
   and banking never fires, which is correct — there is nowhere to coast to.
   That also means the 2 °C of headroom between 20 and the 22 °C cap buys only
   about 1.8 h of shift at k = 0.1, so banking is a marginal trick in this
   room. The run-up is the half that earns its keep.

### 25 Oct 2026 — banking cooked the room

Spot was near zero all day (0.055 SEK/kWh against a 0.42 run-up average), the
percentage margin passed, and banking drove the desired to **26 °C** from 12:48
while Andy was working in there. The wall sensor never read above **20.6 °C**,
but with the fooled setpoint an unreachable target makes Bio2 run at **full
output** for hours — it was on the `powerful` preset with the fan on `High`
pointing down — so the room was unbearable long before the air temperature got
anywhere near the target. Doors had to be opened. Total saving at stake: about
2 SEK.

Four things were wrong and all four are now guarded: no occupancy check, a
ceiling (26 °C) far above anything habitable, a purely *relative* price test
that fires when power is already nearly free, and a coast-down referenced to
the outdoor temperature for a room that cools toward the house. Banking is also
off by default now. The preset and fan were returned to `none` and `Auto`.

### Airing, and two learning biases (25 Oct 2026)

The bio hall has **two external doors** and gets opened for fresh air. That
broke the learner in a way worth recording, because both failures are generic:

- **Open doors poisoned `k`.** Aired, the room fell about **6 °C/h**, which
  against a 10 °C ΔT looks like `k = 0.6`. The old bounds (0.01–2.0) accepted
  it, so every 10-minute sample dragged `k` up by ~0.02: **0.064 → 0.124 in
  twenty minutes**. Left alone it would have reached 0.4 within hours, which
  collapses `Teq` and makes the planner pre-warm for the maximum lead every
  single day.
- **Holding at target poisoned `h` downward.** At steady state `dT/dt ≈ 0`, so
  the observation degenerates to `k·ΔT` — "whatever maintains this
  temperature", not the unit's capacity. `h` drifted **2.0 → 1.32** over five
  days, dropping `Teq` to ~20.8 and making the planner believe 20 °C was only
  just reachable, when Bio2 had in fact lifted the room 14 → 18.3 °C in an
  afternoon.

Three guards: **`input_boolean.bio_ventilating`** stops sampling altogether and
turns Bio2 **off** (heating with the doors open just warms the garden, and the
headline reads `Airing · Off`); `max_k` is 0.5, since an internal room cannot
lose heat faster; and any observation more than `k_outlier_factor` (2.5×) from
the running estimate is **rejected rather than blended**, which the status line
marks `REJ`. `h` is now only learned while the room is actually rising at least
`min_rise_for_h` (0.3 °C/h). `k` and `h` were reset to 0.15 and 2.0 afterwards,
since both were corrupted and the sensor had moved.

> **The wall sensor is not representative.** It peaked at 20.6 °C over four days
> while the room felt far too warm, and it read low even after being moved to
> the middle of the room. Every decision here is computed from it, so treat its
> absolute value with suspicion until a second sensor at seat height confirms
> it. Moved to where people actually sit it read **23 °C while the old spot
> read 20.4** — a 2.5 °C gradient, so the target now means something different
> from what it meant before the move.
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
| `input_boolean.bio_bank_enabled` | **off** — master switch for banking |
| `input_boolean.bio_ventilating` | off — doors open: Bio2 off, no model sampling |
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
