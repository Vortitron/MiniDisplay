#!/usr/bin/env python3
"""Unit tests for the sam.yaml HVAC decision maths.

Two concerns are pinned here:

1. Heating: the de-duplication refactor (extracting the maths into the
   automation `variables:` block) must stay behaviour-preserving, so the NEW
   variable templates are checked against the ORIGINAL inline expressions
   (NEW == OLD) and against hand-computed expected values.

2. Cooling: the cooling logic was deliberately rewritten (summer 2026) so the
   compressor only runs when it is genuinely hot BOTH inside and out
   (>= 27/27), on the scorcher override (> 30°C out AND either room > 27°C AND
   cheap power), or when pre-cooling on cheap power ahead of a hot afternoon;
   otherwise Sam just circulates air (fan_only). The cooling-trend baseline is
   capped at today's forecast max so a sun-baked outdoor sensor can't fake a
   downward trend and suppress pre-cool. These tests pin the NEW cooling rules
   with explicit scenarios (there is no old behaviour worth preserving — the old
   "outdoor >= 25 and indoor > 20 -> compressor" rule was the bug being fixed).

The tests render the templates with plain Jinja2 but mimic Home Assistant's
variable handling, where each rendered template result is parsed back into a
native Python type (bool/int/float/str) before the next variable is rendered.

Run with:  python3 -m pytest ElectricAutomations/tests/test_sam_hvac_templates.py
       or:  python3 ElectricAutomations/tests/test_sam_hvac_templates.py
"""

from __future__ import annotations

from ast import literal_eval

from jinja2 import Environment

# --- Constants (mirror the top-level `variables:` block in sam.yaml) --------
CONSTANTS = {
	# Cooling thresholds (see sam.yaml).
	"cool_compressor_in": 27,
	"cool_compressor_out": 27,
	"cool_fan_target": 25,
	"cool_outdoor_gate": 22,
	"cool_precool_day_max": 27,
	"cool_precool_floor": 23,
	"cool_trend_margin": 1.0,
	"cool_hot_outdoor": 30,
	"cool_hot_room": 27,
	"heat_offset": 1,
	"cool_offset": -1,
	"base_stop_heat_offset": -2,
	"max_stop_heat_offset": -5,
	"temp_tolerance": 0.5,
	"fan_only_diff": 3,
	"sam_setpoint_cap": 27,
	# climate.sam exposes min_temp=16, max_temp=30 in the live system.
	"sam_min_temp": 16,
	"sam_max_temp": 30,
}

_ENV = Environment()


def _parse_result(text: str):
	"""Mimic Home Assistant's native-type parsing of a rendered template."""
	stripped = text.strip()
	if stripped in ("True", "False"):
		return stripped == "True"
	if stripped in ("None", ""):
		return None if stripped == "None" else ""
	try:
		return literal_eval(stripped)
	except (ValueError, SyntaxError):
		return stripped


def render_var(template: str, ctx: dict):
	"""Render a single automation variable and parse to a native type."""
	return _parse_result(_ENV.from_string(template).render(**ctx))


# --- ORIGINAL inline heating expressions (copied verbatim, pre-refactor) -----
OLD_HEAT_MODE = (
	"{% set diff = remote_heat - desired_effective %}"
	"{{ 'fan_only' if internal_at_unit_hot or living_above_all_targets "
	"or (remote_heat < desired_effective - temp_tolerance and outdoor > desired_effective) "
	"or diff > fan_only_diff else 'heat' }}"
)
OLD_HEAT_SETPOINT = (
	"{% set diff = remote_heat - desired_effective %}"
	"{% set need = desired_effective - remote_heat %}"
	"{% set boost = [heat_offset, need] | max %}"
	"{% if living_above_all_targets %}"
	"  {% set unclamped = internal + [base_stop_heat_offset - (living_overheat_diff | float(0)), max_stop_heat_offset] | max %}"
	"{% elif internal_at_unit_hot %}"
	"  {% set unclamped = internal + max_stop_heat_offset %}"
	"{% elif remote_heat < desired_effective - temp_tolerance %}"
	"  {% set unclamped = internal + boost %}"
	"{% elif remote_heat >= desired_effective %}"
	"  {% set unclamped = internal + [base_stop_heat_offset - diff, max_stop_heat_offset] | max %}"
	"{% else %}"
	"  {% set unclamped = internal %}"
	"{% endif %}"
	"{{ [sam_min_temp, [sam_max_temp, sam_setpoint_cap, unclamped] | min] | max }}"
)

# --- NEW variable definitions (must match the `variables:` block in sam.yaml) ---
HEAT_VARS = {
	"heat_diff": "{{ remote_heat - desired_effective }}",
	"heat_need": "{{ desired_effective - remote_heat }}",
	"heat_boost": "{{ [heat_offset, heat_need] | max }}",
	"heat_fan_only": (
		"{{ internal_at_unit_hot or living_above_all_targets "
		"or (remote_heat < desired_effective - temp_tolerance and outdoor > desired_effective) "
		"or heat_diff > fan_only_diff }}"
	),
	"heat_mode": "{{ 'fan_only' if heat_fan_only else 'heat' }}",
	"heat_setpoint": (
		"{% if living_above_all_targets %}"
		"  {% set unclamped = internal + [base_stop_heat_offset - (living_overheat_diff | float(0)), max_stop_heat_offset] | max %}"
		"{% elif internal_at_unit_hot %}"
		"  {% set unclamped = internal + max_stop_heat_offset %}"
		"{% elif remote_heat < desired_effective - temp_tolerance %}"
		"  {% set unclamped = internal + heat_boost %}"
		"{% elif remote_heat >= desired_effective %}"
		"  {% set unclamped = internal + [base_stop_heat_offset - heat_diff, max_stop_heat_offset] | max %}"
		"{% else %}"
		"  {% set unclamped = internal %}"
		"{% endif %}"
		"{{ [sam_min_temp, [sam_max_temp, sam_setpoint_cap, unclamped] | min] | max }}"
	),
}

# Cooling vars, in dependency order (later vars use earlier ones).
COOL_VARS = {
	# Baseline for the "getting cooler" test is capped at today's forecast max so
	# a sun-baked outdoor sensor (e.g. 38°C against a flat 32°C forecast) can't
	# fake a downward trend and wrongly suppress pre-cool.
	"cool_trend_baseline": "{{ [outdoor, forecast_day_max] | min if forecast_day_max > 0 else outdoor }}",
	"outdoor_cooling_trend": "{{ forecast_out_4h < cool_trend_baseline - cool_trend_margin }}",
	"cool_season": "{{ outdoor >= cool_outdoor_gate }}",
	"room_too_warm": "{{ remote_cool >= cool_fan_target }}",
	"very_hot": "{{ remote_cool >= cool_compressor_in and outdoor >= cool_compressor_out }}",
	# Scorcher override: really hot outside and EITHER room uncomfortably warm.
	"cool_hot_rooms": (
		"{{ (living_room_temp_ok and living_room_temp > cool_hot_room) "
		"or (bedroom_temp_ok and bedroom_temp > cool_hot_room) }}"
	),
	"hot_cheap_cool": "{{ cheap_now and outdoor > cool_hot_outdoor and cool_hot_rooms }}",
	"precool_now": (
		"{{ cheap_now and forecast_day_max >= cool_precool_day_max "
		"and not outdoor_cooling_trend "
		"and remote_cool > cool_precool_floor "
		"and outdoor >= cool_outdoor_gate }}"
	),
	"cool_active": "{{ (cool_season and room_too_warm) or precool_now or hot_cheap_cool }}",
	"cool_use_compressor": "{{ very_hot or precool_now or hot_cheap_cool }}",
	"cool_mode": "{{ 'cool' if cool_use_compressor else 'fan_only' }}",
	"cool_setpoint": (
		"{% if cool_use_compressor %}"
		"  {% set unclamped = internal + cool_offset %}"
		"{% else %}"
		"  {% set unclamped = internal %}"
		"{% endif %}"
		"{{ [sam_min_temp, [sam_max_temp, sam_setpoint_cap, unclamped] | min] | max }}"
	),
	"cool_action_label": (
		"{% if cool_use_compressor and precool_now and not very_hot and not hot_cheap_cool %}Pre-cool (cheap)"
		"{% elif cool_use_compressor %}Cooling"
		"{% else %}Fan only{% endif %}"
	),
}

ALL_VARS = {**HEAT_VARS, **COOL_VARS}


def build_context(scenario: dict) -> dict:
	"""Derive the intermediate context (as sam.yaml's variables block does)."""
	ctx = dict(CONSTANTS)
	living = scenario["living"]
	bedroom = scenario.get("bedroom", living)
	outdoor = scenario["outdoor"]
	internal = scenario["internal"]
	control = scenario.get("control", 16)
	fan_running = scenario.get("fan_running", False)

	desired_base = float(control)
	# The mama bedroom thermostat blend was retired (summer 2026 — bedroom
	# heater removed); desired_effective is now simply the control temperature.
	desired_effective = desired_base

	remote_cool = float(living)
	if fan_running:
		remote_heat = min(float(living), float(bedroom))
	else:
		remote_heat = float(living)

	ctx.update(
		{
			"living_room_temp": float(living),
			"bedroom_temp": float(bedroom),
			# Sensors valid unless a scenario explicitly marks one offline.
			"living_room_temp_ok": bool(scenario.get("living_room_temp_ok", True)),
			"bedroom_temp_ok": bool(scenario.get("bedroom_temp_ok", True)),
			"outdoor": float(outdoor),
			"internal": float(internal),
			"desired_base": desired_base,
			"desired_effective": desired_effective,
			"remote_cool": remote_cool,
			"remote_heat": remote_heat,
			"internal_at_unit_hot": float(internal) >= CONSTANTS["sam_setpoint_cap"],
			"living_above_all_targets": float(living) > desired_effective,
			"living_overheat_diff": float(living) - desired_effective,
			# Cooling inputs (price + forecast) — read directly in sam.yaml.
			"cheap_now": bool(scenario.get("cheap_now", False)),
			"forecast_day_max": float(scenario.get("forecast_day_max", 0)),
			"forecast_out_4h": float(scenario.get("forecast_out_4h", outdoor)),
		}
	)
	return ctx


def render_values(ctx: dict, var_defs: dict) -> dict:
	"""Render the given variable templates sequentially into the context."""
	ctx = dict(ctx)
	for name, tmpl in var_defs.items():
		ctx[name] = render_var(tmpl, ctx)
	return ctx


# --- Heating scenarios: (name, scenario, expected heat_mode, heat_setpoint) ---
HEAT_SCENARIOS = [
	("live_now_overheat_guard", dict(living=19.2, bedroom=20.45, outdoor=14, internal=18, control=16, fan_running=True),
		"fan_only", 16.0),
	("very_cold_full_boost", dict(living=12, bedroom=13, outdoor=2, internal=18, control=20, fan_running=False),
		"heat", 26.0),
	("at_target_nudge_down", dict(living=20, bedroom=20, outdoor=10, internal=21, control=20, fan_running=False),
		"heat", 19.0),
	("mild_coasting_fan_only", dict(living=15, bedroom=15, outdoor=22, internal=18, control=20, fan_running=False),
		"fan_only", 23.0),
	("unit_hot", dict(living=15, bedroom=15, outdoor=5, internal=28, control=20, fan_running=False),
		"fan_only", 23.0),
	("strong_overheat_guard", dict(living=25, bedroom=24, outdoor=10, internal=22, control=20, fan_running=False),
		"fan_only", 17.0),
	("warm_room_cool_out", dict(living=27, bedroom=26, outdoor=20, internal=24, control=20, fan_running=False),
		"fan_only", 19.0),
]

# --- Cooling scenarios: (name, scenario, expected cool_active, cool_mode,
#     cool_setpoint, cool_action_label) ---
COOL_SCENARIOS = [
	# The exact bug the user reported: 20°C room, 25°C outside -> must NOT cool.
	("today_bug_no_cool", dict(living=20.1, outdoor=25, internal=20, cheap_now=False, forecast_day_max=22, forecast_out_4h=22),
		False, "fan_only", 20.0, "Fan only"),
	# Genuinely hot inside AND out -> compressor.
	("very_hot_both", dict(living=28, outdoor=28, internal=27, cheap_now=False, forecast_day_max=30, forecast_out_4h=28),
		True, "cool", 26.0, "Cooling"),
	# Hot inside but mild outside (<27) -> fan only, no compressor.
	("hot_in_mild_out", dict(living=28, outdoor=24, internal=26, cheap_now=False, forecast_day_max=29, forecast_out_4h=24),
		True, "fan_only", 26.0, "Fan only"),
	# Warm room (>=25) and hot out, but room <27 -> fan only (both must hit 27).
	("warm_room_not_27", dict(living=26, outdoor=28, internal=25, cheap_now=False, forecast_day_max=30, forecast_out_4h=28),
		True, "fan_only", 25.0, "Fan only"),
	# Pre-cool: cheap now + hot day + no cooling trend + room above floor.
	("precool_cheap_hotday", dict(living=24, outdoor=24, internal=23, cheap_now=True, forecast_day_max=30, forecast_out_4h=24),
		True, "cool", 22.0, "Pre-cool (cheap)"),
	# The live 34°C-day case: 24.4 in, 29 out (rising to 33), cheap power ->
	# pre-cool with the compressor (setpoint internal-1 = 25), fan spreads it.
	("today_hot_day_precool_live", dict(living=24.4, outdoor=29, internal=26, cheap_now=True, forecast_day_max=33.1, forecast_out_4h=29.74),
		True, "cool", 25.0, "Pre-cool (cheap)"),
	# Pre-cool suppressed because it's getting cooler outside anyway.
	("precool_suppressed_trend", dict(living=24, outdoor=26, internal=23, cheap_now=True, forecast_day_max=30, forecast_out_4h=24),
		False, "fan_only", 23.0, "Fan only"),
	# Pre-cool stops once the room is at/below the pre-cool floor.
	("precool_floor_reached", dict(living=22.5, outdoor=24, internal=22, cheap_now=True, forecast_day_max=30, forecast_out_4h=24),
		False, "fan_only", 22.0, "Fan only"),
	# Winter evening pre-warm drives the room to 25°C while it's cold out:
	# must NOT be mistaken for "too hot" and flipped to cooling.
	("winter_prewarm_not_cooling", dict(living=25, outdoor=5, internal=22, cheap_now=True, forecast_day_max=8, forecast_out_4h=5),
		False, "fan_only", 22.0, "Fan only"),
	# Scorcher override (the live 27 Jun case): 38°C out, living only 25.3 but
	# BEDROOM 27.5 (>27), cheap power -> run the compressor outright. Sensor 38
	# sits above the 33°C forecast max, so the baseline caps at 33 and the trend
	# is correctly False (no fake "cooling"). Label is "Cooling", not pre-cool.
	("scorcher_bedroom_hot_live", dict(living=25.3, bedroom=27.5, outdoor=38, internal=28, cheap_now=True, forecast_day_max=33, forecast_out_4h=32.5),
		True, "cool", 27.0, "Cooling"),
	# Same scorcher but power is EXPENSIVE -> just the fan, no compressor.
	("scorcher_but_expensive_fan", dict(living=25.3, bedroom=27.5, outdoor=38, internal=28, cheap_now=False, forecast_day_max=33, forecast_out_4h=32.5),
		True, "fan_only", 27.0, "Fan only"),
	# Sun-baked sensor regression: 38°C sensor vs a flat 32.5°C forecast, rooms
	# below 27. The OLD trend (forecast < sensor-1 = 37) would have wrongly read
	# "cooling" and suppressed pre-cool; capping the baseline at the 33°C forecast
	# max keeps the trend False, so cheap pre-cool still runs.
	("sunbaked_sensor_still_precools", dict(living=25, bedroom=25, outdoor=38, internal=26, cheap_now=True, forecast_day_max=33, forecast_out_4h=32.5),
		True, "cool", 25.0, "Pre-cool (cheap)"),
]


def _check_heat_scenario(entry):
	name, scenario, exp_hmode, exp_hset = entry
	ctx = build_context(scenario)

	old_hmode = render_var(OLD_HEAT_MODE, ctx)
	old_hset = float(render_var(OLD_HEAT_SETPOINT, ctx))

	nv = render_values(ctx, HEAT_VARS)
	new_hmode = nv["heat_mode"]
	new_hset = float(nv["heat_setpoint"])

	# Refactor must be behaviour-preserving: NEW == OLD.
	assert new_hmode == old_hmode, f"{name}: heat_mode NEW {new_hmode} != OLD {old_hmode}"
	assert abs(new_hset - old_hset) < 1e-9, f"{name}: heat_setpoint NEW {new_hset} != OLD {old_hset}"

	# Pin expected values so logic errors are caught, not just drift.
	assert new_hmode == exp_hmode, f"{name}: heat_mode {new_hmode} != expected {exp_hmode}"
	assert abs(new_hset - exp_hset) < 1e-9, f"{name}: heat_setpoint {new_hset} != expected {exp_hset}"

	# Setpoint must always honour the clamps.
	assert CONSTANTS["sam_min_temp"] <= new_hset <= min(CONSTANTS["sam_max_temp"], CONSTANTS["sam_setpoint_cap"]), \
		f"{name}: heat setpoint {new_hset} outside clamp range"
	assert isinstance(nv["heat_fan_only"], bool), f"{name}: heat_fan_only not bool"


def _check_cool_scenario(entry):
	name, scenario, exp_active, exp_mode, exp_set, exp_label = entry
	ctx = build_context(scenario)
	nv = render_values(ctx, ALL_VARS)

	new_active = nv["cool_active"]
	new_mode = nv["cool_mode"]
	new_set = float(nv["cool_setpoint"])
	new_label = nv["cool_action_label"]

	assert new_active == exp_active, f"{name}: cool_active {new_active} != expected {exp_active}"
	assert new_mode == exp_mode, f"{name}: cool_mode {new_mode} != expected {exp_mode}"
	assert abs(new_set - exp_set) < 1e-9, f"{name}: cool_setpoint {new_set} != expected {exp_set}"
	assert new_label == exp_label, f"{name}: cool_action_label {new_label!r} != expected {exp_label!r}"

	# Compressor must never run unless very hot (27/27), pre-cooling, or the
	# scorcher override (hot_cheap_cool).
	if new_mode == "cool":
		assert nv["very_hot"] or nv["precool_now"] or nv["hot_cheap_cool"], \
			f"{name}: compressor engaged without very_hot, precool or hot_cheap_cool"

	# Setpoint must always honour the clamps.
	assert CONSTANTS["sam_min_temp"] <= new_set <= min(CONSTANTS["sam_max_temp"], CONSTANTS["sam_setpoint_cap"]), \
		f"{name}: cool setpoint {new_set} outside clamp range"

	for flag in ("cool_active", "very_hot", "precool_now", "cool_use_compressor",
			"outdoor_cooling_trend", "cool_hot_rooms", "hot_cheap_cool"):
		assert isinstance(nv[flag], bool), f"{name}: {flag} not bool"


# --- cheap_now derivation (mirrors the broadened sam.yaml definition) --------
# sam.yaml:
#   cheap_now = (is_state('input_boolean.cheap_leccy','on') or price_rank < price_rank_4h)
#               and not on_fixed_price
# The cheap_leccy term was added so a cheap morning still pre-cools even when it's
# cheaper still later (rank-vs-4h alone would say "wait").
def cheap_now(cheap_leccy_on: bool, price_rank: int, price_rank_4h: int, on_fixed: bool) -> bool:
	return (cheap_leccy_on or price_rank < price_rank_4h) and not on_fixed


CHEAP_NOW_CASES = [
	# (name, cheap_leccy_on, rank, rank_4h, on_fixed, expected)
	("today_cheap_leccy_even_cheaper_later", True, 4, 1, False, True),   # the fix
	("cheaper_now_than_in_4h", False, 2, 8, False, True),                # act-now signal
	("not_cheap_either_way", False, 8, 2, False, False),
	("fixed_feed_suppresses_precool", True, 4, 1, True, False),
]


def test_cheap_now_derivation():
	for name, cl, r, r4, fx, exp in CHEAP_NOW_CASES:
		got = cheap_now(cl, r, r4, fx)
		assert got == exp, f"{name}: cheap_now {got} != expected {exp}"


def test_heating_is_behaviour_preserving():
	for entry in HEAT_SCENARIOS:
		_check_heat_scenario(entry)


def test_cooling_logic():
	for entry in COOL_SCENARIOS:
		_check_cool_scenario(entry)


if __name__ == "__main__":
	test_heating_is_behaviour_preserving()
	test_cooling_logic()
	test_cheap_now_derivation()
	print(
		f"OK: {len(HEAT_SCENARIOS)} heating scenarios (NEW == OLD, expected, clamps), "
		f"{len(COOL_SCENARIOS)} cooling scenarios (27/27 + scorcher override + pre-cool + sun-baked trend) and "
		f"{len(CHEAP_NOW_CASES)} cheap_now cases passed."
	)
