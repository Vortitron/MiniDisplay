# House Thermal Model

`HouseThermalModel.yaml` learns the house's thermal behaviour automatically by sampling inside and outside temperatures every 10 minutes and fitting two parameters using an exponential moving average (EMA):

- **k** — heat loss coefficient (1/hour)
- **h** — Sam's effective heating rate (°C/hour at zero ΔT)

From these, the model exposes:

- **τ = 1/k** — thermal time constant (hours)
- **T_eq = T_outside_forecast + h/k** — equilibrium indoor temperature while Sam heats continuously, using the **forecast** outside temperature over the next 4 hours (not just current)
- **hours to target** — time needed to reach a target temperature (default 20°C) with Sam heating full-tilt, based on the forecast

### Why forecast, not current?

When we want to be at 20°C by 19:00 and it's 15:00, the outside temperature during the 15:00–19:00 heating window matters more than the temperature right now. Using the 4-hour forecast average gives a much better answer to "how long will it take to reach target?" — especially in the evening when temperatures are usually falling.

The model pulls its forecast from `weather.openweathermap` via `weather.get_forecasts` (type `hourly`) and averages the `temperature` values for the next `forecast_hours` hours (default 4). The result is written to `input_number.forecast_outside_4h` for other automations to read.

**Important:** the k/h parameters themselves are still learned from **actual current** inside/outside temperatures — the forecast is only used in the forward-looking "hours to target" calculation.

## The physics

Newton's law of cooling, extended with a heat source:

\[ \frac{dT}{dt} = h - k \cdot (T_{\text{inside}} - T_{\text{outside}}) \]

- **When Sam is off / idle / fan_only**: `h = 0`, so inside temp decays exponentially toward outside with time constant **τ**.
- **When Sam is heating**: the solution is `T(t) = T_eq + (T_0 − T_eq) · exp(−k·t)`, so inside temp rises exponentially toward **T_eq**.

### Solving "hours to reach target"

\[ t = \frac{1}{k} \ln\left(\frac{T_{\text{eq}} - T_0}{T_{\text{eq}} - T_{\text{target}}}\right) \]

This is valid when `T_0 < T_target < T_eq`. If `T_eq ≤ T_target` (Sam can't reach target at this outside temp), the model returns 99 hours as a sentinel.

## Sampling strategy

Each 10-minute tick:

1. Read `sensor.t_h_sensor_temperature` (inside) and `sensor.sam_outside_temperature` (outside).
2. Compare against values stored in helpers at the previous sample.
3. Compute **dT/dt** in °C/hour.
4. **Reject** the sample if any of:
   - Interval outside 5–30 minutes (clock skew, automation restart)
   - Change > 2°C (door opened, sensor glitch)
   - |T_inside − T_outside| < 2°C (too little signal to extract k reliably)
5. Categorise by `climate.sam.hvac_action`:
   - `idle` / `fan` / `off` / `cooling` → passive sample, update **k**
   - `heating` → active sample, update **h** using the current k estimate
6. Apply EMA: `new = 0.95 * old + 0.05 * observed` (smoothing factor `ema_alpha = 0.05`)
7. Additionally bound new values to physically plausible ranges (k: 0.01–2.0 /h, h: 0.1–20 °C/h) before updating.

### Starting estimates

Seed the helpers with sensible defaults before the first sample:

- `input_number.house_heat_loss_k` — initial value **0.2** (→ τ ≈ 5 hours, typical for a reasonably insulated home)
- `input_number.house_heat_rate` — initial value **2.0** (°C/hour at zero ΔT; will refine after a day or two)

The EMA will pull these toward the true values as real samples accumulate. After ~24 hours with mixed heating/idle periods the estimates should stabilise.

## Interpreting the numbers

Typical Swedish wooden/brick house:

| Quality | k (1/h) | τ (h) |
|---|---|---|
| Very poorly insulated | 0.5 | 2 |
| Average | 0.2 | 5 |
| Well insulated | 0.1 | 10 |
| Passive house | 0.03 | 33 |

Sam at 1500W heat output into ~150m³ of air + contents would give **h ≈ 2–4 °C/h**, depending on thermal mass.

## Example usage

Once the model has converged, you can ask questions like:

> "It's 15:00, outside is 0°C, inside is 16°C. Should I start pre-warming now to be at 20°C by 19:00?"

- `T_eq = 0 + h/k = 0 + 2.5/0.2 = 12.5°C` → **wait, Sam can't reach 20°C at 0°C outside with only 1500W!**

In that case the model flags it (returns 99) and `DaytimeCheapHeat.yaml` knows to start heating as early as cheap electricity allows.

If `T_eq > target` (plenty of margin), the model tells us exactly how many hours of heating will just reach target, and we can schedule accordingly.

## Dependencies

- `sensor.t_h_sensor_temperature` (living room, representative of the heated zone)
- `sensor.sam_outside_temperature`
- `climate.sam` (reads `hvac_action` attribute)
- `weather.openweathermap` (for the 4-hour forecast)

## Helper entities to create in Home Assistant

See `helpers.yaml` for the full set of helpers needed across all automations in this folder. The ones specific to the thermal model are:

| Entity | Min | Max | Step | Unit | Initial |
|---|---|---|---|---|---|
| `input_number.house_heat_loss_k` | 0 | 3 | 0.0001 | 1/h | 0.2 |
| `input_number.house_heat_rate` | 0 | 30 | 0.001 | °C/h | 2.0 |
| `input_number.house_thermal_tau` | 0 | 100 | 0.01 | h | 5.0 |
| `input_number.thermal_last_inside` | -50 | 50 | 0.01 | °C | — |
| `input_number.thermal_last_outside` | -50 | 50 | 0.01 | °C | — |
| `input_number.hours_to_evening_target` | 0 | 24 | 0.01 | h | — |
| `input_number.forecast_outside_4h` | -50 | 50 | 0.01 | °C | — |

Plus:
- `input_datetime.thermal_last_sample` — has_date: true, has_time: true
- `input_text.house_thermal_status` — max: 255 (for dashboard display)

## Using the model in DaytimeCheapHeat

`DaytimeCheapHeat.yaml` reads **k**, **h**, **τ**, `hours_to_evening_target`, `forecast_outside_4h`, plus `sensor.forecast_tonight_min` and `sensor.forecast_outside_at_23` (from `forecast_sensors.yaml`). It writes the decision audit to **`input_text.sam_preheat_calc`**.

Evening 25°C pre-warm is skipped when a mild night is forecast (e.g. only ~17°C at 23:00) and the house is already warm enough or the model says you will reach 20°C before 19:00 anyway.
