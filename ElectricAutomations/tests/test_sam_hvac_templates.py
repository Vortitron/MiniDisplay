#!/usr/bin/env python3
"""Behaviour-preserving unit tests for the sam.yaml HVAC decision maths.

`sam.yaml` historically repeated the same heating/cooling setpoint and
mode expressions up to four times (set_hvac_mode, set_temperature,
logbook.log, headline, status). These tests pin the decision maths down so
the de-duplication refactor (extracting the maths into the automation
`variables:` block) can be proven equivalent to the original inline copies,
and so future edits cannot silently change Sam's control behaviour.

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
	"cool_indoor_threshold": 26,
	"cool_outdoor_threshold": 25,
	"cool_indoor_min": 20,
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


# --- ORIGINAL inline expressions (copied verbatim from the pre-refactor file) ---
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
OLD_COOL_MODE = (
	"{{ 'fan_only' if remote_cool > desired_effective + temp_tolerance "
	"and outdoor < desired_effective else 'cool' }}"
)
OLD_COOL_SETPOINT = (
	"{% set unclamped = internal + (cool_offset if remote_cool > desired_effective + temp_tolerance else 0) %}"
	"{{ [sam_min_temp, [sam_max_temp, sam_setpoint_cap, unclamped] | min] | max }}"
)

# --- NEW variable definitions (must match the `variables:` block in sam.yaml) ---
NEW_VARS = {
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
	# NB: the original ties the cool_offset to "room warm" only, but the
	# fan_only decision additionally requires "outdoor cooler than target".
	# These are deliberately different conditions and must stay split.
	"cool_room_warm": "{{ remote_cool > desired_effective + temp_tolerance }}",
	"cool_fan_only": "{{ cool_room_warm and outdoor < desired_effective }}",
	"cool_mode": "{{ 'fan_only' if cool_fan_only else 'cool' }}",
	"cool_setpoint": (
		"{% set unclamped = internal + (cool_offset if cool_room_warm else 0) %}"
		"{{ [sam_min_temp, [sam_max_temp, sam_setpoint_cap, unclamped] | min] | max }}"
	),
}


def build_context(scenario: dict) -> dict:
	"""Derive the intermediate context (as sam.yaml's variables block does)."""
	ctx = dict(CONSTANTS)
	living = scenario["living"]
	bedroom = scenario["bedroom"]
	outdoor = scenario["outdoor"]
	internal = scenario["internal"]
	control = scenario["control"]
	bedroom_target_raw = scenario.get("bedroom_target")  # None or number
	fan_running = scenario["fan_running"]

	desired_base = float(control)
	if bedroom_target_raw is not None:
		desired_effective = max(desired_base, float(bedroom_target_raw))
	else:
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
			"outdoor": float(outdoor),
			"internal": float(internal),
			"desired_base": desired_base,
			"desired_effective": desired_effective,
			"remote_cool": remote_cool,
			"remote_heat": remote_heat,
			"internal_at_unit_hot": float(internal) >= CONSTANTS["sam_setpoint_cap"],
			"living_above_all_targets": float(living) > desired_effective,
			"living_overheat_diff": float(living) - desired_effective,
		}
	)
	return ctx


def new_values(ctx: dict) -> dict:
	"""Render the NEW variables sequentially (later vars use earlier ones)."""
	ctx = dict(ctx)
	for name, tmpl in NEW_VARS.items():
		ctx[name] = render_var(tmpl, ctx)
	return ctx


# (scenario, expected_heat_mode, expected_heat_setpoint, expected_cool_mode, expected_cool_setpoint)
SCENARIOS = [
	# name, scenario, expected: heat_mode, heat_setpoint, cool_mode, cool_setpoint
	# (cool_* is evaluated for every scenario because the formula is deterministic;
	#  the automation only *applies* the branch chosen by cool_active.)
	("live_now_overheat_guard", dict(living=19.2, bedroom=20.45, outdoor=14, internal=18, control=16, bedroom_target=None, fan_running=True),
		"fan_only", 16.0, "fan_only", 17.0),
	("very_cold_full_boost", dict(living=12, bedroom=13, outdoor=2, internal=18, control=20, bedroom_target=None, fan_running=False),
		"heat", 26.0, "cool", 18.0),
	("at_target_nudge_down", dict(living=20, bedroom=20, outdoor=10, internal=21, control=20, bedroom_target=None, fan_running=False),
		"heat", 19.0, "cool", 21.0),
	("mild_coasting_fan_only", dict(living=15, bedroom=15, outdoor=22, internal=18, control=20, bedroom_target=None, fan_running=False),
		"fan_only", 23.0, "cool", 18.0),
	("unit_hot", dict(living=15, bedroom=15, outdoor=5, internal=28, control=20, bedroom_target=None, fan_running=False),
		"fan_only", 23.0, "cool", 27.0),
	("strong_overheat_guard", dict(living=25, bedroom=24, outdoor=10, internal=22, control=20, bedroom_target=None, fan_running=False),
		"fan_only", 17.0, "fan_only", 21.0),
	("cooling_active_cool", dict(living=27, bedroom=26, outdoor=20, internal=24, control=20, bedroom_target=None, fan_running=False),
		"fan_only", 19.0, "cool", 23.0),
	("cooling_fan_only", dict(living=27, bedroom=26, outdoor=18, internal=23, control=20, bedroom_target=None, fan_running=False),
		"fan_only", 18.0, "fan_only", 22.0),
	("bedroom_target_wins", dict(living=18, bedroom=19, outdoor=10, internal=20, control=16, bedroom_target=21, fan_running=True),
		"heat", 23.0, "cool", 20.0),
]


def _check_scenario(entry):
	name, scenario, exp_hmode, exp_hset, exp_cmode, exp_cset = entry
	ctx = build_context(scenario)

	old_hmode = render_var(OLD_HEAT_MODE, ctx)
	old_hset = float(render_var(OLD_HEAT_SETPOINT, ctx))
	old_cmode = render_var(OLD_COOL_MODE, ctx)
	old_cset = float(render_var(OLD_COOL_SETPOINT, ctx))

	nv = new_values(ctx)
	new_hmode = nv["heat_mode"]
	new_hset = float(nv["heat_setpoint"])
	new_cmode = nv["cool_mode"]
	new_cset = float(nv["cool_setpoint"])

	# 1) Refactor must be behaviour-preserving: NEW == OLD.
	assert new_hmode == old_hmode, f"{name}: heat_mode NEW {new_hmode} != OLD {old_hmode}"
	assert abs(new_hset - old_hset) < 1e-9, f"{name}: heat_setpoint NEW {new_hset} != OLD {old_hset}"
	assert new_cmode == old_cmode, f"{name}: cool_mode NEW {new_cmode} != OLD {old_cmode}"
	assert abs(new_cset - old_cset) < 1e-9, f"{name}: cool_setpoint NEW {new_cset} != OLD {old_cset}"

	# 2) Pin expected values so logic errors are caught, not just drift.
	assert new_hmode == exp_hmode, f"{name}: heat_mode {new_hmode} != expected {exp_hmode}"
	assert abs(new_hset - exp_hset) < 1e-9, f"{name}: heat_setpoint {new_hset} != expected {exp_hset}"
	assert new_cmode == exp_cmode, f"{name}: cool_mode {new_cmode} != expected {exp_cmode}"
	assert abs(new_cset - exp_cset) < 1e-9, f"{name}: cool_setpoint {new_cset} != expected {exp_cset}"

	# 3) Setpoint must always honour the clamps.
	for sp in (new_hset, new_cset):
		assert CONSTANTS["sam_min_temp"] <= sp <= min(CONSTANTS["sam_max_temp"], CONSTANTS["sam_setpoint_cap"]), \
			f"{name}: setpoint {sp} outside clamp range"

	# 4) Native types are correct (guards against the parse_result whitespace trap).
	assert isinstance(nv["heat_fan_only"], bool), f"{name}: heat_fan_only not bool"
	assert isinstance(nv["cool_fan_only"], bool), f"{name}: cool_fan_only not bool"


def test_refactor_is_behaviour_preserving():
	for entry in SCENARIOS:
		_check_scenario(entry)


if __name__ == "__main__":
	test_refactor_is_behaviour_preserving()
	print(f"OK: {len(SCENARIOS)} scenarios passed (NEW == OLD, expected values, clamps, native types).")
