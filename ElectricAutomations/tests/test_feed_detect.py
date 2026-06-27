#!/usr/bin/env python3
"""Unit tests for FeedDetect.yaml — deciding which physical feed is live.

Mirrors the `determination` template:
  HEM = monthly/fixed feed meter, BIO = spot/15-min feed meter (both kW).
  Whichever carries the house load is the live feed; on_fixed_price_feed
  tracks "house is on the fixed (Hem) feed".

Run: python3 ElectricAutomations/tests/test_feed_detect.py
 or: python3 -m pytest ElectricAutomations/tests/test_feed_detect.py
"""

from __future__ import annotations

DEADBAND = 0.2   # kW — dual-meter winner must lead by this much
LOAD_KW = 0.4    # kW — single available meter clearly carrying load
IDLE_KW = 0.2    # kW — single available meter clearly idle

_UNAVAIL = ("unavailable", "unknown", "none", "")


def detect(hem_raw, bio_raw, on_fixed_now,
           deadband=DEADBAND, load_kw=LOAD_KW, idle_kw=IDLE_KW):
	hem_av = str(hem_raw) not in _UNAVAIL
	bio_av = str(bio_raw) not in _UNAVAIL
	hem_w = abs(float(hem_raw)) if hem_av else 0.0
	bio_w = abs(float(bio_raw)) if bio_av else 0.0
	if hem_av and bio_av:
		if hem_w > bio_w + deadband:
			d = "fixed"
		elif bio_w > hem_w + deadband:
			d = "spot"
		else:
			d = "hold"
	elif bio_av:
		d = "spot" if bio_w >= load_kw else ("fixed" if bio_w < idle_kw else "hold")
	elif hem_av:
		d = "fixed" if hem_w >= load_kw else ("spot" if hem_w < idle_kw else "hold")
	else:
		d = "hold"
	change_to_fixed = d == "fixed" and not on_fixed_now
	change_to_spot = d == "spot" and on_fixed_now
	return d, change_to_fixed, change_to_spot


# --- both meters available --------------------------------------------------

def test_on_spot_bio_high_hem_idle():
	d, cf, cs = detect("1.5", "1.5", on_fixed_now=False)  # hem,bio order below
	# explicit: hem idle, bio load
	d, cf, cs = detect(hem_raw="0.1", bio_raw="1.5", on_fixed_now=True)
	assert d == "spot" and cs and not cf


def test_on_fixed_hem_high_bio_idle():
	d, cf, cs = detect(hem_raw="1.5", bio_raw="0.1", on_fixed_now=False)
	assert d == "fixed" and cf and not cs


def test_deadband_holds_when_close():
	# 0.25 vs 0.1 -> diff 0.15 < 0.2 deadband -> hold
	d, cf, cs = detect(hem_raw="0.25", bio_raw="0.1", on_fixed_now=False)
	assert d == "hold" and not cf and not cs


def test_both_idle_overnight_holds():
	d, cf, cs = detect(hem_raw="0.1", bio_raw="0.11", on_fixed_now=True)
	assert d == "hold"  # genuinely idle on spot -> stays as-is (latched)


def test_solar_export_counts_as_active():
	# Hem exporting (-2 kW) is still the live feed by magnitude.
	d, cf, cs = detect(hem_raw="-2.0", bio_raw="0.1", on_fixed_now=False)
	assert d == "fixed" and cf


# --- one meter unavailable (P1 readers drop out) ----------------------------

def test_current_scenario_hem_unavailable_bio_idle_is_fixed():
	# Exactly the live situation: Hem unavailable, Bio dropped to 0.113 idle.
	d, cf, cs = detect(hem_raw="unavailable", bio_raw="0.113", on_fixed_now=False)
	assert d == "fixed" and cf


def test_hem_unavailable_bio_load_is_spot():
	d, cf, cs = detect(hem_raw="unavailable", bio_raw="0.85", on_fixed_now=True)
	assert d == "spot" and cs


def test_hem_unavailable_bio_midrange_holds():
	# 0.3 kW is between idle(0.2) and load(0.4) -> ambiguous -> hold
	d, cf, cs = detect(hem_raw="unknown", bio_raw="0.3", on_fixed_now=True)
	assert d == "hold"


def test_bio_unavailable_hem_load_is_fixed():
	d, cf, cs = detect(hem_raw="1.0", bio_raw="unavailable", on_fixed_now=False)
	assert d == "fixed" and cf


def test_bio_unavailable_hem_idle_is_spot():
	d, cf, cs = detect(hem_raw="0.1", bio_raw="unavailable", on_fixed_now=True)
	assert d == "spot" and cs


def test_both_unavailable_holds():
	d, cf, cs = detect(hem_raw="unavailable", bio_raw="unavailable", on_fixed_now=True)
	assert d == "hold" and not cf and not cs


# --- no redundant writes ----------------------------------------------------

def test_no_change_when_already_correct():
	# Decided fixed but flag already on -> no change action.
	d, cf, cs = detect(hem_raw="1.5", bio_raw="0.1", on_fixed_now=True)
	assert d == "fixed" and not cf and not cs
	# Decided spot but flag already off -> no change action.
	d, cf, cs = detect(hem_raw="0.1", bio_raw="1.5", on_fixed_now=False)
	assert d == "spot" and not cf and not cs


def _run_all():
	fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
	for fn in fns:
		fn()
	print(f"OK - {len(fns)} feed-detect tests passed")


if __name__ == "__main__":
	_run_all()
