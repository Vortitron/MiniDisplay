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

from jinja2 import Environment, pass_context


def _ha_min(value):
	"""Live HA min filter semantics: iterable only (TypeError on scalar)."""
	return min(value)


def _ha_max(value):
	"""Live HA max filter semantics: iterable only (TypeError on scalar)."""
	return max(value)


_ENV = Environment()
_ENV.filters["min"] = _ha_min
_ENV.filters["max"] = _ha_max


@pass_context
def _is_state(ctx, entity_id, state):
	"""HA is_state(), backed by a `_states` dict in the render context.

	Lets the chain templates below stay byte-identical to DaytimeCheapHeat.yaml
	instead of being paraphrased into plain variables.
	"""
	return ctx.get("_states", {}).get(entity_id) == state


@pass_context
def _states_fn(ctx, entity_id):
	return ctx.get("_states", {}).get(entity_id, "unknown")


@pass_context
def _state_attr(ctx, entity_id, attr):
	return ctx.get("_attrs", {}).get(entity_id, {}).get(attr)


_ENV.globals["is_state"] = _is_state
_ENV.globals["states"] = _states_fn
_ENV.globals["state_attr"] = _state_attr


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
	"{% elif use_prewarm_25_evening %}"
	"  {{ prewarm_control_target }}"
	"{% elif cheap_for_boost %}"
	"  {% set boosted = [d + 3, prewarm_max] | min %}"
	"  {% if living_ok and living_temp >= boosted - 0.5 %}"
	"    {{ d }}"
	"  {% else %}"
	"    {{ boosted }}"
	"  {% endif %}"
	"{% elif electricity_expensive_now %}"
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
		on_fixed_price=False,
		electricity_expensive_now=True,
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
	# Relative-dear but below today's average must not coast below a higher
	# desired (10 Sep 2026 morning: rank 15/11 at 0.66 SEK vs avg 1.23).
	assert float(render(CONTROL_TEMPLATE, _control_ctx(
		cheap_for_boost=False, use_prewarm_25_evening=False,
		electricity_expensive_now=False, desired=20))) == 20
	# Genuinely expensive still coasts to 16 even if desired is higher.
	assert float(render(CONTROL_TEMPLATE, _control_ctx(
		cheap_for_boost=False, use_prewarm_25_evening=False,
		electricity_expensive_now=True, desired=20))) == 16
	# Cheap + very cold outside no longer means a flat 25°C: it routes through
	# the model-sized pre-warm like every other cheap hour (Sep 2026).
	assert float(render(CONTROL_TEMPLATE, _control_ctx(outside_temp=5))) == 24.2


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


# --- Sep 2026: absolute price gate + bounded pre-warm window -----------------
# Must match DaytimeCheapHeat.yaml exactly.
NORDPOOL = "sensor.nordpool_kwh_se4_sek_3_10_025"

PRICE_GATE_CHAIN = {
	"electricity_cheap_now": "{{ price_rank < price_rank_4h and not on_fixed_price }}",
	"price_genuinely_cheap": (
		"{{ is_state('input_boolean.cheap_leccy', 'on') "
		"or price_rank <= cheap_rank_ceiling }}"
	),
	"cheap_for_boost": (
		"{{ electricity_cheap_now and price_genuinely_cheap "
		"and not evening_hours_block_boost "
		"and not suppress_morning_heat }}"
	),
	"nordpool_price": "{{ states('sensor.nordpool_kwh_se4_sek_3_10_025') | float(0) }}",
	"nordpool_average": (
		"{{ state_attr('sensor.nordpool_kwh_se4_sek_3_10_025', 'average') "
		"| float(nordpool_price) }}"
	),
	"price_genuinely_expensive": "{{ nordpool_price >= nordpool_average }}",
	"electricity_expensive_now": (
		"{{ price_rank > price_rank_4h and price_genuinely_expensive "
		"and not tv_on and not on_fixed_price }}"
	),
}

WINDOW_CHAIN = {
	"cold_outside": "{{ outside_temp < cold_outside_threshold }}",
	"prewarm_window_start": "{{ 13 if cold_outside else 15 }}",
	"approaching_evening": (
		"{{ current_hour | int >= prewarm_window_start | int "
		"and current_hour | int < 19 }}"
	),
}

USE_PREWARM = (
	"{{ cheap_for_boost and approaching_evening"
	" and not prewarm_skip_comfortable"
	" and not prewarm_skip_mild_night"
	" and not prewarm_skip_on_track"
	" and (not living_ok or living_temp < 19) }}"
)

GATE_CONSTS = {
	"cheap_rank_ceiling": 11,
	"cold_outside_threshold": 10,
	"on_fixed_price": False,
	"evening_hours_block_boost": False,
	"suppress_morning_heat": False,
	"tv_on": False,
}


def _nordpool(price, average):
	return {
		"_states": {
			"input_boolean.cheap_leccy": "off",
			NORDPOOL: str(price),
		},
		"_attrs": {NORDPOOL: {"average": average}},
	}


def test_price_gate_rejects_the_run_up_into_a_peak():
	"""Real Nordpool shape, 3 Sep 2026 (SE4), replayed through both rank
	templates. The relative test alone calls the run-up into each peak "cheap"."""
	# hour: (rank, rank_4h, SEK/kWh) — hours 6 and 18 are among the DEAREST of
	# the day, yet rank < rank_4h because the hours after them are worse still.
	day = {
		3: (1, 8, 0.32),
		6: (15, 18, 1.85),
		14: (6, 9, 0.51),
		18: (17, 21, 2.14),
	}
	expected_boost = {3: True, 6: False, 14: True, 18: False}
	for hour, (rank, rank4, _price) in day.items():
		ctx = _render_chain(PRICE_GATE_CHAIN, dict(
			GATE_CONSTS, price_rank=rank, price_rank_4h=rank4,
			_states={"input_boolean.cheap_leccy": "off"}))
		# The relative signal fires for all four of these hours...
		assert ctx["electricity_cheap_now"] is True, hour
		# ...but only the genuinely cheap ones survive the absolute bar.
		assert ctx["cheap_for_boost"] is expected_boost[hour], (
			f"hour {hour} (rank {rank}): {ctx['cheap_for_boost']}")


def test_cheap_leccy_is_an_absolute_escape_hatch():
	"""A dear-looking rank still boosts if the day's average is dearer still."""
	ctx = _render_chain(PRICE_GATE_CHAIN, dict(
		GATE_CONSTS, price_rank=15, price_rank_4h=18,
		_states={"input_boolean.cheap_leccy": "on"}))
	assert ctx["cheap_for_boost"] is True


def test_below_average_morning_is_not_called_expensive():
	"""Live 10 Sep 2026 09:40 SE4: 0.657 SEK, daily avg 1.23, rank 15 vs 4h 11.

	Overnight was 0.16 SEK so this hour ranked in the dearer half of the day,
	and the relative test (rank > rank_4h) called it 'Electricity expensive'.
	In kronor it was cheap — below today's average, with an evening of 4–6 SEK.
	"""
	live = _render_chain(PRICE_GATE_CHAIN, dict(
		GATE_CONSTS, price_rank=15, price_rank_4h=11, **_nordpool(0.657, 1.234875)))
	assert live["electricity_cheap_now"] is False
	assert live["price_genuinely_cheap"] is False
	assert live["price_genuinely_expensive"] is False
	assert live["electricity_expensive_now"] is False
	# The relative-only test (what the MiniDisplay was showing) still fires.
	assert live["price_rank"] > live["price_rank_4h"]

	# Same ranks, but a price that really is above today's average -> coast.
	dear = _render_chain(PRICE_GATE_CHAIN, dict(
		GATE_CONSTS, price_rank=15, price_rank_4h=11, **_nordpool(2.5, 1.234875)))
	assert dear["price_genuinely_expensive"] is True
	assert dear["electricity_expensive_now"] is True

	# TV on still protects comfort even when the price is genuinely dear.
	watching = _render_chain(PRICE_GATE_CHAIN, dict(
		GATE_CONSTS, tv_on=True, price_rank=18, price_rank_4h=10,
		**_nordpool(2.5, 1.234875)))
	assert watching["electricity_expensive_now"] is False


def test_prewarm_window_widens_when_cold():
	cases = [
		# (outside, hour, in window?)
		(15, 14, False), (15, 15, True), (15, 18, True), (15, 19, False),
		(5, 12, False), (5, 13, True), (5, 18, True), (5, 19, False),
		(5, 3, False), (15, 3, False),  # never overnight
	]
	for outside, hour, expected in cases:
		ctx = _render_chain(WINDOW_CHAIN, dict(
			GATE_CONSTS, outside_temp=outside, current_hour=hour))
		assert ctx["approaching_evening"] is expected, (
			f"outside={outside} hour={hour}: {ctx['approaching_evening']}")
		assert ctx["prewarm_window_start"] == (13 if outside < 10 else 15)


# The pre-Sep-2026 ladder, kept to prove what the change actually stops.
OLD_COLD_BRANCH_CONTROL = (
	CONTROL_TEMPLATE
	.replace(
		"{% elif use_prewarm_25_evening %}",
		"{% elif cheap_for_boost and outside_temp < 10 %}"
		"  {{ prewarm_max }}"
		"{% elif use_prewarm_25_evening %}",
	)
)


def test_no_overnight_25c_blast():
	"""The headline fix: a cold, genuinely cheap 03:00 no longer drives the
	house to 25°C. At the learned tau (~6 h) only ~7% of that overshoot would
	still be there at 19:00, so it was ~93% wasted."""
	gate = _render_chain(PRICE_GATE_CHAIN, dict(
		GATE_CONSTS, price_rank=1, price_rank_4h=8,
		_states={"input_boolean.cheap_leccy": "off"}))
	window = _render_chain(WINDOW_CHAIN, dict(
		GATE_CONSTS, outside_temp=2, current_hour=3))
	assert gate["cheap_for_boost"] is True      # genuinely cheap
	assert window["approaching_evening"] is False  # but nowhere near evening

	use_prewarm = render(USE_PREWARM, dict(
		cheap_for_boost=gate["cheap_for_boost"],
		approaching_evening=window["approaching_evening"],
		prewarm_skip_comfortable=False,
		prewarm_skip_mild_night=False,
		prewarm_skip_on_track=False,
		living_ok=True, living_temp=16.5))
	assert use_prewarm is False

	ctx = _control_ctx(
		cheap_for_boost=True, use_prewarm_25_evening=use_prewarm,
		outside_temp=2, living_temp=16.5, desired=16)
	# New: falls through to the modest +3 boost, with its already-warm skip.
	assert float(render(CONTROL_TEMPLATE, ctx)) == 19.0
	# Old: the flat cold branch won outright, at 03:00, every cheap hour.
	assert float(render(OLD_COLD_BRANCH_CONTROL, ctx)) == 25.0


def test_cold_afternoon_still_respects_the_skip_guards():
	"""The other half of the fix: below 10°C the three thermal-model guards
	used to be unreachable, because the flat cold branch sat above them."""
	use_prewarm = render(USE_PREWARM, dict(
		cheap_for_boost=True, approaching_evening=True,
		prewarm_skip_comfortable=True,   # room is already at 19.5
		prewarm_skip_mild_night=False,
		prewarm_skip_on_track=False,
		living_ok=True, living_temp=19.5))
	assert use_prewarm is False

	ctx = _control_ctx(
		cheap_for_boost=True, use_prewarm_25_evening=use_prewarm,
		outside_temp=4, living_temp=19.5, desired=16)
	# New: room is already warm enough, so no boost at all.
	assert float(render(CONTROL_TEMPLATE, ctx)) == 16.0
	# Old: heated an already-warm room to 25°C because it was cold outside.
	assert float(render(OLD_COLD_BRANCH_CONTROL, ctx)) == 25.0


if __name__ == "__main__":
	tests = [
		test_old_prewarm_target_raises_when_living_below_floor,
		test_new_prewarm_target_values,
		test_control_prewarm_branch_now_reachable,
		test_control_other_branches_unchanged,
		test_hours_until_19,
		test_hot_day_morning_skip,
		test_price_gate_rejects_the_run_up_into_a_peak,
		test_cheap_leccy_is_an_absolute_escape_hatch,
		test_below_average_morning_is_not_called_expensive,
		test_prewarm_window_widens_when_cold,
		test_no_overnight_25c_blast,
		test_cold_afternoon_still_respects_the_skip_guards,
	]
	for fn in tests:
		fn()
	print(f"OK: {len(tests)} DaytimeCheapHeat test groups passed.")
