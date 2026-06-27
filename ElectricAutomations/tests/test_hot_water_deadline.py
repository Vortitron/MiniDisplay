#!/usr/bin/env python3
"""Tests for HotWater.yaml's evening reheat-deadline logic.

Reproduces the 2026-06-15 failure: a ~16:30 shower depleted the tank, but the
pre-evening reheat deadline was hard-coded to 18:00, so by 18:00 the reheat
rule disengaged and there was no hot water for a 19:00 shower. The deadline is
now the tunable `evening_ready_hour` (20:00).

The templates below are copied verbatim from the `variables:` block of
HotWater.yaml (the evening-deadline subset). They are rendered with plain
Jinja2 and an injected fake `now()`, mirroring how Home Assistant evaluates
them. Each scenario is checked at BOTH the old ready hour (18) and the new one
(20) to demonstrate the behaviour change and lock it in.

Run with:  python3 ElectricAutomations/tests/test_hot_water_deadline.py
       or:  python3 -m pytest ElectricAutomations/tests/test_hot_water_deadline.py
"""

from __future__ import annotations

import ast
import datetime

from jinja2 import Environment

_ENV = Environment()

# --- Templates copied verbatim from HotWater.yaml --------------------------
T_CHEAPEST_2_PRE_EVENING = (
	"{% set ch = now().hour %}"
	"{% if shower_detected and ch < evening_ready_hour %}"
	"  {% set window = hourly_prices | selectattr('hour', 'ge', ch)"
	"      | selectattr('hour', 'lt', evening_ready_hour) | list %}"
	"  {% set sorted_w = window | sort(attribute='avg') %}"
	"  {{ sorted_w[:2] | map(attribute='hour') | list }}"
	"{% else %}"
	"  []"
	"{% endif %}"
)
T_MUST_HEAT = (
	"{% set mins_left = 0 if now().hour >= evening_ready_hour"
	"   else (((evening_ready_hour - now().hour) * 60) - now().minute) %}"
	"{{ shower_detected and now().hour < evening_ready_hour"
	"   and reheat_minutes_remaining > 0"
	"   and mins_left <= reheat_minutes_remaining }}"
)


def _fake_now(hour: int, minute: int = 0):
	# 2026-06-15 is a Monday (weekday() == 0); these templates are the weekday
	# branch so the exact date only needs to be a weekday.
	return datetime.datetime(2026, 6, 15, hour, minute)


def _price_curve(cheap_until: int = 18, cheap: float = 0.10, peak: float = 1.00):
	"""Today's shape: cheap up to `cheap_until`, expensive evening peak after."""
	return [{"hour": h, "avg": (cheap if h < cheap_until else peak)} for h in range(24)]


def decide(ready_hour, hour, minute, shower, remaining, prices,
           in_overnight=False, in_daytime=False):
	ctx = {
		"now": lambda: _fake_now(hour, minute),
		"evening_ready_hour": ready_hour,
		"shower_detected": shower,
		"reheat_minutes_remaining": remaining,
		"hourly_prices": prices,
	}
	pre_txt = _ENV.from_string(T_CHEAPEST_2_PRE_EVENING).render(**ctx).strip()
	cheapest = ast.literal_eval(pre_txt) if pre_txt else []
	in_pre = hour in cheapest
	must = _ENV.from_string(T_MUST_HEAT).render(**ctx).strip() == "True"
	# weekday_scheduled_heat = OR of the four sources (has_today_data == 1 path)
	weekday_heat = bool(in_overnight or in_daytime or in_pre or must)
	return {"cheapest": cheapest, "in_pre": in_pre, "must": must, "heat": weekday_heat}


def test_old_18_deadline_misses_evening_shower():
	"""With the OLD 18:00 deadline, a depleted tank gets no evening reheat."""
	prices = _price_curve(cheap_until=18)
	# 18:30, tank flagged, 70 min reheat still owed, no cheap overnight/daytime now.
	r = decide(18, 18, 30, shower=True, remaining=70, prices=prices)
	assert r["in_pre"] is False, r
	assert r["must"] is False, r
	assert r["heat"] is False, r  # <-- the bug: boiler stays OFF before a 19:00 shower


def test_new_20_deadline_covers_evening_shower():
	"""With the NEW 20:00 ready hour, the same situation keeps heating."""
	prices = _price_curve(cheap_until=18)
	r = decide(20, 18, 30, shower=True, remaining=70, prices=prices)
	assert 18 in r["cheapest"], r          # window [18,20) now considered
	assert r["in_pre"] is True, r
	assert r["heat"] is True, r            # <-- fixed: boiler keeps reheating


def test_detection_just_after_shower_heats_cheapest_hour_first():
	"""17:10 detection: cheap hour 17 is picked immediately (price-aware)."""
	prices = _price_curve(cheap_until=18)
	r = decide(20, 17, 10, shower=True, remaining=120, prices=prices)
	assert r["cheapest"][0] == 17, r       # cheapest hour in [17,20) is 17
	assert r["in_pre"] is True, r
	assert r["heat"] is True, r


def test_deadline_force_when_time_short():
	"""19:50 with 30 min still owed: deadline safety forces heating to 20:00."""
	prices = _price_curve(cheap_until=18)
	r = decide(20, 19, 50, shower=True, remaining=30, prices=prices)
	assert r["must"] is True, r            # mins_left (10) <= remaining (30)
	assert r["heat"] is True, r
	# Old 18:00 deadline would have given up entirely.
	old = decide(18, 19, 50, shower=True, remaining=30, prices=prices)
	assert old["heat"] is False, old


def test_no_shower_no_spurious_evening_heat():
	"""No depletion flag => the evening rule must not turn the boiler on."""
	prices = _price_curve(cheap_until=18)
	r = decide(20, 12, 0, shower=False, remaining=0, prices=prices)
	assert r["in_pre"] is False and r["must"] is False and r["heat"] is False, r
	# Normal daytime cheap heating is independent and still works.
	r2 = decide(20, 12, 0, shower=False, remaining=0, prices=prices, in_daytime=True)
	assert r2["heat"] is True, r2


def _all_tests():
	return [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


if __name__ == "__main__":
	tests = _all_tests()
	for t in tests:
		t()
	print(f"OK: {len(tests)} hot-water deadline tests passed.")
