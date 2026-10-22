#!/usr/bin/env python3
"""Tests for Bio2Hvac.yaml — the bio hall heat pump.

Unlike the Sam tests, these render the REAL templates out of the YAML: the
second and third `variables:` blocks of the automation (the desired ladder and
the heat maths) use only plain Jinja, so they are loaded from Bio2Hvac.yaml
and rendered against a hand-made copy of the first block's inputs. Each
rendered result is parsed back to a native type, as Home Assistant does.

Run with:  python3 ElectricAutomations/tests/test_bio2_hvac_templates.py
       or:  python3 -m pytest ElectricAutomations/tests/test_bio2_hvac_templates.py
"""

from __future__ import annotations

import pathlib
from ast import literal_eval

import yaml
from jinja2 import Environment

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUTOMATION = yaml.safe_load((ROOT / "Bio2Hvac.yaml").read_text())
CONSTANTS = dict(AUTOMATION["variables"])
# actions[0] reads live state; actions[1] is the desired ladder, actions[2] the heat maths.
DESIRED_VARS = AUTOMATION["actions"][1]["variables"]
HEAT_VARS = AUTOMATION["actions"][2]["variables"]

_ENV = Environment()


def _ha_round(value, precision=0, method="common", default=None):
	"""Home Assistant's forgiving round: an int at precision 0 (so 22 -> '22°C')."""
	try:
		value = round(float(value), precision)
	except (ValueError, TypeError):
		return default
	return int(value) if precision == 0 else value


_ENV.filters["round"] = _ha_round
_ENV.filters["timestamp_custom"] = lambda ts, fmt="%H:%M", local=True: "20:00"
# lock_minutes_remaining uses now(); pin it so the tests are deterministic.
NOW_TS = 1_800_000_000.0
_ENV.globals["now"] = lambda: type("Now", (), {"timestamp": staticmethod(lambda: NOW_TS)})()


def _parse(text: str):
	stripped = text.strip()
	if stripped in ("True", "False"):
		return stripped == "True"
	if stripped == "":
		return ""
	try:
		return literal_eval(stripped)
	except (ValueError, SyntaxError):
		return stripped


def render(ctx: dict, var_defs: dict) -> dict:
	ctx = dict(ctx)
	for name, tmpl in var_defs.items():
		ctx[name] = _parse(_ENV.from_string(str(tmpl)).render(**ctx))
	return ctx


def inputs(**over) -> dict:
	"""The first variables block, as the live automation would have rendered it."""
	ctx = dict(CONSTANTS)
	ctx.update(
		{
			"bio2_state": "heat",
			"bio2_ok": True,
			"bio2_preset": "none",
			"bio2_min_temp": 16.0,
			"bio2_max_temp": 30.0,
			"room_state": "14.1",
			"room_ok": True,
			"room": 14.1,
			"internal_state": "14",
			"internal_ok": True,
			"internal": 14.0,
			"outdoor": 7.0,
			"projector_state": "off",
			"projector_on": False,
			"phone_zone": "away",
			"phone_comfort": False,
			# Pre-warm planning inputs (block 1): a 14 °C room, 8 °C out, the
			# seed model k 0.2 / h 2 (Teq 18 -> 20 is out of reach -> 99 h ->
			# lead capped at prewarm_max_lead_h), 13:00 with the film at 20:00.
			"prewarm_enabled": True,
			"film_ts": 1_800_000_000.0 + 7 * 3600,
			"hours_until_film": 7.0,
			"bio_k": 0.2,
			"bio_h": 2.0,
			"t_out_fc": 8.0,
			"t_eq": 18.0,
			"hours_needed": 99,
			"bank_horizon_h": 2.03,
			"price_now": 2.0,
			"window_avg": 3.0,
			"holiday_mode": False,
			"super_expensive": False,
			"current_desired": 16.0,
			"auto_set": 16.0,
			"lock_until_ts": 0.0,
			"lock_active_now": False,
			"manual_override": False,
		}
	)
	ctx.update(over)
	return ctx


def evaluate(**over) -> dict:
	return render(render(inputs(**over), DESIRED_VARS), HEAT_VARS)


# --- desired ladder --------------------------------------------------------

def test_idle_bio_is_economy_even_in_the_evening():
	r = evaluate()
	assert r["desired"] == 16 and r["reason"].strip() == "Bio idle 16°C"


def test_film_on_wants_20():
	for state in ("playing", "paused"):
		r = evaluate(projector_state=state, projector_on=True)
		assert r["desired"] == 20, state
		assert r["reason"].strip() == "Film on 20°C"


def test_phone_in_bio_by_day_wants_20():
	r = evaluate(phone_zone="bio", phone_comfort=True)
	assert r["desired"] == 20 and r["reason"].strip() == "Phone in bio 20°C"
	# The film reason wins the label when both hold.
	r = evaluate(phone_zone="bio", phone_comfort=True, projector_on=True)
	assert r["reason"].strip() == "Film on 20°C"


# --- pre-warm for film time ------------------------------------------------

def test_prewarm_window_heats_in_the_run_up_whatever_the_price():
	# Target out of reach for the seed model: lead capped at 4 h, so from
	# 16:00 the room is heated towards 20 even at a dear price.
	r = evaluate(hours_until_film=3.5, price_now=3.3, window_avg=3.0)
	assert r["prewarm_window"] is True and r["desired"] == 20
	assert r["reason"].strip() == "Pre-warm for 20:00"
	# With a learned, reachable model the lead is the model's answer.
	r = evaluate(hours_until_film=3.5, hours_needed=2.1, t_eq=24.0)
	assert r["prewarm_lead_h"] == 2.1 and r["prewarm_window"] is False
	r = evaluate(hours_until_film=2.0, hours_needed=2.1, t_eq=24.0)
	assert r["prewarm_window"] is True and r["desired"] == 20


def test_bank_heat_only_when_cheap_and_within_the_horizon():
	# A tight room: k 0.1 -> horizon ln(18/12)/0.1 = 4.05 h, so heat banked
	# at 26 °C is still 20 °C four hours later. Film at 20:00, now 16:00
	# (4 h), plain lead 1.5 h: banking now (8 + 12 * e^0.4 = 25.9 -> 26)
	# replaces the whole dear run-up, and the price is well below its average.
	r = evaluate(hours_until_film=4.0, hours_needed=1.5, t_eq=28.0, bio_k=0.1,
		bank_horizon_h=4.05, price_now=1.0, window_avg=3.0, room=18.0)
	assert r["bank_possible"] is True and r["bank_cheap"] is True
	assert r["bank_target"] == 26
	assert r["bank_now"] is True and r["desired"] == 26
	assert r["reason"].strip() == "Bank heat 26°C (cheap)"
	# Closer to film time less is needed: 2 h out -> 8 + 12 * e^0.2 = 22.7 -> 23.
	r = evaluate(hours_until_film=2.0, hours_needed=1.5, t_eq=28.0, bio_k=0.1,
		bank_horizon_h=4.05, price_now=1.0, window_avg=3.0, room=18.0)
	assert r["bank_target"] == 23 and r["desired"] == 23
	# Same but the price now is only 10 % cheaper: under the 15 % margin.
	r = evaluate(hours_until_film=2.0, hours_needed=1.5, t_eq=28.0, bio_k=0.1,
		bank_horizon_h=4.05, price_now=2.7, window_avg=3.0, room=18.0)
	assert r["bank_cheap"] is False and r["desired"] == 16
	# Too early: the heat would have leaked away by 20:00.
	r = evaluate(hours_until_film=6.0, hours_needed=2.0, t_eq=28.0, bio_k=0.1,
		bank_horizon_h=4.05, price_now=0.5, window_avg=3.0, room=18.0)
	assert r["bank_possible"] is False and r["desired"] == 16
	# Already banked: hold the target (Bio2 idles at it) rather than drop
	# to 16 and re-raise, which churned the desired helper on 22 Oct.
	r = evaluate(hours_until_film=4.0, hours_needed=1.5, t_eq=28.0, bio_k=0.1,
		bank_horizon_h=4.05, price_now=1.0, window_avg=3.0, room=26.0)
	assert r["bank_now"] is True and r["desired"] == 26
	# Room sensor down: no banking.
	r = evaluate(hours_until_film=4.0, hours_needed=1.5, t_eq=28.0, bio_k=0.1,
		bank_horizon_h=4.05, price_now=1.0, window_avg=3.0, room_ok=False, room=0.0)
	assert r["bank_now"] is False
	# The seed model (k 0.2, 8 °C out): horizon ln(18/12)/0.2 = 2.03 h, so
	# banking only reaches two hours back until the model learns the room.
	r = evaluate(hours_until_film=1.0, hours_needed=0.5, bank_horizon_h=2.03, price_now=0.3, window_avg=3.0, room=19.0)
	assert r["bank_possible"] is True and r["bank_now"] is True and r["desired"] == 23  # 8 + 12 * e^0.2 = 22.7
	r = evaluate(hours_until_film=2.5, hours_needed=0.5, bank_horizon_h=2.03, price_now=0.3, window_avg=3.0, room=19.0)
	assert r["bank_possible"] is False


def test_prewarm_switch_and_holiday():
	r = evaluate(hours_until_film=1.0, prewarm_enabled=False)
	assert r["prewarm_window"] is False and r["desired"] == 16
	r = evaluate(hours_until_film=1.0, holiday_mode=True)
	assert r["prewarm_window"] is False and r["desired"] == 10


def test_after_film_time_nothing_is_planned():
	r = evaluate(hours_until_film=-1.0, price_now=0.1)
	assert r["prewarm_window"] is False and r["bank_possible"] is False
	assert r["desired"] == 16


def test_holiday_wins_over_everything():
	r = evaluate(holiday_mode=True, projector_on=True, manual_override=True, current_desired=23.0)
	assert r["desired"] == 10 and "Holiday" in r["reason"]


def test_manual_change_is_kept_and_locked():
	# You set 22 while the automation last wrote 16: a manual change.
	r = evaluate(current_desired=22.0, auto_set=16.0, manual_override=True)
	assert r["desired"] == 22.0
	assert r["reason"].strip() == "You set 22°C (90m)"
	# Later, lock still running, projector off: still 22, with the time left.
	r = evaluate(current_desired=22.0, auto_set=22.0, lock_active_now=True, lock_until_ts=NOW_TS + 45 * 60)
	assert r["desired"] == 22.0
	assert r["reason"].strip() == "You set 22°C (45m)"
	assert r["lock_minutes_remaining"] == 45


# --- heat maths (same fooling as sam.yaml) ---------------------------------

def _check_setpoint(r: dict) -> None:
	sp = float(r["heat_setpoint"])
	assert 16 <= sp <= 30, sp
	assert sp * 2 == int(sp * 2), f"{sp} not on the 0.5 step"
	assert isinstance(r["heat_fan_only"], bool)
	assert isinstance(r["shed_now"], bool)


def test_live_cold_room_today_heats_hard():
	# 20 Oct 2026 10:00: room 14.1, unit reads 14, nobody there -> 16 wanted.
	r = evaluate()
	_check_setpoint(r)
	assert r["heat_mode"] == "heat"
	assert float(r["heat_setpoint"]) == 16.0  # internal 14 + need 1.9 = 15.9 -> 16
	assert r["heat_action_label"].strip() == "Heating"


def test_film_start_from_cold_asks_for_internal_plus_need():
	r = evaluate(projector_on=True, projector_state="playing", room=14.1, internal=14.0)
	_check_setpoint(r)
	assert r["heat_mode"] == "heat"
	assert float(r["heat_setpoint"]) == 20.0  # 14 + 5.9 -> 20
	assert r["heat_action_label"].strip() == "Heating"


def test_unit_overreads_still_heats_at_max():
	# Ceiling sensor says 26 while the room is 16 and a film is on: ask for 30.
	r = evaluate(projector_on=True, room=16.0, internal=26.0)
	assert r["heat_mode"] == "heat" and float(r["heat_setpoint"]) == 30.0


def test_at_target_holds_by_nudging_below_internal():
	r = evaluate(projector_on=True, room=20.2, internal=22.0)
	_check_setpoint(r)
	assert r["heat_mode"] == "heat"
	assert float(r["heat_setpoint"]) == 20.0  # 22 + max(-2 - 0.2, -5) = 19.8 -> 20
	assert r["heat_action_label"].strip() == "Holding"


def test_film_ends_room_well_above_economy_goes_fan_only():
	# Film over at 23:00, room 20.5 against 16: more than 3 above -> fan only.
	r = evaluate(room=20.5, internal=21.0)
	assert r["heat_mode"] == "fan_only"
	assert r["heat_action_label"].strip() == "Fan only"
	assert float(r["heat_setpoint"]) == 16.0  # 21 + max(-6.5, -5) = 16


def test_room_sensor_down_runs_on_its_own_sensor():
	r = evaluate(room_ok=False, room_state="unavailable", room=0.0, projector_on=True, internal=18.0)
	assert r["heat_mode"] == "heat"
	assert float(r["heat_setpoint"]) == 22.0  # target 20 + 2 fallback offset
	assert r["heat_action_label"].strip() == "Bio2 sensor only"
	assert r["shed_now"] is False  # never shed blind


def test_mild_outside_coasts():
	r = evaluate(room=14.0, outdoor=18.0, internal=15.0)  # want 16, warmer out
	assert r["heat_mode"] == "fan_only"
	assert r["heat_action_label"].strip() == "Coasting (mild)"


def test_super_expensive_sheds_only_when_idling_above_target():
	assert evaluate(super_expensive=True, room=17.0)["shed_now"] is True
	assert evaluate(super_expensive=True, room=15.0)["shed_now"] is False
	assert evaluate(super_expensive=True, projector_on=True, room=19.0)["shed_now"] is False


def test_half_degree_rounding():
	r = evaluate(projector_on=True, room=18.3, internal=19.0)  # 19 + 1.7 = 20.7 -> 20.5
	assert float(r["heat_setpoint"]) == 20.5


if __name__ == "__main__":
	tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
	for t in tests:
		t()
	print(f"OK: {len(tests)} Bio2 HVAC tests passed (templates read from Bio2Hvac.yaml).")
