#!/usr/bin/env python3
"""Unit tests for the Super-Expensive load-shedding decision maths.

Rendered with plain Jinja2 (mimicking Home Assistant's native-type parsing of
each rendered template). Pins:

1. SuperExpensive.yaml `should_be_active` — price threshold WITH hysteresis
   (latch on at/above the threshold, only release below threshold - deadband).
2. SuperExpensive.yaml `to_turn_off` — only sheds loads that are currently on
   (already-off / unavailable entities are skipped, across domains).
3. sam.yaml super-expensive guard — Sam goes off ONLY when it is just idling,
   i.e. the living room is above 19 °C (at/below that, or if unknown, Sam is
   left running because it may be actively heating).

Run with:  python3 -m pytest ElectricAutomations/tests/test_super_expensive.py
       or:  python3 ElectricAutomations/tests/test_super_expensive.py
"""

from __future__ import annotations

from ast import literal_eval

from jinja2 import Environment

_ENV = Environment()

DEADBAND = 0.15
OFF_ABOVE = 19

SHED_ENTITIES = [
	"switch.t34_smart_plug_switch_1",
	"climate.circulation_fan",
	"climate.bio_office_heat",
	"light.led_flood_light",
	"light.bio_floodlight",
]

# --- Templates copied verbatim from the YAML -------------------------------
SHOULD_BE_ACTIVE = (
	"{{ price_ok and (price >= on_level or (currently_active and price >= off_level)) }}"
)
TO_TURN_OFF = (
	"{% set ns = namespace(items=[]) %}"
	"{% for e in shed_entities %}"
	"  {% if states(e) not in ['off', 'unavailable', 'unknown', 'none', ''] %}"
	"    {% set ns.items = ns.items + [e] %}"
	"  {% endif %}"
	"{% endfor %}"
	"{{ ns.items }}"
)
SAM_GUARD = (
	"{{ super_expensive and living_room_temp_ok and living_room_temp > super_expensive_off_above }}"
)


def _parse_result(text: str):
	stripped = text.strip()
	if stripped in ("True", "False"):
		return stripped == "True"
	if stripped in ("None", ""):
		return None if stripped == "None" else ""
	try:
		return literal_eval(stripped)
	except (ValueError, SyntaxError):
		return stripped


def render(template: str, **ctx):
	return _parse_result(_ENV.from_string(template).render(**ctx))


def should_be_active(price, threshold, currently_active, price_ok=True, deadband=DEADBAND):
	return render(
		SHOULD_BE_ACTIVE,
		price=price,
		price_ok=price_ok,
		on_level=threshold,
		off_level=threshold - deadband,
		currently_active=currently_active,
	)


def to_turn_off(state_map):
	return render(
		TO_TURN_OFF,
		shed_entities=SHED_ENTITIES,
		states=lambda e: state_map.get(e, "unknown"),
	)


def sam_guard(super_expensive, living_ok, living, off_above=OFF_ABOVE):
	return render(
		SAM_GUARD,
		super_expensive=super_expensive,
		living_room_temp_ok=living_ok,
		living_room_temp=living,
		super_expensive_off_above=off_above,
	)


# --- 1) Hysteresis ---------------------------------------------------------

def test_enters_at_or_above_threshold():
	assert should_be_active(2.00, 2.0, currently_active=False) is True
	assert should_be_active(2.56, 2.0, currently_active=False) is True


def test_does_not_enter_below_threshold():
	assert should_be_active(1.99, 2.0, currently_active=False) is False


def test_stays_active_within_deadband():
	assert should_be_active(1.90, 2.0, currently_active=True) is True


def test_releases_below_deadband():
	assert should_be_active(1.80, 2.0, currently_active=True) is False


def test_no_flap_exactly_at_off_level():
	assert should_be_active(1.85, 2.0, currently_active=True) is True
	assert should_be_active(1.849, 2.0, currently_active=True) is False


def test_price_unavailable_is_never_active():
	assert should_be_active(0.0, 2.0, currently_active=True, price_ok=False) is False
	assert should_be_active(0.0, 2.0, currently_active=False, price_ok=False) is False


def test_threshold_is_tunable():
	assert should_be_active(2.56, 3.0, currently_active=False) is False
	assert should_be_active(3.10, 3.0, currently_active=False) is True


# --- 2) Shed-list filter ---------------------------------------------------

def test_shed_only_entities_that_are_on():
	# climate "on" states are e.g. heat/cool/fan_only, not literally "on".
	state_map = {
		"switch.t34_smart_plug_switch_1": "off",
		"climate.circulation_fan": "heat",
		"climate.bio_office_heat": "unavailable",  # unplugged -> skip
		"light.led_flood_light": "on",
		"light.bio_floodlight": "off",
	}
	assert to_turn_off(state_map) == ["climate.circulation_fan", "light.led_flood_light"]


def test_shed_nothing_when_all_off():
	state_map = {e: "off" for e in SHED_ENTITIES}
	assert to_turn_off(state_map) == []


def test_shed_skips_unknown_and_unavailable():
	state_map = {
		"switch.t34_smart_plug_switch_1": "on",
		"climate.circulation_fan": "unknown",
		"climate.bio_office_heat": "unavailable",
		"light.led_flood_light": "off",
		"light.bio_floodlight": "on",
	}
	assert to_turn_off(state_map) == ["switch.t34_smart_plug_switch_1", "light.bio_floodlight"]


# --- 3) sam.yaml guard (off only when idling / warm) -----------------------

def test_sam_off_when_super_expensive_and_warm():
	assert sam_guard(super_expensive=True, living_ok=True, living=20.0) is True


def test_sam_not_off_at_or_below_off_above():
	# At exactly 19 it is NOT "over 19", so Sam keeps running (may be heating).
	assert sam_guard(super_expensive=True, living_ok=True, living=19.0) is False
	assert sam_guard(super_expensive=True, living_ok=True, living=18.0) is False


def test_sam_not_off_when_temp_unknown():
	assert sam_guard(super_expensive=True, living_ok=False, living=0.0) is False


def test_sam_normal_when_not_super_expensive():
	assert sam_guard(super_expensive=False, living_ok=True, living=22.0) is False


def _run_all():
	fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
	for fn in fns:
		fn()
	print(f"OK - {len(fns)} super-expensive template tests passed")


if __name__ == "__main__":
	_run_all()
