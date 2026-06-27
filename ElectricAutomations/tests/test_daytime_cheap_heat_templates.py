#!/usr/bin/env python3
"""Unit tests for the DaytimeCheapHeat.yaml decision templates.

Covers the two June 2026 bugs:

1. `prewarm_control_target` used "[a, b, c] | min | max" which raises
   TypeError ('int' object is not iterable) whenever living_temp < 19.
   Because automation variables are rendered eagerly, this killed EVERY
   run of Daytime Cheap Heat while the living room was below 19°C —
   desired/control/reason froze at their last values (observed live:
   stale since 23:45 the previous night).
2. The `control` and `reason` templates referenced `use_prewarm_evening`,
   but the variable is named `use_prewarm_25_evening`. Undefined names are
   silently falsy in `{% if %}`, so the variable pre-warm branch was dead
   code and afternoon pre-warms fell through to the flat "+3°C" boost.

...and a third bug found while verifying the fix live:

3. `hours_until_19` used "(19 - hour) | max(0)". On the live HA the min/max
   filters accept an ITERABLE ONLY (verified via /api/template: the varargs
   form raises TypeError 'int' object is not iterable). So every run before
   19:00 died at this variable too. List form "[x, 0] | max" is required.

The Jinja environment below mirrors the live HA semantics: min/max operate
on a single iterable argument; scalar input raises TypeError.

Run with:  python3 ElectricAutomations/tests/test_daytime_cheap_heat_templates.py
(no pytest dependency, same as test_sam_hvac_templates.py)
"""

from __future__ import annotations

from ast import literal_eval

from jinja2 import Environment


def _ha_min(value):
	"""Live HA min filter semantics: iterable only (TypeError on scalar)."""
	return min(value)


def _ha_max(value):
	"""Live HA max filter semantics: iterable only (TypeError on scalar)."""
	return max(value)


_ENV = Environment()
_ENV.filters["min"] = _ha_min
_ENV.filters["max"] = _ha_max


def _parse_result(text: str):
	stripped = text.strip()
	if stripped in ("True", "False"):
		return stripped == "True"
	try:
		return literal_eval(stripped)
	except (ValueError, SyntaxError):
		return stripped


def render(template: str, ctx: dict):
	return _parse_result(_ENV.from_string(template).render(**ctx))


# --- Templates ---------------------------------------------------------------
OLD_PREWARM_TARGET = (
	"{% if living_ok and living_temp >= evening_hold_floor %}"
	"  {{ evening_comfort_target }}"
	"{% else %}"
	"  {% set deficit = evening_hold_floor - living_temp %}"
	"  {% set needed = evening_hold_floor + 2 + (deficit * 2) %}"
	"  {{ [evening_comfort_target, needed, prewarm_max] | min | max }}"
	"{% endif %}"
)

# Must match DaytimeCheapHeat.yaml `prewarm_control_target` exactly.
NEW_PREWARM_TARGET = (
	"{% if living_ok and living_temp >= evening_hold_floor %}"
	"  {{ evening_comfort_target }}"
	"{% else %}"
	"  {% set deficit = evening_hold_floor - living_temp %}"
	"  {% set needed = evening_hold_floor + 2 + (deficit * 2) %}"
	"  {{ [[needed, prewarm_max] | min, evening_comfort_target] | max }}"
	"{% endif %}"
)

# Must match DaytimeCheapHeat.yaml `control` exactly (post-fix).
CONTROL_TEMPLATE = (
	"{% set d = desired | float %}"
	"{% if holiday_mode %}"
	"  10"
	"{% elif manual_override or lock_active_now %}"
	"  {{ d }}"
	"{% elif evening_hours %}"
	"  {% if living_ok and living_temp >= evening_hold_floor %}"
	"    {{ d }}"
	"  {% else %}"
	"    {{ [d, evening_hold_floor + 1] | max }}"
	"  {% endif %}"
	"{% elif cheap_for_boost and outside_temp < 10 %}"
	"  {{ prewarm_max }}"
	"{% elif use_prewarm_25_evening %}"
	"  {{ prewarm_control_target }}"
	"{% elif cheap_for_boost %}"
	"  {% set boosted = [d + 3, prewarm_max] | min %}"
	"  {% if living_ok and living_temp >= boosted - 0.5 %}"
	"    {{ d }}"
	"  {% else %}"
	"    {{ boosted }}"
	"  {% endif %}"
	"{% elif price_rank > price_rank_4h and not tv_on %}"
	"  16"
	"{% else %}"
	"  {{ d }}"
	"{% endif %}"
)

BASE = {
	"evening_hold_floor": 19,
	"evening_comfort_target": 20,
	"prewarm_max": 25,
	"living_ok": True,
}


def test_old_prewarm_target_raises_when_living_below_floor():
	"""Proof of bug 1: the old chain dies for living < 19 (live failure)."""
	ctx = dict(BASE, living_temp=17.4)
	try:
		render(OLD_PREWARM_TARGET, ctx)
	except TypeError:
		pass
	else:
		raise AssertionError("old template should raise TypeError for living < floor")


def test_new_prewarm_target_values():
	cases = [
		(19.0, 20),    # at floor -> comfort target (if-branch)
		(19.8, 20),    # warm -> comfort target (last successful live run)
		(17.4, 24.2),  # live morning value: 21 + 2*1.6
		(18.9, 21.2),  # just below floor: 21 + 2*0.1
		(10.0, 25),    # very cold -> capped at prewarm_max
		(0.0, 25),     # absurd cold -> still capped
	]
	for living, expected in cases:
		got = render(NEW_PREWARM_TARGET, dict(BASE, living_temp=living))
		assert abs(float(got) - expected) < 1e-9, f"living={living}: {got} != {expected}"
	# Both variants agree on the non-broken branch (living >= floor).
	for living in (19.0, 20.5, 25.0):
		ctx = dict(BASE, living_temp=living)
		assert render(OLD_PREWARM_TARGET, ctx) == render(NEW_PREWARM_TARGET, ctx)


def _control_ctx(**over):
	ctx = dict(
		BASE,
		desired=16,
		holiday_mode=False,
		manual_override=False,
		lock_active_now=False,
		evening_hours=False,
		cheap_for_boost=True,
		outside_temp=12,
		use_prewarm_25_evening=True,
		prewarm_control_target=24.2,
		price_rank=6,
		price_rank_4h=4,
		tv_on=False,
		living_temp=17.4,
	)
	ctx.update(over)
	return ctx


def test_control_prewarm_branch_now_reachable():
	"""Proof of bug 2: with the typo the branch was dead; fixed it fires."""
	# Fixed template, flag true -> the computed pre-warm target is used.
	assert float(render(CONTROL_TEMPLATE, _control_ctx())) == 24.2
	# Flag false -> falls through to flat +3 boost (16+3=19).
	assert float(render(CONTROL_TEMPLATE, _control_ctx(use_prewarm_25_evening=False))) == 19.0
	# Old behaviour reproduced: an undefined flag name is silently falsy,
	# so the branch never fired (this is what the typo did in production).
	broken = CONTROL_TEMPLATE.replace(
		"{% elif use_prewarm_25_evening %}", "{% elif use_prewarm_evening_typo %}"
	)
	assert float(render(broken, _control_ctx())) == 19.0


def test_control_other_branches_unchanged():
	assert float(render(CONTROL_TEMPLATE, _control_ctx(holiday_mode=True))) == 10
	assert float(render(CONTROL_TEMPLATE, _control_ctx(manual_override=True, desired=19.9))) == 19.9
	# Evening, cold room -> hold floor + 1.
	assert float(render(CONTROL_TEMPLATE, _control_ctx(
		evening_hours=True, desired=20, living_temp=17.0))) == 20
	assert float(render(CONTROL_TEMPLATE, _control_ctx(
		evening_hours=True, desired=16, living_temp=17.0))) == 20  # max(16, 19+1)
	# Expensive, no TV, no boost -> 16.
	assert float(render(CONTROL_TEMPLATE, _control_ctx(
		cheap_for_boost=False, use_prewarm_25_evening=False))) == 16
	# Cheap + very cold outside -> max overheat.
	assert float(render(CONTROL_TEMPLATE, _control_ctx(outside_temp=5))) == 25


# Must match DaytimeCheapHeat.yaml `hours_until_19` exactly (post-fix).
HOURS_UNTIL_19 = (
	"{% if current_hour | int < 19 %}"
	"  {{ [19 - current_hour | int, 0] | max }}"
	"{% else %}"
	"  0"
	"{% endif %}"
)


def test_hours_until_19():
	"""Bug 3: the varargs form "x | max(0)" dies on this HA; list form works."""
	for hour, expected in [(0, 19), (7, 12), (11, 8), (18, 1), (19, 0), (23, 0)]:
		got = render(HOURS_UNTIL_19, {"current_hour": hour})
		assert got == expected, f"hour={hour}: {got} != {expected}"
	# The old varargs form raises on this HA version (and in this harness).
	try:
		render("{{ (19 - 7) | max(0) }}", {})
	except TypeError:
		pass
	else:
		raise AssertionError("varargs max should raise TypeError (live HA semantics)")


# --- Summer: skip morning heating on a hot day (Jun 2026) --------------------
# Chain of derived flags, rendered in order (mirrors DaytimeCheapHeat.yaml).
SUPPRESS_CHAIN = {
	"hot_day_ahead": "{{ forecast_day_max > hot_day_max_threshold }}",
	"is_morning": "{{ current_hour | int < morning_end_hour }}",
	"really_cold": (
		"{{ (living_ok and living_temp < really_cold_living) "
		"or outside_temp < really_cold_outside }}"
	),
	"suppress_morning_heat": "{{ hot_day_ahead and is_morning and not really_cold }}",
	"cheap_for_boost": (
		"{{ electricity_cheap_now and not evening_hours_block_boost "
		"and not suppress_morning_heat }}"
	),
}

SUPPRESS_CONSTS = {
	"hot_day_max_threshold": 25,
	"morning_end_hour": 12,
	"really_cold_living": 16,
	"really_cold_outside": 5,
	"living_ok": True,
}


def _render_chain(defs: dict, ctx: dict) -> dict:
	ctx = dict(ctx)
	for name, tmpl in defs.items():
		ctx[name] = render(tmpl, ctx)
	return ctx


def test_hot_day_morning_skip():
	"""A hot day forecast suppresses the cheap-power morning warm-up, unless
	it's genuinely cold right now, and never touches the afternoon pre-warm."""
	base = dict(SUPPRESS_CONSTS, evening_hours_block_boost=False, electricity_cheap_now=True)

	# Hot day, morning, not cold -> suppressed (no morning boost).
	hot_morning = _render_chain(SUPPRESS_CHAIN, dict(
		base, forecast_day_max=28, current_hour=8, living_temp=20, outside_temp=15))
	assert hot_morning["suppress_morning_heat"] is True
	assert hot_morning["cheap_for_boost"] is False
	# control with the gate off (cheap_for_boost False) -> stays at desired 16.
	c_fixed = float(render(CONTROL_TEMPLATE, _control_ctx(
		cheap_for_boost=False, use_prewarm_25_evening=False,
		outside_temp=15, living_temp=17, price_rank=4, price_rank_4h=6)))
	assert c_fixed == 16, f"hot morning should not boost: {c_fixed}"
	# Without the fix it would have boosted to 19 (desired + 3).
	c_unfixed = float(render(CONTROL_TEMPLATE, _control_ctx(
		cheap_for_boost=True, use_prewarm_25_evening=False,
		outside_temp=15, living_temp=17, price_rank=4, price_rank_4h=6)))
	assert c_unfixed == 19, f"old behaviour should boost to 19: {c_unfixed}"

	# "Unless really cold": a frosty room keeps the morning warm-up.
	cold_morning = _render_chain(SUPPRESS_CHAIN, dict(
		base, forecast_day_max=28, current_hour=8, living_temp=14, outside_temp=15))
	assert cold_morning["suppress_morning_heat"] is False
	assert cold_morning["cheap_for_boost"] is True
	# Frosty outside also counts as "really cold".
	frosty_out = _render_chain(SUPPRESS_CHAIN, dict(
		base, forecast_day_max=28, current_hour=8, living_temp=20, outside_temp=2))
	assert frosty_out["suppress_morning_heat"] is False

	# Mild day -> never suppressed.
	mild = _render_chain(SUPPRESS_CHAIN, dict(
		base, forecast_day_max=20, current_hour=8, living_temp=20, outside_temp=15))
	assert mild["suppress_morning_heat"] is False

	# Hot afternoon (not morning) -> the evening pre-warm path is untouched.
	hot_afternoon = _render_chain(SUPPRESS_CHAIN, dict(
		base, forecast_day_max=28, current_hour=16, living_temp=20, outside_temp=15))
	assert hot_afternoon["suppress_morning_heat"] is False


if __name__ == "__main__":
	tests = [
		test_old_prewarm_target_raises_when_living_below_floor,
		test_new_prewarm_target_values,
		test_control_prewarm_branch_now_reachable,
		test_control_other_branches_unchanged,
		test_hours_until_19,
		test_hot_day_morning_skip,
	]
	for fn in tests:
		fn()
	print(f"OK: {len(tests)} DaytimeCheapHeat test groups passed.")
