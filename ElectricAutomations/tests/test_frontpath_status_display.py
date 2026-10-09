#!/usr/bin/env python3
"""FrontPath screen lines and onboard LED.

Mirrors esphome/FrontPath/frontpath-display.yaml and the rain/temperature
variables in frontpath_lights_automations_simple.yaml.

Run:  python3 ElectricAutomations/tests/test_frontpath_status_display.py
"""

from __future__ import annotations

import math
import unittest

ROAD_E4 = "E4"
ROAD_GAMLA = "Gamla E4"
RAIN_CONDITIONS = frozenset(
	{"rainy", "pouring", "lightning-rainy", "hail", "snowy", "snowy-rainy"}
)
PRECIP_MM = 0.2
HOURS_NONE = 48
TEMP_MISSING = 99.0
LINE_WIDTH = 22
BACKLIGHT_ON_BELOW_LUX = 15.0
BACKLIGHT_OFF_ABOVE_LUX = 40.0


def backlight_wanted(lux: float, currently_on: bool) -> bool:
	"""Night needs the lamp. The blue-hour Dusk flag is off once it is fully dark."""
	assert lux >= 0.0
	if lux < BACKLIGHT_ON_BELOW_LUX:
		return True
	if lux > BACKLIGHT_OFF_ABOVE_LUX:
		return False
	return currently_on


def onboard_led(markaryd_diverted: bool | None, orkelljunga_diverted: bool | None) -> str:
	"""Blinks while either journey is off its usual road (HA works out `diverted`).

	Both are usually Gamla E4; the pool line stands in for Ljungaskog. Ice is shown on the
	screen only; the WS2812 that used to show it was never fitted.
	"""
	return "blink" if (markaryd_diverted or orkelljunga_diverted) else "off"


def hours_until_rain(entries: list[dict], now_ts: float) -> tuple[int, float | None]:
	"""First future hour with real precipitation. 48 means nothing in the window."""
	assert now_ts >= 0
	for entry in entries:
		ts = entry.get("datetime")
		if ts is None or ts < now_ts:
			continue
		precip = float(entry.get("precipitation") or 0)
		cond = entry.get("condition") or ""
		if precip >= PRECIP_MM or cond in RAIN_CONDITIONS:
			# Ceil so 30 minutes is "1h", not "now". Exact hours stay exact.
			hours = int(math.ceil((ts - now_ts) / 3600 - 1e-9))
			return max(hours, 0), entry.get("temperature")
	return HOURS_NONE, None


def next_temperature(entries: list[dict], now_ts: float) -> float:
	for entry in entries:
		ts = entry.get("datetime")
		temp = entry.get("temperature")
		if ts is None or ts < now_ts or temp is None:
			continue
		return round(float(temp), 1)
	return TEMP_MISSING


def journey_line(place: str, minutes: str | None, road: str | None) -> str:
	if not minutes or minutes in {"unknown", "unavailable", "none"}:
		mins = "--"
	else:
		mins = minutes.split(".", 1)[0]
	if road == ROAD_E4:
		tag = "E4"
	elif road == ROAD_GAMLA:
		tag = "Gamla"
	else:
		tag = "--"
	line = f"{place} {mins}m {tag}"
	return line[:LINE_WIDTH]


def rain_line(hours: float | None) -> str:
	if hours is None:
		return "Rain --"
	whole = int(round(hours))
	if whole >= HOURS_NONE:
		return "No rain"
	if whole <= 0:
		return "Rain now"
	return f"Rain {whole}h"


def temp_line(temp_c: float | None, ice: bool) -> str:
	if temp_c is None or temp_c >= 90:
		text = "--"
	else:
		rounded = round(float(temp_c), 1)
		if abs(rounded - round(rounded)) < 0.05:
			text = f"{rounded:.0f} C"
		else:
			text = f"{rounded:.1f} C"
	if ice:
		text += " ice"
	return text


class BacklightTests(unittest.TestCase):
	def test_night_and_day(self) -> None:
		self.assertTrue(backlight_wanted(0.5, False))
		self.assertFalse(backlight_wanted(80.0, True))

	def test_hysteresis_band_holds(self) -> None:
		self.assertTrue(backlight_wanted(25.0, True))
		self.assertFalse(backlight_wanted(25.0, False))


class LedModeTests(unittest.TestCase):
	def test_usual_roads_are_off(self) -> None:
		self.assertEqual(onboard_led(False, False), "off")

	def test_either_journey_diverted_blinks(self) -> None:
		self.assertEqual(onboard_led(True, False), "blink")
		self.assertEqual(onboard_led(False, True), "blink")

	def test_unknown_does_not_blink(self) -> None:
		self.assertEqual(onboard_led(None, None), "off")

class ForecastTests(unittest.TestCase):
	def test_first_wet_hour(self) -> None:
		now = 1_000_000.0
		entries = [
			{"datetime": now - 3600, "precipitation": 5, "temperature": 1, "condition": "rainy"},
			{"datetime": now + 3600, "precipitation": 0, "temperature": 8, "condition": "cloudy"},
			{"datetime": now + 4 * 3600, "precipitation": 1.2, "temperature": 7, "condition": "rainy"},
		]
		hours, temp = hours_until_rain(entries, now)
		self.assertEqual(hours, 4)
		self.assertEqual(temp, 7)
		self.assertEqual(next_temperature(entries, now), 8.0)

	def test_condition_counts_when_precipitation_is_missing(self) -> None:
		now = 1_000_000.0
		entries = [
			{"datetime": now + 1800, "precipitation": None, "temperature": 3, "condition": "snowy"},
		]
		hours, _temp = hours_until_rain(entries, now)
		self.assertEqual(hours, 1)

	def test_trace_rain_is_ignored(self) -> None:
		now = 1_000_000.0
		entries = [
			{"datetime": now + 3600, "precipitation": 0.1, "temperature": 9, "condition": "cloudy"},
		]
		self.assertEqual(hours_until_rain(entries, now)[0], HOURS_NONE)

	def test_empty_forecast(self) -> None:
		self.assertEqual(hours_until_rain([], 10)[0], HOURS_NONE)
		self.assertEqual(next_temperature([], 10), TEMP_MISSING)


class LineTests(unittest.TestCase):
	def test_journey_lines_fit(self) -> None:
		self.assertEqual(journey_line("Markaryd", "11", ROAD_GAMLA), "Markaryd 11m Gamla")
		self.assertEqual(journey_line("Orkelljunga", "16.0", ROAD_E4), "Orkelljunga 16m E4")
		self.assertLessEqual(len(journey_line("Orkelljunga", "16", ROAD_GAMLA)), LINE_WIDTH)

	def test_rain_and_temp_lines(self) -> None:
		self.assertEqual(rain_line(48), "No rain")
		self.assertEqual(rain_line(0), "Rain now")
		self.assertEqual(rain_line(3), "Rain 3h")
		self.assertEqual(rain_line(None), "Rain --")
		self.assertEqual(temp_line(6.5, False), "6.5 C")
		self.assertEqual(temp_line(7.0, True), "7 C ice")
		self.assertEqual(temp_line(99, False), "--")


if __name__ == "__main__":
	unittest.main()
