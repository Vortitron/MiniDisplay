#!/usr/bin/env python3
"""Pin LoftC3 / phone-charge behaviour for iDeal LED strips.

Phone charge turns the loft off, then sets the stairs strip to red
at 3%. That red write is last, and the stairs entity is not in any
explicit turn_off. The other ISP strips stay unpainted so a bare
LoftC3 turn_on can resume their DIY. The one LoftC3 exception is the
stairs strip in the morning: it gets Effect 09 so it does not resume
the overnight red.

Run:  python3 ElectricAutomations/tests/test_loftc3_lights.py
"""

from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHARGE_PATH = ROOT / "LoftLightsOffCharge.yaml"
LOFTC3_PATH = ROOT / "LoftC3Lights.yaml"
STAIRS = "light.isp_0db21e_b21e"
OTHER_ISP = (
	"light.loft_lights",
	"light.isp_1a3c38_3c38",
)
STAIRS_NIGHT_BRIGHTNESS_PCT = 3
STAIRS_NIGHT_RGB = [255, 0, 0]
STAIRS_MORNING_EFFECT = "Effect 09"
LED_ON_COMMANDS = ("leds_on", "leds_only", "all_on")
PIXEL_8_DEVICE = "c5e32dc81cd7d30327bbd97e043130a6"
SEEKER_DEVICE = "911ce9be1f83a09b179821cb2c9c0de6"


def _actions(doc: dict) -> list:
	return doc.get("actions") or doc.get("action") or []


def _walk(node):
	if isinstance(node, dict):
		yield node
		for value in node.values():
			yield from _walk(value)
	elif isinstance(node, list):
		for item in node:
			yield from _walk(item)


def _entity_ids(target) -> list[str]:
	if target is None:
		return []
	if isinstance(target, str):
		return [target]
	if isinstance(target, dict):
		raw = target.get("entity_id")
		if raw is None:
			return []
		if isinstance(raw, str):
			return [raw]
		return list(raw)
	return []


def _paints_strip(step: dict) -> bool:
	if step.get("action") != "light.turn_on":
		return False
	data = step.get("data") or {}
	return any(
		key in data
		for key in (
			"rgb_color",
			"hs_color",
			"brightness",
			"brightness_pct",
			"effect",
			"color_name",
		)
	)


def test_charge_ends_on_stairs_dim_red():
	doc = yaml.safe_load(CHARGE_PATH.read_text())
	actions = _actions(doc)
	assert actions
	assert any(
		(step.get("target") or {}).get("floor_id") == "loft_floor"
		for step in actions
		if step.get("action") == "light.turn_off"
	)
	for step in actions:
		if step.get("action") == "light.turn_off":
			assert STAIRS not in _entity_ids(step.get("target"))
	night = actions[-1]
	assert night.get("action") == "light.turn_on"
	assert _entity_ids(night.get("target")) == [STAIRS]
	data = night.get("data") or {}
	assert data.get("brightness_pct") == STAIRS_NIGHT_BRIGHTNESS_PCT
	assert data.get("rgb_color") == STAIRS_NIGHT_RGB
	for other in OTHER_ISP:
		assert other not in _entity_ids(night.get("target"))


def test_charge_does_not_paint_other_ideal_leds():
	doc = yaml.safe_load(CHARGE_PATH.read_text())
	painted = [
		node
		for node in _walk(doc)
		if _paints_strip(node)
		and any(e in _entity_ids(node.get("target")) for e in OTHER_ISP)
	]
	assert not painted, f"other ISP strips must not be painted: {painted}"
	text = CHARGE_PATH.read_text()
	assert "ac" in text
	assert PIXEL_8_DEVICE in text
	assert SEEKER_DEVICE not in text
	assert "Seeker" not in text
	assert "scene.create" not in text
	assert "input_text.loft_stairs_restore" not in text


def test_charge_has_retrigger_cooldown():
	"""Charger sensors flap on plug-in; one plug-in must be one run."""
	doc = yaml.safe_load(CHARGE_PATH.read_text())
	templates = [
		str(c.get("value_template"))
		for c in doc.get("conditions") or []
		if c.get("condition") == "template"
	]
	assert any("last_triggered" in t and "300" in t for t in templates)


def _is_morning_stairs_effect(step: dict) -> bool:
	return (
		_entity_ids(step.get("target")) == [STAIRS]
		and (step.get("data") or {}) == {"effect": STAIRS_MORNING_EFFECT}
	)


def _morning_ifs(doc: dict) -> list[dict]:
	return [
		node
		for node in _walk(doc)
		if "if" in node
		and any("stairs_morning" in str(c.get("value_template")) for c in node["if"])
	]


def test_loftc3_bare_turn_on_for_isp_strips():
	doc = yaml.safe_load(LOFTC3_PATH.read_text())
	allowed = {
		id(step) for node in _morning_ifs(doc) for step in node.get("then") or []
		if _is_morning_stairs_effect(step)
	}
	painted = [
		node
		for node in _walk(doc)
		if _paints_strip(node)
		and any(e in _entity_ids(node.get("target")) for e in (*OTHER_ISP, STAIRS))
		and id(node) not in allowed
	]
	assert not painted, f"ISP strips must not be painted: {painted}"
	text = LOFTC3_PATH.read_text()
	assert "from_json" not in text
	assert "scene.turn_on" not in text
	assert "hs_color" not in text


def test_room_off_leaves_stairs_on():
	doc = yaml.safe_load(LOFTC3_PATH.read_text())
	room_off = None
	for node in _walk(doc):
		template = ""
		for cond in node.get("conditions") or []:
			template += str(cond.get("value_template") or "")
		if "room_off" in template:
			room_off = node
			break
	assert room_off is not None
	for step in room_off.get("sequence") or []:
		if step.get("action") == "light.turn_off":
			assert STAIRS not in _entity_ids(step.get("target"))


def _branch(doc: dict, cmd: str) -> dict:
	for node in _walk(doc):
		for cond in node.get("conditions") or []:
			if f"'{cmd}'" in str(cond.get("value_template") or ""):
				return node
	raise AssertionError(f"no branch for {cmd}")


def test_led_on_commands_set_stairs_effect_in_the_morning():
	doc = yaml.safe_load(LOFTC3_PATH.read_text())
	variables = doc["actions"][0]["variables"]
	assert variables["stairs_morning"] == "{{ 5 <= now().hour < 12 }}"
	for cmd in LED_ON_COMMANDS:
		last = _branch(doc, cmd)["sequence"][-1]
		assert "stairs_morning" in str(last.get("if")), f"{cmd}: morning check must run last"
		assert [s for s in last["then"] if _is_morning_stairs_effect(s)], f"{cmd}: no Effect 09"
	for cmd in ("room_off", "stairs_night"):
		assert "stairs_morning" not in str(_branch(doc, cmd)), f"{cmd} must not set the effect"


def main() -> None:
	test_charge_ends_on_stairs_dim_red()
	test_charge_does_not_paint_other_ideal_leds()
	test_charge_has_retrigger_cooldown()
	test_loftc3_bare_turn_on_for_isp_strips()
	test_room_off_leaves_stairs_on()
	test_led_on_commands_set_stairs_effect_in_the_morning()
	print("OK: LoftC3 / phone-charge stairs night-light tests passed.")


if __name__ == "__main__":
	main()
