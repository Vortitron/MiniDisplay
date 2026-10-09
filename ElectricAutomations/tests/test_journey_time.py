#!/usr/bin/env python3
"""Journey lines pick Gamla E4 or E4 from Google's distance.

Google Travel Time does not name the road. Markaryd splits at 15 km
(old road 12.2, E4 17.5). The Örkelljunga pool splits at 19.6 km
(old road 19.0, E4 20.3). These render the state templates from
JourneyTime.yaml rather than a copy of them.

Run with:  python3 ElectricAutomations/tests/test_journey_time.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from jinja2 import Environment

_YAML = Path(__file__).resolve().parents[1] / "JourneyTime.yaml"
_MARKARYD = "sensor.front_walkway_google_travel_time_to_markaryd"
_POOL = "sensor.google_travel_time_to_orkelljunga"


def _float(value, default=0.0):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _int(value, default=0):
	try:
		return int(float(value))
	except (TypeError, ValueError):
		return default


def _round(value, precision=0):
	return round(float(value), precision)


def _state_template(unique_id: str) -> str:
	"""The folded state block for one sensor, so the test cannot drift from the YAML."""
	lines = _YAML.read_text().splitlines()
	unique_at = next(i for i, line in enumerate(lines) if line.strip() == f"unique_id: {unique_id}")
	start = next(i for i, line in enumerate(lines[unique_at:], unique_at) if line.strip() == "state: >-")
	key_indent = len(lines[start]) - len(lines[start].lstrip(" "))
	body = []
	for line in lines[start + 1 :]:
		if line.strip() == "":
			body.append("")
			continue
		indent = len(line) - len(line.lstrip(" "))
		if indent <= key_indent:
			break
		body.append(line[indent:])
	while body and body[-1] == "":
		body.pop()
	return "\n".join(body)


_ENV = Environment()
_ENV.filters["float"] = _float
_ENV.filters["int"] = _int
_ENV.filters["round"] = _round


def render(unique_id, source, distance, traffic, state="10.5"):
	template = _ENV.from_string(_state_template(unique_id))
	return template.render(
		state_attr=lambda entity, attr: {
			(source, "distance"): distance,
			(source, "duration_in_traffic"): traffic,
		}.get((entity, attr)),
		states=lambda entity: state if entity == source else "unknown",
	).strip()


def main() -> None:
	text = _YAML.read_text()
	assert "km >= 15" in text
	assert "km >= 19.6" in text
	# Availability must render true/false. `and distance` returns the
	# distance string, and Home Assistant then marks the sensor unavailable.
	assert "state_attr(src, 'distance') not in [none, '', 'unknown', 'unavailable']" in text
	cases = [
		("journey_markaryd", _MARKARYD, "12,3 km", "11 min", "10.55", "Markaryd 11min Gamla E4"),
		("journey_markaryd", _MARKARYD, "12.2 km", "10 min", "10.2", "Markaryd 10min Gamla E4"),
		("journey_markaryd", _MARKARYD, "14.9 km", "13 min", "13", "Markaryd 13min Gamla E4"),
		("journey_markaryd", _MARKARYD, "15 km", "16 min", "15.5", "Markaryd 16min E4"),
		("journey_markaryd", _MARKARYD, "17,5 km", "18 min", "18", "Markaryd 18min E4"),
		("journey_markaryd", _MARKARYD, "12,3 km", None, "10.6", "Markaryd 11min Gamla E4"),
		("journey_orkelljunga", _POOL, "19,2 km", "16 min", "16.1", "Örkelljunga 16min Gamla E4"),
		("journey_orkelljunga", _POOL, "19.5 km", "17 min", "17", "Örkelljunga 17min Gamla E4"),
		("journey_orkelljunga", _POOL, "19.6 km", "18 min", "18", "Örkelljunga 18min E4"),
		("journey_orkelljunga", _POOL, "20,3 km", "18 min", "18", "Örkelljunga 18min E4"),
	]
	failed = False
	for unique_id, source, distance, traffic, state, expected in cases:
		got = render(unique_id, source, distance, traffic, state)
		if got != expected:
			failed = True
			print(f"FAIL {unique_id} {distance!r} {traffic!r}: {got!r} != {expected!r}")
		else:
			print(f"ok   {expected}")
	if failed:
		sys.exit(1)
	print("all journey line cases passed")


if __name__ == "__main__":
	main()
