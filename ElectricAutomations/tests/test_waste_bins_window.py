#!/usr/bin/env python3
"""Unit tests for the BEDA indoor-bin reminder window.

KitchenDetectorer and LoftC3 parse the waste_collection_schedule sensor
state and show a reminder from 18:00 the evening before collection until
the end of collection day. This file pins that rule and the date parsers
so a later ESP lambda tweak cannot silently change "when it appears".

Run:  python3 ElectricAutomations/tests/test_waste_bins_window.py
"""

from __future__ import annotations

import datetime as dt
import re


EVENING_HOUR = 18


def days_until_from_state(raw: str, today: dt.date) -> int:
	"""Mirror the ESPHome lambda. Returns -999 when unparseable."""
	if raw in ("", "unknown", "unavailable", "none"):
		return -999
	stripped = raw.strip()
	if stripped.lstrip("-").isdigit():
		return int(stripped)
	match = re.search(r",\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", raw)
	if match:
		day, month, year = (int(match.group(i)) for i in (1, 2, 3))
	else:
		match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
		if match:
			year, month, day = (int(match.group(i)) for i in (1, 2, 3))
		else:
			match = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw)
			if not match:
				return -999
			day, month, year = (int(match.group(i)) for i in (1, 2, 3))
	if year < 2020 or not (1 <= month <= 12) or not (1 <= day <= 31):
		return -999
	target = dt.date(year, month, day)
	return (target - today).days


def due_soon(days: int, hour: int, evening_hour: int = EVENING_HOUR) -> bool:
	if days == 0:
		return True
	if days == 1 and hour >= evening_hour:
		return True
	return False


TODAY = dt.date(2026, 9, 2)  # Wednesday; live HA at time of writing


def test_parse_wcs_on_weekday_date():
	assert days_until_from_state("on Mon, 07.09.2026", TODAY) == 5
	assert days_until_from_state("on Thu, 10.09.2026", TODAY) == 8


def test_parse_iso_and_plain_dotted():
	assert days_until_from_state("2026-09-07", TODAY) == 5
	assert days_until_from_state("07.09.2026", TODAY) == 5


def test_parse_integer_days_until():
	assert days_until_from_state("0", TODAY) == 0
	assert days_until_from_state("1", TODAY) == 1
	assert days_until_from_state(" 5 ", TODAY) == 5


def test_parse_unknown_is_sentinel():
	assert days_until_from_state("unknown", TODAY) == -999
	assert days_until_from_state("", TODAY) == -999
	assert days_until_from_state("garbage", TODAY) == -999


def test_window_today_always_shows():
	assert due_soon(0, 0)
	assert due_soon(0, 17)
	assert due_soon(0, 23)


def test_window_evening_before():
	assert not due_soon(1, 17)
	assert due_soon(1, 18)
	assert due_soon(1, 23)


def test_window_further_out_or_past_is_hidden():
	assert not due_soon(2, 18)
	assert not due_soon(5, 21)
	assert not due_soon(-1, 12)
	assert not due_soon(-999, 18)


def test_live_schedule_is_quiet_on_wednesday_morning():
	# C2 Mon 7 Sep (5 days), C1 Thu 10 Sep (8 days). Wednesday 10:00
	# must not show either reminder.
	c2 = days_until_from_state("on Mon, 07.09.2026", TODAY)
	c1 = days_until_from_state("on Thu, 10.09.2026", TODAY)
	assert not due_soon(c2, 10)
	assert not due_soon(c1, 10)


def test_c2_appears_sunday_evening():
	sunday = dt.date(2026, 9, 6)
	c2 = days_until_from_state("on Mon, 07.09.2026", sunday)
	assert c2 == 1
	assert not due_soon(c2, 17)
	assert due_soon(c2, 18)


if __name__ == "__main__":
	tests = [v for k, v in globals().items() if k.startswith("test_")]
	for fn in tests:
		fn()
	print(f"{len(tests)} tests passed")
