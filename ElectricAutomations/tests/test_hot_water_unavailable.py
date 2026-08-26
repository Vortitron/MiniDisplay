#!/usr/bin/env python3
"""Tests for hot-water plug absence / not-reacting state classification.

Locks in the Aug 2026 gap: when Tuya (or later Tuya Local) failed to load,
`switch.smart_plug_2_socket_1` was unavailable/unknown and the old reliability
check only matched an explicit `off` state — so no alert fired.

Run with:  python3 ElectricAutomations/tests/test_hot_water_unavailable.py
       or:  python3 -m pytest ElectricAutomations/tests/test_hot_water_unavailable.py
"""

from __future__ import annotations

ABSENT_STATES = ("unavailable", "unknown", "none", "")
NOT_REACTING_STATES = ("off",) + ABSENT_STATES


def plug_absent(state: str) -> bool:
	"""True when the entity is missing or the integration has not loaded it."""
	return state in ABSENT_STATES


def plug_not_reacting_after_on(state: str) -> bool:
	"""True when a commanded ON did not leave the plug in a live on state."""
	return state in NOT_REACTING_STATES


def notification_id_for(state: str) -> str:
	if plug_absent(state):
		return "hot_water_unavailable"
	if state == "off":
		return "hot_water_not_reacting"
	raise AssertionError(f"no alert expected for state={state!r}")


def test_on_and_off_are_present():
	assert plug_absent("on") is False
	assert plug_absent("off") is False


def test_unavailable_unknown_empty_are_absent():
	for st in ABSENT_STATES:
		assert plug_absent(st) is True, st


def test_not_reacting_includes_off_and_absent():
	assert plug_not_reacting_after_on("off") is True
	assert plug_not_reacting_after_on("unavailable") is True
	assert plug_not_reacting_after_on("on") is False


def test_notification_ids_split_absent_from_off():
	assert notification_id_for("unavailable") == "hot_water_unavailable"
	assert notification_id_for("unknown") == "hot_water_unavailable"
	assert notification_id_for("off") == "hot_water_not_reacting"


def _all_tests():
	return [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


if __name__ == "__main__":
	tests = _all_tests()
	for t in tests:
		t()
	print(f"OK: {len(tests)} hot-water unavailable tests passed.")
