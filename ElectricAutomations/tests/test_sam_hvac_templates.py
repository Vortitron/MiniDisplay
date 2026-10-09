#!/usr/bin/env python3
"""Unit tests for the sam.yaml HVAC decision maths.

Two concerns are pinned here:

1. Heating: Sam's own sensor sits near the ceiling and over-reads while it
   heats, so it only guides the setpoint (internal + need, clamped to the
   unit's 16-30°C range and rounded to its 0.5°C step). The 27°C heating
   ceiling is read from the living-room sensor (heat_room_max). Sep 2026:
   the old "internal >= 27 -> fan_only" rule short-cycled Sam every ~7 min
   and was removed; the scenarios below pin the new rules.

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
	"cool_blast_offset": -10,
	"base_stop_heat_offset": -2,
	"max_stop_heat_offset": -5,
	"temp_tolerance": 0.5,
	"fan_only_diff": 3,
	"heat_room_max": 27,
	"cool_setpoint_cap": 27,
	"heat_fallback_offset": 2,
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


# --- NEW variable definitions (must match the `variables:` block in sam.yaml) ---
HEAT_VARS = {
	"heat_diff": "{{ remote_heat - desired_effective }}",
	"heat_need": "{{ desired_effective - remote_heat }}",
	"heat_boost": "{{ [heat_offset, heat_need] | max }}",
	"heat_fan_only": (
		"{{ not internal_fallback and (room_at_heat_max or living_above_all_targets "
		"or (remote_heat < desired_effective - temp_tolerance and outdoor > desired_effective) "
		"or heat_diff > fan_only_diff) }}"
	),
	"heat_mode": "{{ 'fan_only' if heat_fan_only else 'heat' }}",
	"heat_setpoint": (
		"{% if internal_fallback %}"
		"  {% set unclamped = desired_effective + heat_fallback_offset %}"
		"{% elif living_above_all_targets %}"
		"  {% set unclamped = internal + [base_stop_heat_offset - (living_overheat_diff | float(0)), max_stop_heat_offset] | max %}"
		"{% elif room_at_heat_max %}"
		"  {% set unclamped = internal + max_stop_heat_offset %}"
		"{% elif remote_heat < desired_effective - temp_tolerance %}"
		"  {% set unclamped = internal + heat_boost %}"
		"{% elif remote_heat >= desired_effective %}"
		"  {% set unclamped = internal + [base_stop_heat_offset - heat_diff, max_stop_heat_offset] | max %}"
		"{% else %}"
		"  {% set unclamped = internal %}"
		"{% endif %}"
		"{% set clamped = [sam_min_temp, [sam_max_temp, unclamped] | min] | max %}"
		"{{ (clamped * 2) | round(0) / 2 }}"
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
		"or (bedroom_temp_ok and bedroom_temp > cool_hot_room) "
		"or (internal_fallback and internal > cool_hot_room) }}"
	),
	"hot_cheap_cool": "{{ cheap_now and outdoor > cool_hot_outdoor and cool_hot_rooms }}",
	"precool_now": (
		"{{ cheap_now and forecast_day_max >= cool_precool_day_max "
		"and not outdoor_cooling_trend "
		"and remote_cool > cool_precool_floor "
		"and outdoor >= cool_outdoor_gate }}"
	),
	# Production sam.yaml inlines is_state('input_boolean.sam_superchill_active')
	# in these templates (HA alphabetises automation variables). Tests inject the
	# equivalent boolean as superchill_active.
	"cool_active": (
		"{{ superchill_active or (cool_season and room_too_warm) "
		"or precool_now or hot_cheap_cool }}"
	),
	"cool_use_compressor": (
		"{{ superchill_active or very_hot or precool_now or hot_cheap_cool }}"
	),
	"cool_mode": "{{ 'cool' if cool_use_compressor else 'fan_only' }}",
	"cool_setpoint": (
		"{% if superchill_active %}"
		"  {% set unclamped = internal + cool_blast_offset %}"
		"{% elif cool_use_compressor %}"
		"  {% set unclamped = internal + cool_offset %}"
		"{% else %}"
		"  {% set unclamped = internal %}"
		"{% endif %}"
		"{% set clamped = [sam_min_temp, [sam_max_temp, cool_setpoint_cap, unclamped] | min] | max %}"
		"{{ (clamped * 2) | round(0) / 2 }}"
	),
	"cool_action_label": (
		"{% if superchill_active %}Superchill"
		"{% elif cool_use_compressor and precool_now and not very_hot and not hot_cheap_cool %}Pre-cool (cheap)"
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

	living_ok = bool(scenario.get("living_room_temp_ok", True))
	bedroom_ok = bool(scenario.get("bedroom_temp_ok", True))
	# Neither room sensor: sam.yaml falls back to Sam's own sensor.
	internal_fallback = not living_ok and not bedroom_ok

	if internal_fallback:
		remote_cool = float(internal)
		remote_heat = float(internal)
	elif fan_running and living_ok and bedroom_ok:
		remote_cool = float(living)
		remote_heat = min(float(living), float(bedroom))
	else:
		remote_cool = float(living)
		remote_heat = float(living) if living_ok else float(bedroom)

	ctx.update(
		{
			"living_room_temp": float(living),
			"bedroom_temp": float(bedroom),
			# Sensors valid unless a scenario explicitly marks one offline.
			"living_room_temp_ok": living_ok,
			"bedroom_temp_ok": bedroom_ok,
			"internal_fallback": internal_fallback,
			"outdoor": float(outdoor),
			"internal": float(internal),
			"desired_base": desired_base,
			"desired_effective": desired_effective,
			"remote_cool": remote_cool,
			"remote_heat": remote_heat,
			"room_at_heat_max": living_ok and float(living) >= CONSTANTS["heat_room_max"],
			"living_above_all_targets": living_ok and float(living) > desired_effective,
			"living_overheat_diff": float(living) - desired_effective,
			# Cooling inputs (price + forecast) — read directly in sam.yaml.
			"cheap_now": bool(scenario.get("cheap_now", False)),
			"forecast_day_max": float(scenario.get("forecast_day_max", 0)),
			"forecast_out_4h": float(scenario.get("forecast_out_4h", outdoor)),
			"superchill_active": bool(scenario.get("superchill_active", False)),
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
	# Sam's ceiling sensor reads hot while the room is cold: keep heating, and
	# ask for the unit max (was fan_only under the old internal >= 27 rule).
	("unit_overreads_keeps_heating", dict(living=15, bedroom=15, outdoor=5, internal=28, control=20, fan_running=False),
		"heat", 30.0),
	# Live 24 Sep 2026: living 16.3, you set 23. Old rule cycled heat 27 /
	# fan_only 22 every ~7 min; now a steady request for the unit max.
	("live_short_cycle_fixed", dict(living=16.3, bedroom=18.7, outdoor=15, internal=27, control=23, fan_running=False),
		"heat", 30.0),
	# Near target the boost is fractional; round to the unit's 0.5 step.
	("half_degree_rounding", dict(living=18.3, bedroom=18.3, outdoor=5, internal=22, control=20, fan_running=False),
		"heat", 23.5),
	# Room ceiling from the living-room sensor: bedroom still cold (fan on,
	# remote = bedroom) and a high pre-warm target, but living has hit 27.
	("room_at_heat_max", dict(living=27.2, bedroom=18, outdoor=5, internal=24, control=28, fan_running=True),
		"fan_only", 19.0),
	("strong_overheat_guard", dict(living=25, bedroom=24, outdoor=10, internal=22, control=20, fan_running=False),
		"fan_only", 17.0),
	("warm_room_cool_out", dict(living=27, bedroom=26, outdoor=20, internal=24, control=20, fan_running=False),
		"fan_only", 19.0),
	# Live 5 Oct 2026: Tuya signed out, T&H (living) unavailable, bedroom
	# sensor long gone. Used to skip ("missing data") and leave Sam on fan_only
	# while you wanted 23. Now Sam heats as its own thermostat at 23 + 2.
	("live_tuya_signed_out_fallback", dict(living=0, bedroom=0, living_room_temp_ok=False, bedroom_temp_ok=False,
			outdoor=13, internal=19, control=23),
		"heat", 25.0),
	# Fallback ignores the over-reading ceiling sensor for mode: still heat,
	# setpoint from the target, not from internal.
	("fallback_internal_overreads", dict(living=0, bedroom=0, living_room_temp_ok=False, bedroom_temp_ok=False,
			outdoor=5, internal=27, control=20),
		"heat", 22.0),
	# Fallback on a low economy target: Sam idles at its own 18.
	("fallback_economy_target", dict(living=0, bedroom=0, living_room_temp_ok=False, bedroom_temp_ok=False,
			outdoor=10, internal=19, control=16),
		"heat", 18.0),
	# Only the bedroom sensor is down: still steered by the living room.
	("bedroom_down_uses_living", dict(living=17, bedroom=0, bedroom_temp_ok=False,
			outdoor=10, internal=20, control=20, fan_running=True),
		"heat", 23.0),
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
	# Superchill: manual blast — compressor + hard-low setpoint (internal-10
	# clamped to sam_min_temp=16), even when power is expensive and rooms are
	# only mildly warm. This is the "30°C outside, blast the house" button.
	("superchill_blast_expensive", dict(living=26, bedroom=26, outdoor=30, internal=27, cheap_now=False, forecast_day_max=32, forecast_out_4h=30, superchill_active=True),
		True, "cool", 17.0, "Superchill"),
	# Superchill wins over a cool outdoor gate that would otherwise block cooling.
	# internal-10 clamps to sam_min_temp (16).
	("superchill_even_if_cool_out", dict(living=24, bedroom=24, outdoor=18, internal=24, cheap_now=False, forecast_day_max=20, forecast_out_4h=18, superchill_active=True),
		True, "cool", 16.0, "Superchill"),
	# No room sensors on a hot day: Sam's own reading stands in for the room.
	("fallback_hot_uses_internal", dict(living=0, bedroom=0, living_room_temp_ok=False, bedroom_temp_ok=False,
			outdoor=28, internal=28, cheap_now=False, forecast_day_max=30, forecast_out_4h=28),
		True, "cool", 27.0, "Cooling"),
]


def _check_heat_scenario(entry):
	name, scenario, exp_hmode, exp_hset = entry
	ctx = build_context(scenario)

	nv = render_values(ctx, HEAT_VARS)
	new_hmode = nv["heat_mode"]
	new_hset = float(nv["heat_setpoint"])

	# Pin expected values so logic errors are caught, not just drift.
	assert new_hmode == exp_hmode, f"{name}: heat_mode {new_hmode} != expected {exp_hmode}"
	assert abs(new_hset - exp_hset) < 1e-9, f"{name}: heat_setpoint {new_hset} != expected {exp_hset}"

	# Setpoint must honour the unit's own range and 0.5 step.
	assert CONSTANTS["sam_min_temp"] <= new_hset <= CONSTANTS["sam_max_temp"], \
		f"{name}: heat setpoint {new_hset} outside clamp range"
	assert new_hset * 2 == int(new_hset * 2), f"{name}: heat setpoint {new_hset} not on 0.5 step"
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

	# Compressor must never run unless Superchill, very hot (27/27), pre-cooling,
	# or the scorcher override (hot_cheap_cool).
	if new_mode == "cool":
		assert (
			nv["superchill_active"] or nv["very_hot"]
			or nv["precool_now"] or nv["hot_cheap_cool"]
		), f"{name}: compressor engaged without superchill/very_hot/precool/hot_cheap_cool"

	# Setpoint must always honour the clamps.
	assert CONSTANTS["sam_min_temp"] <= new_set <= min(CONSTANTS["sam_max_temp"], CONSTANTS["cool_setpoint_cap"]), \
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


def test_heating_logic():
	for entry in HEAT_SCENARIOS:
		_check_heat_scenario(entry)


def test_cooling_logic():
	for entry in COOL_SCENARIOS:
		_check_cool_scenario(entry)


if __name__ == "__main__":
	test_heating_logic()
	test_cooling_logic()
	test_cheap_now_derivation()
	print(
		f"OK: {len(HEAT_SCENARIOS)} heating scenarios (expected, clamps, 0.5 step), "
		f"{len(COOL_SCENARIOS)} cooling scenarios (27/27 + scorcher override + pre-cool + sun-baked trend) and "
		f"{len(CHEAP_NOW_CASES)} cheap_now cases passed."
	)
