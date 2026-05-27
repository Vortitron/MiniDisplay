# Hot Water Boiler – Price-Optimised Control

## Boiler specs

- **Power:** 1500W
- **Capacity:** 100 litres (closed boiler, pipe-mounted temperature sensor)
- **Full cold reheat** (15°C → 60°C): ~5.2 kWh → **3.5 hours**
- **Post-shower reheat** (~25°C → 55°C): ~3.5 kWh → **2.3 hours**
- **Nightly maintenance** (with standing losses): **~2.5 hours**

## Automations

### `HotWater.yaml` — deterministic daily schedule

Computes the heating schedule directly from today's Nordpool hourly prices, splitting the day into two independent windows so there is always guaranteed overnight reheat.

#### Heating rules (evaluated in order)

| Condition | Result | Rationale |
|---|---|---|
| Manual override active (2h timer) | **ON** | Respect manual switch-on |
| Holiday mode on | **OFF** | Nobody using hot water |
| **Sunday** | **ON all day** | Weekend comfort |
| **Saturday**, current hour < 19 AND not in 4 most expensive hours of 00:00–18:59 | **ON** | Always-hot weekend, but skip peaks |
| **Saturday**, current hour ≥ 19 | **OFF** | Sunday's all-day rule kicks in at midnight |
| **Weekday** — current hour is one of the **2 cheapest hours in 00:00–05:59** | **ON** | Guaranteed overnight reheat |
| **Weekday** — current hour is one of the **4 cheapest hours in 06:00–23:59** | **ON** | Daytime top-up |
| **Weekday** — `hot_water_notified` is on AND it's before 18:00 AND current hour is one of the **2 cheapest hours in [now, 18:00)** | **ON** | Ensure hot water in time for evening |
| **Weekday deadline safety** — `hot_water_notified` is on and remaining reheat minutes are now greater than/equal to minutes left before 18:00 | **ON** | Prevents waiting too long for cheap slots and missing evening hot water |
| Otherwise | **OFF** | Save money |

Weekday base schedule: **6 hours of heating per day**, always at the cheapest prices within each window, **always at least 2 overnight**.

Saturday: ~15 hours of heating (00:00–18:59 minus the 4 most expensive). Weekend usage is heavier and less predictable, so the boiler stays warm except during the worst peaks.

When a shower has emptied the tank (`hot_water_notified` on), the weekday pre-evening rule adds up to 2 more hours of heating before 18:00, picked from the cheapest hours still ahead in the day. A deadline safety override forces heating once there is no longer enough time left to delay.

#### Why split into two windows?

Previously the automation used `input_number.electricity_price_rank < 6` combined with an "overnight" (21:00–06:00) time range. This had a critical bug:

1. The rank is computed over **today's 24 hours only**.
2. If today's cheapest hours were at midday, then overnight hours ranked *above* 6 — they weren't in the top 6 of the day.
3. So the "overnight + rank < 6" rule never fired, even though electricity overnight was absolutely cheap.
4. Result: **no overnight heating**, water still cold when the next shower came.

Computing the 2 cheapest hours within the 00:00–05:59 window guarantees that the 2 overnight hours *always* get selected, regardless of how expensive they are relative to midday. The 4 cheapest of 06:00–23:59 still captures any daytime bargains.

#### Fallback (Nordpool data unavailable)

The automation now auto-detects Nordpool slot resolution (hourly, 30-minute, or 15-minute) and normalises it into hourly buckets before ranking.

If there is still insufficient data (fewer than 20 hour buckets), fallback is:

- `hot_water_notified` on and before 18:00: **heat now** (do not postpone reheat on missing price data)
- otherwise: **01:00–04:00** conservative safety schedule

#### Manual override (2h)

Two ways to force the boiler ON for 2 hours regardless of schedule:

1. **Boost button** (`input_button.hot_water_boost_2h`) — owned by `HotWaterBoost.yaml`. Press it from any dashboard/voice/automation to set `input_datetime.hot_water_manual_override_until = now + 2h` and turn the switch on. This is the primary, explicit mechanism.

2. **Switch toggle fallback** (in `HotWater.yaml`) — if `switch.smart_plug_2_socket_1` goes from off → on during a scheduled-OFF hour and no override is currently active, an override is automatically applied for 2h. This catches manual toggles via any source: dashboard switch card, physical button on the smart plug, voice, third-party integrations, etc.

The detection logic is **schedule-based, not `user_id`-based**:

- When the automation itself turns the switch on, the schedule already says ON, so the override is **not** applied (no self-loop).
- When someone toggles the switch externally during an OFF hour, the schedule says OFF, the new state is ON — must be external → override applied.
- Toggling on during a cheap hour (when schedule says ON anyway) does nothing extra; the schedule continues normally. If you want to extend past the cheap hour, press the boost button.

The previous version used `context.user_id is not none` to detect manual clicks, but that fails for physical buttons on the smart plug and some integrations, leading to "switch turns on then immediately off again" bugs.

#### Reliability check

After turning the plug on, the automation waits 1 minute then checks if it actually switched on. If it's still off, a persistent notification is raised ("Hot Water Not Reacting — Alarm: 2").

### `HotWaterTemperature.yaml` — shower detection

Monitors `sensor.manifoldtemperature_hot_water_boiler_temp` (pipe-mounted sensor on the closed boiler):

- **Stays above 40°C for 3 minutes** → sets `input_boolean.hot_water_notified` on (sustained hot draw = real shower / dishes / extended use, not a brief hand-rinse)
- **Drops below 20°C for 10s** alarm trigger exists but is currently disabled in YAML

The pipe sensor reliably detects sustained hot-water flow (pipe stays warm only while water is moving through). A brief hand-rinse will not usually keep the pipe above 40°C for 3 minutes, so it distinguishes heavier usage from incidental flow.

### `HotWaterReheatTracker.yaml` — flag clearing after reheat

Decouples the flag from instantaneous pipe state. Once the flag is set, it can only be cleared by **2 cumulative hours of boiler heating**:

1. When `hot_water_notified` turns on → set `input_number.hot_water_reheat_minutes_remaining = 120`
2. Every minute, if flag is on **and** boiler switch is on → decrement counter by 1
3. When counter reaches 0 → clear flag

This means:
- The flag survives someone washing hands mid-reheat (which used to clear it prematurely with the old "warm pipe" clear logic).
- Heating accumulates across windows — e.g. 2h overnight + 1h pre-evening counts as 3h total.
- HA restarts pause the counter (no fake heating credit during downtime).
- Holiday mode pauses the counter (boiler isn't running).

`input_boolean.hot_water_notified` drives the **pre-evening reheat rule** in `HotWater.yaml`: while the flag is on and current time is before 18:00, the automation finds the 2 cheapest hours remaining in [now, 18:00) and heats during those. The flag clears automatically once 2 cumulative hours of heating have happened, so the rule disengages exactly when the tank should be full again.

For unscheduled urgent hot water, use the manual override (2h boost via button/switch).

## Holiday mode

When `input_boolean.holiday_mode` is on:
- Sunday all-day and Saturday extended heating are **disabled**
- All scheduled heating is **disabled**
- Manual override still works (e.g. for the day you return home)

If you'll be away for more than 2 weeks, consider a manual boost before returning to avoid legionella risk.

## Triggers

`HotWater.yaml` re-evaluates on:

- **Every 15 minutes** (time pattern — primary driver)
- `sensor.nordpool_kwh_se4_sek_3_10_025.raw_today` change (new day, new prices)
- `input_boolean.holiday_mode` change
- `input_boolean.hot_water_notified` change (for logging context)
- `switch.smart_plug_2_socket_1` turning on (manual override detection)

## Dependencies

- `switch.smart_plug_2_socket_1` (boiler smart plug)
- `sensor.manifoldtemperature_hot_water_boiler_temp`
- `sensor.nordpool_kwh_se4_sek_3_10_025` (hourly price data via `raw_today`)
- `input_boolean.hot_water_notified`
- `input_boolean.holiday_mode`
- `input_button.hot_water_boost_2h`
- `input_number.hot_water_reheat_minutes_remaining`
- `input_datetime.hot_water_manual_override_until`

## Expected daily pattern (example)

With typical Swedish prices (cheap overnight, peak 07:00–09:00 and 17:00–20:00, mid-day moderate):

### Weekday

| Time | Typical behaviour |
|---|---|
| 00:00–02:00 | Usually not cheapest overnight hours |
| 02:00–04:00 | Often the **2 cheapest overnight hours** → **ON** for reheat |
| 04:00–06:00 | Off (overnight quota filled) |
| 06:00–10:00 | Expensive peak → off |
| 10:00–15:00 | Usually the **4 cheapest daytime hours** → **ON** if today's price curve puts a dip here |
| 15:00–20:00 | Expensive peak → off |
| 20:00–00:00 | Off |

### Saturday

| Time | Typical behaviour |
|---|---|
| 00:00–07:00 | Usually **ON** (cheap overnight, definitely not in 4 most expensive) |
| 07:00–09:00 | Likely **OFF** (morning peak — typically 1–2 of the 4 most expensive hours) |
| 09:00–17:00 | Mostly **ON** with maybe one off-hour at midday peak |
| 17:00–19:00 | Likely **OFF** (evening peak — typically the rest of the 4 most expensive) |
| 19:00–00:00 | **OFF** (Sunday all-day takes over at midnight) |

### Sunday

ON all day (unless holiday mode).

Actual schedule depends on the day's price curve — check the logbook entries for the specific hour lists chosen.
