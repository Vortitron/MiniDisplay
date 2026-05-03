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
| Manual override active (3h timer) | **ON** | Respect manual switch-on |
| Holiday mode on | **OFF** | Nobody using hot water |
| Sunday | **ON all day** | Weekend comfort |
| Current hour is one of the **2 cheapest hours in 00:00–05:59** | **ON** | Guaranteed overnight reheat |
| Current hour is one of the **4 cheapest hours in 06:00–23:59** | **ON** | Daytime top-up |
| `hot_water_notified` is on AND it's before 18:00 AND current hour is one of the **2 cheapest hours in [now, 18:00)** | **ON** | Ensure hot water in time for evening |
| Otherwise | **OFF** | Save money |

Total base schedule: **6 hours of heating per day**, always at the cheapest prices within each window, **always at least 2 overnight**.

When a shower has emptied the tank (`hot_water_notified` on), the pre-evening rule adds up to 2 more hours of heating before 18:00, picked from the cheapest hours still ahead in the day. This rule auto-disengages once warm water is drawn (the pipe sensor sees >30°C and clears the flag).

#### Why split into two windows?

Previously the automation used `input_number.electricity_price_rank < 6` combined with an "overnight" (21:00–06:00) time range. This had a critical bug:

1. The rank is computed over **today's 24 hours only**.
2. If today's cheapest hours were at midday, then overnight hours ranked *above* 6 — they weren't in the top 6 of the day.
3. So the "overnight + rank < 6" rule never fired, even though electricity overnight was absolutely cheap.
4. Result: **no overnight heating**, water still cold when the next shower came.

Computing the 2 cheapest hours within the 00:00–05:59 window guarantees that the 2 overnight hours *always* get selected, regardless of how expensive they are relative to midday. The 4 cheapest of 06:00–23:59 still captures any daytime bargains.

#### Fallback (Nordpool data unavailable)

If the Nordpool sensor has fewer than 20 hours of data (e.g. after integration restart), the automation falls back to heating **01:00–04:00** as a conservative safety schedule. This is enough for a full cold reheat.

#### Manual override

If someone physically turns on `switch.smart_plug_2_socket_1` via the HA UI, the automation detects a user-initiated change (non-null `context.user_id`), sets a 3-hour override timer (`input_datetime.hot_water_manual_override_until`), and won't turn the boiler off during that period.

When the automation itself turns the switch on, `context.user_id` is null, so the override path is not triggered — no self-retriggering loop.

#### Reliability check

After turning the plug on, the automation waits 1 minute then checks if it actually switched on. If it's still off, a persistent notification is raised ("Hot Water Not Reacting — Alarm: 2").

### `HotWaterTemperature.yaml` — shower detection

Monitors `sensor.manifoldtemperature_hot_water_boiler_temp` (pipe-mounted sensor on the closed boiler):

- **Drops below 20°C** (for 10s) → sets `input_boolean.hot_water_notified` on, sends notification ("Hot water, isn't.")
- **Rises above 32°C** (for 10s) → clears `input_boolean.hot_water_notified`

This reliably detects when someone has had a shower (pipe temp drops sharply as cold water is drawn through). It's less reliable for detecting when the tank has simply cooled over time, since the pipe sensor can't measure internal tank temperature.

`input_boolean.hot_water_notified` drives the **pre-evening reheat rule** in `HotWater.yaml`: if it's on and current time is before 18:00, the automation finds the 2 cheapest hours remaining in [now, 18:00) and heats during those. This ensures hot water is ready for an evening shower even if the day's cheapest 4 hours fall after 18:00.

The flag clears automatically once someone draws warm water (pipe sensor >30°C), so the rule disengages without needing extra plumbing.

For unscheduled urgent hot water, use the manual override (3h boost via the switch).

## Holiday mode

When `input_boolean.holiday_mode` is on:
- Sunday all-day heating is **disabled**
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
- `input_datetime.hot_water_manual_override_until`

## Expected daily pattern (example)

With typical Swedish prices (cheap overnight, peak 07:00–09:00 and 17:00–20:00, mid-day moderate):

| Time | Typical behaviour |
|---|---|
| 00:00–02:00 | Usually not cheapest overnight hours |
| 02:00–04:00 | Often the **2 cheapest overnight hours** → **ON** for reheat |
| 04:00–06:00 | Off (overnight quota filled) |
| 06:00–10:00 | Expensive peak → off |
| 10:00–15:00 | Usually the **4 cheapest daytime hours** → **ON** if today's price curve puts a dip here |
| 15:00–20:00 | Expensive peak → off |
| 20:00–00:00 | Off |

Actual schedule depends on the day's price curve — check the logbook entries for the specific hour lists chosen.
