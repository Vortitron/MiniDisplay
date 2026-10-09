# Freezer plug

The freezer (Living Room) runs through a Tuya plug on the official Tuya cloud
integration, device **Freezer**. Deploy with:

```bash
python3 ElectricAutomations/tests/test_freezer_watch.py
python3 ElectricAutomations/deploy_freezer.py
```

## Entities

| Entity | What |
| --- | --- |
| `switch.smart_plug_2_switch_1` | The plug relay. Not `switch.smart_plug_2_socket_1`, which is Hot Water. |
| `sensor.smart_plug_2_power_2` | Power, W |
| `select.smart_plug_2_power_on_behaviour_2` | `1` = on after a power cut. Leave it at `1` |
| `binary_sensor.living_room_freezer_running` | Template helper: power > **15 W**; unavailable when power isn't a number |
| `input_boolean.freezer_maintenance` | Defrost/clean/move mode: no keep-on, no power alerts. Ends itself after 12 h |
| `input_select.freezer_alert` | `none` / `running_long` / `idle_long`. Bookkeeping, so each alert is raised and dismissed once |

All three helpers are **storage** helpers created over MCP (template config flow
and `ha_set_helper`), so no restart is needed and they are not in `helpers.yaml`.
To change the 15 W threshold, open Settings → Helpers → Freezer running.

## Automations

| File | HA id | Purpose |
| --- | --- | --- |
| `FreezerKeepOn.yaml` | `freezer_keep_on` | Plug off for 10 s (or seen off on the 15-min poll) → turn it back on, Alarm 1. Alarm 2 if it won't come on |
| `FreezerPowerWatch.yaml` | `freezer_power_watch` | Running non-stop ≥ 3 h → "door open?". Not running ≥ 3 h → "broken or unplugged?" Both Alarm 2, dismissed on recovery |
| `FreezerUnavailable.yaml` | `freezer_plug_unavailable` | Plug unavailable/unknown ≥ 30 min → Alarm 2 (the other two can't see anything then) |

Alerts use `notify.persistent_notification`, so they reach the MiniDisplay and
(through `PersistentNotificationRelay.yaml`) the Pixel 8.

The power watch polls every 5 min, comparing the running sensor's
`last_changed` with `run_limit_h` / `idle_limit_h`, and does not rely on
`for:` triggers. A `for:` timer is lost when automations are reloaded, so a
freezer that died before a deploy would never alert. An HA restart resets
`last_changed`, so at worst an alert comes 3 h after the restart.

## Tuning

The 15 W / 3 h / 3 h values are first guesses, set on 2026-10-07 before there
was any history. Once there are a few days of `sensor.smart_plug_2_power_2`,
check:

- **Compressor power**, which sets the 15 W threshold. Idle should read about
  0 W, running is typically 50–150 W. A frost-free defrost heater spike also
  counts as "running", which is fine.
- **Longest normal run.** A big shop of warm food can keep it running for
  hours, so set `run_limit_h` comfortably above the longest run seen.
- **Longest normal off period.** Usually under an hour indoors, so
  `idle_limit_h` can probably drop to 2.

After a defrost the freezer can run flat out for 4–6 h while it pulls back
down, so expect a "running non-stop" alert unless maintenance mode is still on.
