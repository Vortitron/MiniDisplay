#!/usr/bin/env python3
"""Tests for the freezer power-watch decision (FreezerPowerWatch.yaml).

Mirrors the automation's choose block: clears before raises, one alert at a
time tracked in input_select.freezer_alert, maintenance suppresses raises but
never clears, and an unavailable running sensor does nothing.

Run with:  python3 ElectricAutomations/tests/test_freezer_watch.py
       or:  python3 -m pytest ElectricAutomations/tests/test_freezer_watch.py
"""

from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN_LIMIT_H = 3
IDLE_LIMIT_H = 3


def decide(running: str, held_h: float, alert: str, maintenance: bool) -> str | None:
	"""Return the branch FreezerPowerWatch takes, or None for no action."""
	if running == "off" and alert == "running_long":
		return "clear_running_long"
	if running == "on" and alert == "idle_long":
		return "clear_idle_long"
	if running == "on" and held_h >= RUN_LIMIT_H and alert != "running_long" and not maintenance:
		return "raise_running_long"
	if running == "off" and held_h >= IDLE_LIMIT_H and alert != "idle_long" and not maintenance:
		return "raise_idle_long"
	return None


def test_normal_cycling_is_quiet():
	assert decide("on", 0.6, "none", False) is None
	assert decide("off", 1.2, "none", False) is None


def test_running_too_long_raises_once():
	assert decide("on", 3.0, "none", False) == "raise_running_long"
	assert decide("on", 4.5, "running_long", False) is None


def test_idle_too_long_raises_once():
	assert decide("off", 3.1, "none", False) == "raise_idle_long"
	assert decide("off", 9.0, "idle_long", False) is None


def test_recovery_clears():
	assert decide("off", 0.0, "running_long", False) == "clear_running_long"
	assert decide("on", 0.0, "idle_long", False) == "clear_idle_long"


def test_missed_clear_resolves_before_opposite_raise():
	# Stopped while unavailable, and has now been off long enough to look idle:
	# drop the stale running alert first; the next poll raises idle.
	assert decide("off", 5.0, "running_long", False) == "clear_running_long"


def test_maintenance_suppresses_raises_not_clears():
	assert decide("off", 8.0, "none", True) is None
	assert decide("on", 8.0, "none", True) is None
	assert decide("on", 0.1, "idle_long", True) == "clear_idle_long"


def test_unavailable_sensor_does_nothing():
	for alert in ("none", "running_long", "idle_long"):
		assert decide("unavailable", 10.0, alert, False) is None


def test_yaml_limits_and_ids_match():
	watch = yaml.safe_load((ROOT / "FreezerPowerWatch.yaml").read_text())
	assert watch["id"] == "freezer_power_watch"
	assert watch["variables"]["run_limit_h"] == RUN_LIMIT_H
	assert watch["variables"]["idle_limit_h"] == IDLE_LIMIT_H
	branches = watch["actions"][1]["choose"]
	conds = [b["conditions"][0]["value_template"] for b in branches]
	# Clears must come before raises (see test_missed_clear_...).
	assert "alert == 'running_long'" in conds[0]
	assert "alert == 'idle_long'" in conds[1]
	assert "run_limit_h" in conds[2]
	assert "idle_limit_h" in conds[3]
	ids = {yaml.safe_load(p.read_text())["id"] for p in ROOT.glob("Freezer*.yaml")}
	assert ids == {"freezer_keep_on", "freezer_power_watch", "freezer_plug_unavailable"}


def _all_tests():
	return [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


if __name__ == "__main__":
	for t in _all_tests():
		t()
		print(f"  ✓ {t.__name__}")
	print("All freezer watch tests passed.")
