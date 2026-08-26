# Deduped persistent notifications with a count

Some persistent notifications used to **stack** — every occurrence created a new
notification (no `notification_id`), so you'd end up with a pile of identical
"Movement Downstairs - Alarm: 1" entries. They now use a stable `notification_id`
so each one **replaces in place**, and they carry a **running count** instead.

## Pattern

Each notification has a dedicated `counter` helper. On every occurrence the
automation posts the persistent notification with the count, then increments the
counter:

```yaml
- action: notify.persistent_notification
  data:
    message: "Movement downstairs ×{{ (states('counter.movement_downstairs') | int(0)) + 1 }} — check for the cat!"
    data:
      notification_id: movement_downstairs
- action: counter.increment
  target:
    entity_id: counter.movement_downstairs
```

The count is rendered as `counter + 1` *before* incrementing, so "this is
occurrence N" is always correct without depending on state-update timing. The
same `notification_id` means the single notification just updates its count
rather than stacking. (`notify.persistent_notification` is configured to fan out
to all devices; only `message`/`title`/`notification_id` are used.)

`PersistentNotificationRelay.yaml` mirrors each new persistent notification to
`notify.mobile_app_pixel_8` so automations do not need separate mobile targets.

## The three notifications

| Notification | `notification_id` | Counter | Defined in |
| --- | --- | --- | --- |
| Hot water used / tank depleted | `hot_water` | `counter.hot_water_used` | `HotWaterTemperature.yaml` (repo) |
| Movement downstairs (check for the cat) | `movement_downstairs` | `counter.movement_downstairs` | `MovementDownstairs.yaml` — moving_energy >25, no hold time, burst-corroborated (3 edges within 20 s, no amplitude shortcut); 18:00–10:00; 30 min cooldown |
| Refill loft wet | `loft_wet_refill` | `counter.loft_wet_refill` | **HA UI** automation *Loft Wet On* (`id 1776061413956`) |

*Movement Downstairs* is versioned in `MovementDownstairs.yaml` and deployed via
the HA config API. *Loft Wet On* remains a HA UI automation.

## Daily reset

`NotificationCounters.yaml` (`notification_counters_daily_reset`) resets all three
counters at **00:00** so each shows a per-day count. The old notification (e.g.
"×5") self-heals on the next event (it re-renders as "×1"); the reset does **not**
dismiss notifications, so an unacknowledged alert is never hidden.

## Helpers to create

`counter.hot_water_used`, `counter.movement_downstairs`, `counter.loft_wet_refill`
— each `initial: 0`, `minimum: 0`, `step: 1` (created as HA helpers).
