#!/usr/bin/env python3
"""Unit tests for Spot30dAverage.yaml ring-buffer parsing.

Home Assistant promotes a comma-separated template *result* to a TupleWrapper
when it is assigned to its own automation variable. The YAML must parse
`states('input_text.spot_daily_avg_history')` inside the `buf` template.

Run:  python3 ElectricAutomations/tests/test_spot_30d_average.py
"""

from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "Spot30dAverage.yaml"
SEED = "0.829,0.773,1.292,1.513,1.418,1.427,1.483,1.543,1.246,0.87,0.977,1.538,1.221,1.462,1.311,1.297,1.513,1.134,1.018,0.756,0.168,1.363,1.434,1.43,1.517,1.358,0.171,1.316,1.615,1.713"


def parse_buf(raw) -> list[float]:
	"""Mirror the buf template: accept a string or an already-split iterable."""
	if isinstance(raw, str):
		parts = raw.split(",")
	elif isinstance(raw, (list, tuple)):
		parts = raw
	else:
		parts = [raw]
	items: list[float] = []
	for p in parts:
		q = str(p).strip()
		if q not in ("", "unknown", "unavailable", "none"):
			items.append(float(q))
	return items


def test_yaml_does_not_split_a_separate_buf_raw_variable():
	text = YAML_PATH.read_text()
	assert "buf_raw.split" not in text
	assert "states('input_text.spot_daily_avg_history')" in text
	cfg = yaml.safe_load(text)
	assert cfg["id"] == "spot_30d_average"
	variables = cfg["actions"][0]["variables"]
	assert "buf_raw" not in variables
	assert "buf | list" in variables["new_buf"]
	assert "new_buf | list" in variables["new_avg"]
	assert "states('input_text.spot_daily_avg_history')" in variables["buf"]


def test_parse_comma_string_matches_live_history():
	items = parse_buf(SEED)
	assert len(items) == 30
	assert items[0] == 0.829
	assert items[-1] == 1.713
	mean = round(sum(items) / len(items), 4)
	assert mean == 1.2235


def test_parse_tuple_wrapper_style_iterable():
	# What HA hands over if the comma-string is assigned as its own variable.
	items = parse_buf(tuple(SEED.split(",")))
	assert len(items) == 30
	assert items[1] == 0.773


def test_parse_skips_empty_and_unknown():
	assert parse_buf("1.0,,unknown,unavailable,none,2.0") == [1.0, 2.0]
	assert parse_buf("") == []


def test_append_today_trims_to_30():
	buf = parse_buf(SEED)
	avg_today = 2.114
	new_buf = (buf + [round(avg_today, 4)])[-30:]
	assert len(new_buf) == 30
	assert new_buf[-1] == 2.114
	assert new_buf[0] == buf[1]


if __name__ == "__main__":
	test_yaml_does_not_split_a_separate_buf_raw_variable()
	test_parse_comma_string_matches_live_history()
	test_parse_tuple_wrapper_style_iterable()
	test_parse_skips_empty_and_unknown()
	test_append_today_trims_to_30()
	print("OK: Spot 30-day Average buffer parsing tests passed.")
