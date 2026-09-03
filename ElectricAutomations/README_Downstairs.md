# Downstairs automations

Home Assistant automations for the downstairs allrum area (cat motion, MQ2 smoke,
LD2410 watchdog). Deploy with:

```bash
python3 ElectricAutomations/deploy_downstairs.py
```

## Automations

| File | HA id | Purpose |
| --- | --- | --- |
| `MovementDownstairs.yaml` | `1762513683407` | Night cat-visit alert (moving_energy gate) |
| `SmokeDownstairsAllrum.yaml` | `1764923529394` | MQ2 spike alarm from Downstairs Allrum ESPHome |
| `SmokeDownstairs.yaml` | `1760719333460` | MQ2 alarm from ManifoldTemperature node |
| `DownstairsMotionUnavailable.yaml` | `1766667848638` | LD2410 unavailable watchdog + recovery |
| `PersistentNotificationRelay.yaml` | `persistent_notification_relay_pixel8` | Mirrors persistent notifications to Pixel 8 |

Persistent notifications are the single alert path for ESP devices (KitchenDetectorer,
MiniDisplay, etc.). `PersistentNotificationRelay.yaml` forwards each new one to
`notify.mobile_app_pixel_8` so individual automations do not need separate mobile
targets (the old LG TV notify has been removed).

## ESPHome: Downstairs Allrum

`esphome/Downstairs/DownstairsAllrum.yaml` hosts the MQ2 ADC and BLE proxy.

### MQ2 spike alarm

Dusty building-work rooms can sit at 35–40% baseline. The MQ2 binary no longer
alarms on a fixed 25% threshold. It tracks a slow baseline and alarms when:

- level rises **15%** above baseline (spike), or
- level hits **70%** absolute (safety ceiling)

Clear when spike margin drops below **8%** and level is under **60%**.

Diagnostic entities: `sensor.downstairs_allrum_mq2_baseline`,
`sensor.downstairs_allrum_mq2_spike_margin`.

**Flash required** after changing MQ2 logic, then re-enable
`automation.smoke_downstairs_allrum` (it is turned off while the old firmware
leaves the MQ2 binary stuck on). The binary is healthy when it sits `off` with
baseline well below the 70% ceiling.

```bash
esphome run esphome/Downstairs/DownstairsAllrum.yaml
```

### LD2410 watchdog entity

`ld2410_ha_watchdog_entity_id` is `binary_sensor.allrum_motion_motion` (replaces
the old `binary_sensor.hlk_ld2410_5f83_motion` entity).

### Movement Downstairs (cat visit) — false-alert filtering

Daytime auto-cal (`button.allrum_motion_auto_sensitivities`) stays manual — do
**not** schedule it at night (a cat in the room would be baked into the noise
floor). Overnight “less sensitive” behaviour is handled in the alert logic
instead.

**The room is out of use.** There is no human movement between 18:00 and 10:00
(workpeople have gone home), so any real moving target in that window is the cat
— and she is shut in until someone goes down. The job of this automation is to
notice that, not to count visits.

`MovementDownstairs.yaml` requires:

1. **`sensor.allrum_motion_moving_energy` above 25** (primary trigger).
   **No hold time** — see the timing note below.
2. **Window 18:00–10:00**, spanning midnight (`or` of two time conditions).
3. **Burst corroboration** — the alert only goes out if the spike is
   corroborated by **two more crossings, all within 20 s of the first one**.
   No amplitude shortcut — see the 2026-08-11 fix note below.
4. **30 min cooldown** (`mode: single` + trailing delay). This is also what
   produces the "keep nagging" behaviour: while she is still moving a fresh
   burst re-fires every 30 min, and once the room is quiet nothing triggers, so
   it stops on its own.

Detection is by **burst shape, not amplitude** — see the calibration note below.
There is deliberately no darkness/`photo_sensor` threshold and no occupancy
condition (`binary_sensor.allrum_motion_occupancy` has been stuck `on` since the
2026-08-04 device boot and filters nothing; it needs
`button.allrum_motion_reboot_device`).

#### Timing note — why the trigger has no `for:` (fixed 2026-08-09)

The automation had not fired since 2026-07-25. Measuring a full night of
recorder data (2026-08-08 18:00 → 2026-08-09 06:00 UTC) showed three independent
blockers:

* `moving_energy` sits at a floor of **13** and reports genuine targets as
  **sub-second spikes**. It crossed 25 on **33** separate occasions that night,
  and the **longest continuous excursion was 0.72 s**. The old
  `for: {seconds: 2}` was therefore unsatisfiable — the trigger could never fire.
* The old condition re-read the sensor with
  `states('sensor.allrum_motion_moving_energy')`. Because conditions evaluate
  after the spike has collapsed back to 13, that test would have failed even if
  the trigger had fired. Anything reading the energy must use
  `trigger.to_state.state`.
* The old reset waited for occupancy off for 2 min with a 12 h timeout. With
  occupancy stuck `on` that wait always ran the full 12 h, so one early trip
  suppressed the rest of the night.

#### Calibration note — burst shape beats amplitude (2026-08-09)

Amplitude alone does not separate cat from noise: isolated noise blips reached
26–48, overlapping the cat's range. **Edge count does.** Comparing a full night
against a confirmed cat-present morning (the cat was found shut in at ~09:00 on
2026-08-09):

* **Noise** — one or two isolated sub-second edges, then nothing.
* **Cat** — 3–15 edges over tens of seconds, repeatedly.

Requiring **≥3 edges within 90 s, or a single peak ≥50** fired on every
confirmed cat burst and rejected every noise blip in both samples. The old
"≥35 when dark" rule is what suppressed the cat at 07:58 that morning (peak 32),
and the 08:00 window close hid the rest of her 08:01–09:48 activity — hence the
extension to 10:00.

**Live confirmation (night of 2026-08-09/10):** fired at 00:35 and 03:34 local
and relayed to the Pixel 8, having fired zero times in the preceding two weeks.
Isolated blips at 23:48 (peak 26) and 23:56 (peak 31) were correctly ignored.

#### Fix note — false alerts after the device reboot (2026-08-11)

`button.allrum_motion_reboot_device` was pressed on 2026-08-10 to clear the
occupancy sensor being stuck `on`. It also changed `moving_energy`'s whole noise
character: floor dropped from a continuous 13 to an event-only 0 (silent for
hours between events, not constantly republishing), and isolated single-frame
noise spikes started reaching the sensor's max value of **100** — well above the
48 ceiling the original ≥50 amplitude shortcut assumed was safe.

That night, of 4 automation triggers, 2 correctly timed out with no
notification, but 2 produced false "check for the cat" alerts with the room
confirmed empty:

* **04:08 local** — a single ~100 ms spike to 64, fired instantly through the
  old "peak ≥50 skips corroboration" shortcut.
* **02:44 local** — two isolated single-frame blips 8.9 s apart, satisfied "3
  crossings within 90 s **of the previous one**" — a budget that stacks up to
  180 s and lets unrelated blips masquerade as a burst.

Fix: removed the amplitude shortcut entirely (every detection needs
corroboration, however strong), and bounded all 3 crossings to within **20 s of
the *first* one** (`window_start`), not 90 s of the previous one. Replayed
against both the confirmed-cat Sunday morning session and the three real cat
visits the night of 2026-08-08/09 (20:57, 22:11, 00:59 local) — all still fire,
most with several edges to spare (4–7 edges within the 20 s window, not just
the minimum 3).

**Known residual gap:** two isolated blips within 20 s of each other still
pass — that's exactly the 02:44 pattern. It was kept anyway (deliberate
trade-off, chosen over a tighter 10 s window or requiring 4 edges) because a
real cat visit could plausibly be just as brief. If that specific false-alert
pattern recurs, tighten further: shrink the window below 20 s and/or raise the
edge requirement to 4.

The notification includes the energy reading so you can tune the numbers
(crossing 25, 3 edges / 20 s) after a few real vs false nights.
Redeploy with `deploy_downstairs.py MovementDownstairs.yaml`.

Note: `sensor.allrum_motion_photo_sensor` is no longer used. Moonlight does not
change mmWave physics, and using darkness as a proxy for "be stricter" cost a
real detection (the 07:58 cat at peak 32). Burst shape is the discriminator.
