# Fixed-Price Swap Advisor

Nudges you to switch the house supply between the **spot** feed (rörligt timpris,
15-min Nordpool pricing) and the **fixed-price** feed, and — once you have
swapped to fixed — **disables all the automations that optimise around the
15-min spot price** (since on a flat tariff the timing of usage no longer
matters).

The house has **two physical supply feeds, each with its own P1 power meter**, and
only one carries the load at a time:

| Feed | Meter | Tariff |
| --- | --- | --- |
| **Hem** | `sensor.hem_p1ib_active_power_a0b765527004` | **Monthly / fixed** price |
| **Bio** | `sensor.bio_p1ib_active_power_a0b7655105e0` | **Spot / 15-min** price |

You physically swap feeds; Home Assistant then **auto-detects** which one is live
from the two meters (see *How the feed is detected*) and sets
`input_boolean.on_fixed_price_feed` itself — no manual toggling needed.

## How the feed is detected

`FeedDetect.yaml` (runs every 2 min + on HA start) compares the two meters
(absolute kW, so solar export still counts as "active"):

- **Both meters available** — whichever leads by more than `deadband` (0.2 kW)
  wins; within the dead-band (e.g. both idle overnight) the **last decision is
  latched**, which stops flapping when the house is genuinely quiet.
- **One meter unavailable** (the P1 readers do drop out) — use the available one:
  clearly carrying load (≥ `load_kw` 0.4 kW) ⇒ that feed is live; clearly idle
  (< `idle_kw` 0.2 kW) ⇒ the *other* (unavailable) feed must be live; in between,
  hold.
- **Both unavailable** — hold.

On a real change it flips `input_boolean.on_fixed_price_feed`, logs it and posts a
single deduped persistent notification (`notification_id: feed_detect`).

## The idea

Compare the **upcoming 24 h** spot price against the **recent 30-day average**
(`input_number.spot_30d_avg`, a proxy for the monthly *rörligt pris*):

- **On spot** and the next-24 h average rises **above** the 30-day average by more
  than the margin → suggest swapping to the **fixed** feed.
- **On fixed** and the next-24 h average falls back **below** the 30-day average by
  the margin → suggest swapping **back to spot**.

Two ways of measuring "the next 24 h" are computed and **either** can trigger:

- **Flat** mean of the next 96 quarter-hour prices (`input_number.spot_next24h_avg`).
- **Usage-weighted** ("the way we use it") — each upcoming hour weighted by a
  typical household consumption profile (`input_number.spot_next24h_avg_weighted`).
  This lifts the figure when the dear hours line up with our heavy-use evening.

## Helpers

| Entity | Purpose |
| --- | --- |
| `input_boolean.on_fixed_price_feed` | **The switch (auto-set by `FeedDetect.yaml`).** ON = house is on the fixed feed → spot-price automations are disabled. |
| `input_number.spot_30d_avg` | Rolling 30-day average daily-mean spot price (base, ex-VAT) — the benchmark. |
| `input_number.spot_next24h_avg` | Flat mean of the next 24 h (published every run). |
| `input_number.spot_next24h_avg_weighted` | Usage-weighted mean of the next 24 h. |
| `input_number.fixed_swap_margin_pct` | Dead-band (default **10 %**) so borderline days don't nag. |
| `input_text.spot_daily_avg_history` | 30-slot ring buffer of daily means feeding `spot_30d_avg`. |
| `input_datetime.fixed_swap_last_suggested` | Throttle — at most one suggestion per day. |

## Automations

- **`FeedDetect.yaml`** (`feed_detect`) — auto-detects the live feed from the Hem
  vs Bio meters and sets `input_boolean.on_fixed_price_feed`. See *How the feed is
  detected* above.
- **`Spot30dAverage.yaml`** (`spot_30d_average`) — at 23:55 appends today's mean
  (the spot sensor's `average` attribute) to the ring buffer, trims to 30 and
  recomputes `spot_30d_avg`. On HA start it just recomputes (never double-counts).
  Seeded from long-term statistics, so it is useful immediately and converges to a
  true 30-day trailing mean of daily means. The comma-separated history string is
  parsed *inside* the `buf` template — assigning it to its own automation
  variable makes HA wrap it as a TupleWrapper, and `.split()` then fails.
- **`FeedSwapLightRestore.yaml`** (`feed_swap_light_restore`) — snapshots which
  lights are on (and how bright) every 5 min, and puts them back after a swap.
  See *Putting the lights back* below.
- **`FixedPriceSwapAdvisor.yaml`** (`fixed_price_swap_advisor`) — computes the
  next-24 h figures, publishes them, and sends a notification when a swap looks
  worthwhile (throttled once/day). Runs on tomorrow's prices publishing, a few
  fixed times, every 30 min, on relevant helper changes and on HA start. It only
  *advises* — `FeedDetect.yaml` does the actual flag-flip once you swap.
  **Needs a full 24 h of prices first:** it only compares/publishes once there are
  ≥ 96 upcoming quarter-hour slots. Nordpool publishes the next day at ~13:00, so
  before then there is less than 24 h ahead and the advisor waits rather than
  judging a partial day (which would skew the average toward whatever's left of
  today). The `raw_tomorrow` trigger makes it re-evaluate the moment tomorrow's
  prices land.

### Notify target

`FixedPriceSwapAdvisor.yaml` → `actions[0].variables.notify_service` =
`notify.persistent_notification` (set up to fan out to all devices). All
notifications carry `notification_id: fixed_price_swap` (and `feed_detect` for the
detector) so repeats **replace** rather than stack.

### Usage profile

`actions[0].variables.usage_profile` — 24 relative weights (index = hour of day,
mean ≈ 1). Only the **shape** matters (the weighted average normalises by the sum
of the weights). These are derived from the **Bio (spot) meter's last-30-day
hourly means** — i.e. the real whole-house load while on the spot feed. Note this
already reflects our **load-shifting to cheap hours**, so the weighted next-24 h
figure tends to sit slightly *below* the flat one. Refresh from that meter if usage
patterns change materially.

## Putting the lights back

Swapping the feed blacks the house out for a few seconds, and **most of the mains
bulbs come back ON** whatever they were before — they trickle back over a couple
of minutes, well after the swap itself is detected. On 21 Sep 2026 the bulbs
relit from 17:38:39 to 17:40:57 while `FeedDetect.yaml` only flipped
`input_boolean.on_fixed_price_feed` at 17:40:00.

`FeedSwapLightRestore.yaml` remembers the state beforehand and replays it. Both
halves live in **one** automation so the tracked-light list exists in one place,
and `mode: single` means the restore run also pauses snapshotting while it works.

### Snapshot (every 5 minutes)

`input_text.light_state_snapshot` holds `"<count>:<skips>:<code>"` — `code` is one
character per tracked light, in the fixed order of `actions[0].variables.lights`:

| Char | Meaning |
| --- | --- |
| `-` | off |
| `#` | on, restore with a bare `light.turn_on` (no brightness) |
| `0`–`9`, `a`–`z` | on, brightness in 36 buckets (`brightness / 255 × 35`) |
| `?` | never seen available — nothing to restore |

`count` guards the positional encoding: change the light list and the stored code
is rejected (and re-synced 5 minutes later). Lights in
`actions[0].variables.plain` are always `#` — the **ISP LED strips run iDeal LED
DIY patterns that any brightness write paints over** (same reason
`LoftC3Lights.yaml` uses a bare `light.turn_on`).

Two things keep the snapshot honest:

- **A light that is unavailable keeps its previous character.** A snapshot taken
  mid-blackout therefore cannot erase what we knew.
- **The jump guard.** The dangerous window is the ~90 s between the bulbs
  relighting and the feed boolean flipping: a 5-minute tick landing there would
  record "everything on" as the truth. If the number of lit lights rises by
  `jump` (3) or more in one tick the snapshot is **not** overwritten, only the
  skip counter moves. After `max_skips` (3) consecutive holds — 15 minutes — the
  new state is believed, so genuinely lighting the house up does eventually
  become the snapshot.

### Restore (on a feed change, or by hand)

Triggered by `input_boolean.on_fixed_price_feed` changing **either way**, or by
pressing `input_button.restore_lights_to_snapshot` (for a plain power cut, or a swap
FeedDetect did not flag).

The snapshot is copied to `input_text.light_restore_pending`, then every 20 s for
15 minutes (`passes` × `pass_delay`) the automation applies it to **whichever
lights are back online**, marking each one `.` as it deals with it:

- wanted off, currently on → `light.turn_off`
- wanted on → `light.turn_on`, with `brightness` unless it is a `plain` light
- already correct → marked done, not touched
- still unavailable → left pending for a later pass

**Each light is touched exactly once**, the first time it reappears, so a light
you switch by hand during the restore window is left alone. A persistent
notification (`notification_id: feed_light_restore`) reports how many were put
back and how many never returned.

### Helpers

| Entity | Purpose |
| --- | --- |
| `input_text.light_state_snapshot` | The snapshot, `"<count>:<skips>:<code>"`. |
| `input_text.light_restore_pending` | Restore working copy; `.` = dealt with. |
| `input_button.restore_lights_to_snapshot` | Run a restore by hand. |

These are **storage helpers**, created live over MCP (as
`input_text.spot_daily_avg_history` and `input_text.loft_stairs_restore` are) —
so no restart, and deliberately *not* declared in `helpers.yaml`, where the same
id would fight for the entity registry slot at restart. `helpers.yaml` carries a
comment with the three definitions so they can be recreated. The automation's
condition keeps it silent until all three exist.

```bash
python3 ElectricAutomations/deploy_feed_restore.py
```

### Two things found while commissioning it (21 Sep 2026)

- **The first press of the button after creating it does nothing.** The trigger
  carries `not_from: [unknown, unavailable]` so HA restoring the button's state
  at startup cannot fire a restore; a never-pressed button's previous state is
  `unknown`, so that first press is filtered too. Press it twice that once.
- **`light.front_porch_local` is motion-driven** by
  `esphome/FrontPath/frontpath_lights_automations*.yaml`. A snapshot can catch it
  mid-motion-brighten, and a restore then dims it back — the test run put it to
  brightness 44 while the motion automation wanted 166, and the motion automation
  won again within the minute. Harmless, but it is the one entity in the list
  another automation actively drives; drop it if it ever annoys.

### Tuning

`actions[0].variables` — `lights` (tracked entities, order matters), `plain`
(on/off only), `jump`, `max_skips`, `passes`, `pass_delay`. Adding a smart plug
works the same way; leave anything another automation owns (hot water, pool)
out of the list.

## What the switch disables (and what it does NOT)

When `input_boolean.on_fixed_price_feed` is **ON**:

| Automation | Effect on fixed feed |
| --- | --- |
| `SuperExpensive.yaml` | Never activates — no load shedding. Releases if it was active. |
| `CheapLeccy.yaml` | `input_boolean.cheap_leccy` forced **off** (stops every "turn on because cheap" consumer). |
| `DaytimeCheapWindow.yaml` | `input_boolean.daytime_cheap_7_21` forced **off**. |
| `DaytimeCheapHeat.yaml` | No cheap-hour boost and no expensive-hour cut — **normal occupancy/comfort heating still runs**. |
| `sam.yaml` | No price-driven pre-cool. **Comfort cooling/heating still runs.** |

**Deliberately left running** (they don't misbehave on a flat tariff):

- **Hot water** (`HotWater.yaml`) — it heats during the "cheapest" N hours of the
  day; on a flat day those are arbitrary but still deliver a hot tank, so the
  schedule is harmless and the deadline/shower logic keeps working.
- The Nordpool sensors, price-rank and caching automations (pure data — no
  actions).

## Tests

- `tests/test_fixed_price_swap.py` — next-24 h maths (flat + weighted), the swap
  decision (margin + once/day throttle, both directions) and every `on_fixed_price`
  guard.
- `tests/test_feed_detect.py` — feed detection: dual-meter compare + dead-band
  latch, single-meter fallback when a meter is unavailable (incl. the live
  Hem-down/Bio-idle = FIXED case), solar export, and no redundant writes.
- `tests/test_feed_swap_light_restore.py` — the light snapshot encoding
  (brightness buckets, plain lights, unavailable keeping its old character), the
  jump guard (surge held, released after `max_skips`) and one restore pass
  (turn off/on, brightness, offline lights deferred, each light touched once).

```bash
python3 ElectricAutomations/tests/test_fixed_price_swap.py
python3 ElectricAutomations/tests/test_feed_detect.py
python3 ElectricAutomations/tests/test_feed_swap_light_restore.py
```

## Notes / caveats

- The benchmark uses the **base** spot sensor (`sensor.nordpool_kwh_se4_sek_3_10_0`,
  ex-VAT) on both sides, so the comparison is like-for-like. It is a *relative*
  "dearer/cheaper than the recent norm" signal, not your exact fixed contract rate.
- `spot_30d_avg` was seeded from long-term statistics day-level prices (≈1.22
  SEK/kWh). Each night it is refined with the true daily mean, so within ~30 days
  the buffer holds only true daily means.
