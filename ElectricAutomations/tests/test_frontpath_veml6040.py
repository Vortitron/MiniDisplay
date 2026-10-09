#!/usr/bin/env python3
"""Unit tests for FrontPath VEML6040 mapping (mirrors frontpath-rgb.yaml).

Live firmware is the overlay esphome/FrontPath/frontpath-rgb.yaml on top of
frontpath.yaml. Keep these formulas in lock-step with poll_veml6040.

Run:  python3 ElectricAutomations/tests/test_frontpath_veml6040.py
"""

from __future__ import annotations

import unittest

LUX_PER_GREEN_COUNT_80MS = 0.12584
LUX_FULL_SCALE = 200.0
GREYNESS_MIN_LUX = 2.0
TWILIGHT_DUSK = 1.75
DIM_LUX = 120.0


def lux_from_green(raw_g: int, lux_per_count: float = LUX_PER_GREEN_COUNT_80MS) -> float:
	assert raw_g >= 0
	return raw_g * lux_per_count


def light_level_percent(lux: float) -> float:
	pct = lux / LUX_FULL_SCALE * 100.0
	if pct < 0.0:
		return 0.0
	if pct > 100.0:
		return 100.0
	return pct


def twilight_index(raw_b: int, raw_r: int) -> float | None:
	"""Blue/red. High = blue hour; ~1 = overcast; low = sodium/path lamps."""
	if raw_r <= 8:
		return None
	tw = raw_b / raw_r
	return min(10.0, tw)


def greyness_percent(raw_r: int, raw_g: int, raw_b: int, lux: float) -> float | None:
	if lux < GREYNESS_MIN_LUX:
		return None
	maxc = max(raw_r, raw_g, raw_b)
	minc = min(raw_r, raw_g, raw_b)
	if maxc <= 0:
		return None
	chroma = (maxc - minc) / maxc
	return (1.0 - chroma) * 100.0


def sky_label(lux: float, tw: float, greyness: float | None) -> str:
	if lux < 1.0:
		return "Night"
	if lux < DIM_LUX and tw >= TWILIGHT_DUSK:
		return "Twilight"
	if lux < DIM_LUX:
		return "Dark overcast"
	if greyness is not None and greyness >= 75.0:
		return "Overcast"
	if tw >= 1.6:
		return "Clear blue"
	return "Sun"


class Veml6040MappingTests(unittest.TestCase):
	def test_darkness_helper_32_percent_is_dusk_lux(self) -> None:
		self.assertAlmostEqual(light_level_percent(64.0), 32.0, places=4)

	def test_overcast_day_saturates_light_level(self) -> None:
		self.assertEqual(light_level_percent(1000.0), 100.0)

	def test_cloud_is_not_twilight(self) -> None:
		# Dim + colour-neutral must not look like the blue hour.
		self.assertEqual(sky_label(lux=40.0, tw=1.15, greyness=90.0), "Dark overcast")

	def test_blue_hour_is_twilight(self) -> None:
		self.assertEqual(sky_label(lux=40.0, tw=2.1, greyness=40.0), "Twilight")

	def test_twilight_index_from_counts(self) -> None:
		self.assertAlmostEqual(twilight_index(400, 200), 2.0, places=4)
		self.assertIsNone(twilight_index(10, 4))

	def test_path_lamp_is_red(self) -> None:
		self.assertLess(twilight_index(80, 400), 0.6)

	def test_equal_rgb_is_fully_grey(self) -> None:
		grey = greyness_percent(800, 800, 800, lux=100.0)
		self.assertIsNotNone(grey)
		self.assertAlmostEqual(grey, 100.0, places=4)


if __name__ == "__main__":
	unittest.main()
