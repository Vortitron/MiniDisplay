# Pool Pump — Price-Optimised Control

**Off-season (from Aug 2026):** the pool is shut down for the year. All four
automations are `initial_state: false` and turned **off** on GamlaBio. Plan
select is `off`. Re-enable in spring by removing `initial_state: false` (or
setting it `true`), deploying, and turning the automations on.

## Hardware

- **Switch:** `switch.smart_plug_4_socket_1` (retasked from air fryer)
- **Pump:** ~5000 L/h
- **Pool:** ~15 000 L → one full turnover ≈ **3 hours** ON time

## Deploy

```bash
python3 ElectricAutomations/deploy_pool_pump.py
```

Publishes MQTT entities (Back Garden area), deploys automations, and updates SuperExpensive shedding.

Dashboard (multi-tab Sam & Energy):

```bash
export HA_URL=http://192.168.1.15:8123 HA_TOKEN=...
python3 ElectricAutomations/deploy_sam_energy_dashboard.py
```

Pool controls live on the **Back Garden** tab at `/sam-energy/back-garden`.

## Daily maintenance (automatic)

`PoolPumpMaintenance.yaml` resets the daily counter at **00:05** and auto-arms **maintenance** mode whenever today's ON time is below **3 hours** (default `number.pool_pump_maintenance_daily_target` = 180).

Maintenance runs only during **cheap** electricity (same rules as cheap windows) and pauses during super-expensive. User plans take priority; maintenance resumes when they finish if the daily target is still unmet.

## Plans

| Button | Mode | Behaviour |
|---|---|---|
| `button.pool_cheap_windows` | `cheap` | Up to **6 h** ON time during cheap slots; **cancels at 16:00** if not finished |
| `button.pool_extended_run` | `extended` | Continuous for 6 h (configurable), pausing only during super-expensive |
| `button.pool_pump_run_1_hour` | `one_hour` | Continuous **1 h** regardless of price (except super-expensive) |
| `button.pool_stop` | `off` | Cancel plan and switch off |

**Manual switch-on:** if you turn `switch.smart_plug_4_socket_1` on with no plan active, `PoolPumpManual.yaml` arms the same **1 h** run.

## Entity IDs

| Purpose | Entity |
|---|---|
| Plan | `select.pool_pump_pool_pump_plan` |
| Budget remaining | `number.pool_pump_minutes_remaining` |
| ON time today | `number.pool_pump_daily_on_minutes` |
| Daily maintenance target | `number.pool_pump_maintenance_daily_target` (default 180) |
| Cheap cutoff hour | `number.pool_pump_cheap_cutoff_hour` (16 when cheap windows armed) |
| Timed until | `datetime.pool_pump_pool_pump_plan_until` |
| Status | `text.pool_pump_pool_pump_status` |
| Buttons | `button.pool_cheap_windows`, `pool_extended_run`, `pool_pump_run_1_hour`, `pool_stop` |

All pool MQTT entities are assigned to the **Back Garden** area via device discovery.

The scheduler must **not** trigger on `number.pool_pump_minutes_remaining` or
`number.pool_pump_daily_on_minutes` — it writes those itself, and a second run
80 ms later double-counts the 15-minute tick. Price-rank is also omitted (the
`/15` time pattern already covers it). A short start delay coalesces
`cheap_leccy` / `super_expensive` when they flip on the same quarter-hour.

## Automations

| File | ID |
|---|---|
| `PoolPump.yaml` | `pool_pump_price_scheduler` |
| `PoolPumpButtons.yaml` | `pool_pump_arm_plan` |
| `PoolPumpMaintenance.yaml` | `pool_pump_daily_maintenance` |
| `PoolPumpManual.yaml` | `pool_pump_manual_on` |

## Tests

```bash
python3 ElectricAutomations/tests/test_pool_pump.py
```
