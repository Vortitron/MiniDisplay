#!/usr/bin/env python3
"""Unit tests for the Fixed-Price Swap feature.

Covers:
  1. next-24h average maths (flat + usage-weighted) — mirrors the
     FixedPriceSwapAdvisor.yaml `slots_calc` loop.
  2. the swap decision (to-fixed / back-to-spot) with margin + once/day throttle.
  3. the on_fixed_price gating guards added to the spot-driven automations,
     rendered from the exact template fragments in the YAML.

Run:  python3 -m pytest ElectricAutomations/tests/test_fixed_price_swap.py
  or: python3 ElectricAutomations/tests/test_fixed_price_swap.py
"""

from __future__ import annotations

from ast import literal_eval

from jinja2 import Environment

_ENV = Environment()

# Typical evening-peaked profile (must match FixedPriceSwapAdvisor.yaml).
USAGE_PROFILE = [0.6, 0.55, 0.5, 0.5, 0.55, 0.7, 0.9, 1.2, 1.3, 1.2, 1.0, 0.95,
                 0.95, 0.9, 0.9, 0.95, 1.1, 1.4, 1.5, 1.45, 1.3, 1.1, 0.85, 0.7]
SEED_BENCHMARK = 1.2235


# --- 1) next-24h averages --------------------------------------------------

def next24h(slots, now_ts, profile=USAGE_PROFILE):
	"""slots: list of {'value','start_hour','end'} with int 'end' vs int now_ts."""
	n = psum = wsum = wprice = 0.0
	cnt = 0
	for s in slots:
		if "value" in s and s.get("end") is not None and s.get("start_hour") is not None:
			if s["end"] > now_ts and cnt < 96:
				v = float(s["value"])
				w = float(profile[s["start_hour"]])
				cnt += 1
				psum += v
				wsum += w
				wprice += v * w
	flat = psum / cnt if cnt else 0.0
	weighted = wprice / wsum if wsum else 0.0
	return cnt, round(flat, 4), round(weighted, 4)


def _slots(values_by_hour, now_ts=0, start=0):
	"""Build 96 quarter-slots (24h) — value per hour repeated x4; end after now."""
	out = []
	for q in range(96):
		hour = (start + q // 4) % 24
		out.append({"value": values_by_hour[hour], "start_hour": hour, "end": q + 1})
	return out


def test_flat_average_constant_prices():
	slots = _slots([2.0] * 24)
	n, flat, weighted = next24h(slots, now_ts=0)
	assert n == 96
	assert flat == 2.0
	assert weighted == 2.0  # constant prices => weighting irrelevant


def test_past_slots_are_skipped():
	slots = _slots([1.0] * 24)
	# now at slot 48 => only the later 48 slots counted (still all value 1.0)
	n, flat, weighted = next24h(slots, now_ts=48)
	assert n == 48
	assert flat == 1.0


def test_weighting_lifts_when_expensive_in_evening():
	# Cheap overnight (low usage weight), dear in the evening peak (high weight).
	vals = [0.5] * 24
	for h in (17, 18, 19, 20):  # evening peak hours
		vals[h] = 3.0
	n, flat, weighted = next24h(_slots(vals), now_ts=0)
	# Weighted should exceed the flat mean because dear hours carry more weight.
	assert weighted > flat


def test_weighting_lowers_when_expensive_overnight():
	vals = [0.5] * 24
	for h in (1, 2, 3, 4):  # cheap-usage overnight hours made dear
		vals[h] = 3.0
	n, flat, weighted = next24h(_slots(vals), now_ts=0)
	assert weighted < flat


# --- 2) swap decision ------------------------------------------------------

def decide(flat, weighted, benchmark, margin_pct, on_fixed, suggested_today, slot_count=96):
	margin = margin_pct / 100.0
	hi = benchmark * (1 + margin)
	lo = benchmark * (1 - margin)
	worst = max(flat, weighted)
	best = min(flat, weighted)
	# Require a FULL 24h of upcoming prices (96 quarter-hour slots) before deciding,
	# i.e. tomorrow's prices have published (~13:00); otherwise wait.
	have_data = slot_count >= 96 and benchmark > 0
	to_fixed = have_data and not on_fixed and worst > hi
	to_spot = have_data and on_fixed and best < lo
	fire = (to_fixed or to_spot) and not suggested_today
	return to_fixed, to_spot, fire


def test_suggest_fixed_when_next24h_above_benchmark():
	to_fixed, to_spot, fire = decide(1.5, 1.6, SEED_BENCHMARK, 10, on_fixed=False, suggested_today=False)
	assert to_fixed and fire and not to_spot


def test_no_suggest_when_within_margin():
	to_fixed, to_spot, fire = decide(1.30, 1.32, SEED_BENCHMARK, 10, on_fixed=False, suggested_today=False)
	# hi = 1.2235*1.1 = 1.346 -> 1.32 below threshold
	assert not to_fixed and not fire


def test_suggest_back_to_spot_when_cheap_again():
	to_fixed, to_spot, fire = decide(1.0, 0.95, SEED_BENCHMARK, 10, on_fixed=True, suggested_today=False)
	# lo = 1.2235*0.9 = 1.101 -> best 0.95 below
	assert to_spot and fire and not to_fixed


def test_no_back_to_spot_when_still_dear():
	to_fixed, to_spot, fire = decide(1.2, 1.25, SEED_BENCHMARK, 10, on_fixed=True, suggested_today=False)
	assert not to_spot and not fire


def test_throttle_blocks_second_suggestion_same_day():
	to_fixed, to_spot, fire = decide(1.5, 1.6, SEED_BENCHMARK, 10, on_fixed=False, suggested_today=True)
	assert to_fixed and not fire  # decision stands, but notification suppressed


def test_insufficient_data_never_suggests():
	to_fixed, to_spot, fire = decide(2.0, 2.0, SEED_BENCHMARK, 10, on_fixed=False, suggested_today=False, slot_count=20)
	assert not to_fixed and not fire


def test_partial_day_before_1pm_waits_for_full_24h():
	# Pre-13:00 there is only today's remainder (~50 slots, no tomorrow yet).
	# Even with clearly dear prices we must hold off until a full 24h is loaded.
	to_fixed, to_spot, fire = decide(2.0, 2.0, SEED_BENCHMARK, 10, on_fixed=False, suggested_today=False, slot_count=50)
	assert not to_fixed and not fire
	# Once the full next day publishes (>=96), the same dear prices do suggest.
	to_fixed2, _, fire2 = decide(2.0, 2.0, SEED_BENCHMARK, 10, on_fixed=False, suggested_today=False, slot_count=146)
	assert to_fixed2 and fire2


# --- 3) on_fixed_price gating guards (rendered from the YAML fragments) -----

def _render(template, **ctx):
	out = _ENV.from_string(template).render(**ctx).strip()
	if out in ("True", "False"):
		return out == "True"
	try:
		return literal_eval(out)
	except (ValueError, SyntaxError):
		return out


def _is_state_factory(fixed_on):
	def is_state(entity, state):
		if entity == "input_boolean.on_fixed_price_feed":
			return state == ("on" if fixed_on else "off")
		return False
	return is_state


# Fragments copied from the automations:
DCH_CHEAP = "{{ price_rank < price_rank_4h and not on_fixed_price }}"
SAM_CHEAP = "{{ price_rank < price_rank_4h and not on_fixed_price }}"
SUPEREXP = ("{{ price_ok and not on_fixed_price "
            "and (price >= on_level or (currently_active and price >= off_level)) }}")
CHEAPLECCY = "{{ current <= (avg_price / 2) and is_state('input_boolean.on_fixed_price_feed', 'off') }}"
DAYWINDOW = "{{ rank < 4 and is_state('input_boolean.on_fixed_price_feed', 'off') }}"


def test_dch_and_sam_cheap_false_on_fixed():
	# Genuinely cheap (rank 1 < 12) but on the fixed feed -> not cheap.
	assert _render(DCH_CHEAP, price_rank=1, price_rank_4h=12, on_fixed_price=True) is False
	assert _render(SAM_CHEAP, price_rank=1, price_rank_4h=12, on_fixed_price=True) is False
	# On spot it still works.
	assert _render(DCH_CHEAP, price_rank=1, price_rank_4h=12, on_fixed_price=False) is True


def test_superexpensive_inactive_on_fixed():
	# Price way above threshold, but on fixed feed -> never active.
	assert _render(SUPEREXP, price_ok=True, on_fixed_price=True, price=5.0,
	               on_level=2.0, off_level=1.85, currently_active=False) is False
	# On spot the same inputs DO activate.
	assert _render(SUPEREXP, price_ok=True, on_fixed_price=False, price=5.0,
	               on_level=2.0, off_level=1.85, currently_active=False) is True


def test_indicators_forced_off_on_fixed():
	# CheapLeccy: current well below avg/2 -> "cheap", but fixed feed forces off.
	assert _render(CHEAPLECCY, current=0.2, avg_price=2.0, is_state=_is_state_factory(True)) is False
	assert _render(CHEAPLECCY, current=0.2, avg_price=2.0, is_state=_is_state_factory(False)) is True
	# DaytimeCheapWindow: rank 1 < 4 -> on, but fixed feed forces off.
	assert _render(DAYWINDOW, rank=1, is_state=_is_state_factory(True)) is False
	assert _render(DAYWINDOW, rank=1, is_state=_is_state_factory(False)) is True


def _run_all():
	fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
	for fn in fns:
		fn()
	print(f"OK - {len(fns)} fixed-price-swap tests passed")


if __name__ == "__main__":
	_run_all()
