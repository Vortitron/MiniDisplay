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
| Otherwise — evening included | **16 °C** |

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

## Dashboards

- **Sam & Energy** (`dashboard_sam_energy.yaml`): a *Bio2 — bio hall heat pump*
  section (headline, thermostat, desired/lock/projector/energy today, the three
  temperatures), and the bio hall on the temperature graph.
- **Energy dashboard**: device *Bio2 HVAC* on `sensor.bio2_daily_energy`
  (the integration's own kWh counter; its power sensor is `unavailable`, so the
  generated `sensor.bio2_current_energy` never counted).

## Files

- `Bio2Hvac.yaml` — the automation (`id: bio2_hvac`), `mode: queued`.
- `tests/test_bio2_hvac_templates.py` — renders the desired ladder and heat
  maths straight out of the YAML (HA-style `round`, pinned `now()`).
- `deploy_bio2_hvac.py` — deploy via VomeHome.
