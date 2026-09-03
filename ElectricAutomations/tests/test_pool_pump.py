#!/usr/bin/env python3
"""Unit tests for PoolPump.yaml decision maths.

Run with:  python3 ElectricAutomations/tests/test_pool_pump.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


TICK_MINUTES = 15
MAINTENANCE_TARGET = 180
CHEAP_CUTOFF_HOUR = 16


@dataclass
class PoolContext:
	mode: str = "off"
	minutes_remaining: int = 0
	daily_on: int = 0
	maintenance_target: int = MAINTENANCE_TARGET
	cheap_cutoff_hour: int = 0
	price_rank: int = 12
	cheap_rank_max: int = 5
	cheap_leccy: bool = False
	on_fixed_price: bool = False
	super_expensive: bool = False
	hour: int = 10
	plan_until: datetime | None = None
	now: datetime | None = None


def electricity_cheap_now(ctx: PoolContext) -> bool:
	if ctx.on_fixed_price:
		return 7 <= ctx.hour < 22
	return ctx.cheap_leccy or ctx.price_rank <= ctx.cheap_rank_max


def evaluate(ctx: PoolContext) -> dict:
	now = ctx.now or datetime(2026, 6, 27, ctx.hour, 0, 0)
	mode_cheap = ctx.mode == "cheap"
	mode_maintenance = ctx.mode == "maintenance"
	mode_extended = ctx.mode == "extended"
	mode_one_hour = ctx.mode == "one_hour"
	timed_window_active = (
		(mode_extended or mode_one_hour)
		and ctx.plan_until is not None
		and now.timestamp() < ctx.plan_until.timestamp()
	)
	cheap_budget_active = (
		(mode_cheap and ctx.minutes_remaining > 0)
		or (
			mode_maintenance
			and ctx.minutes_remaining > 0
			and ctx.daily_on < ctx.maintenance_target
		)
	)
	cheap_now = electricity_cheap_now(ctx)
	should_run_cheap = cheap_budget_active and cheap_now and not ctx.super_expensive
	should_run_timed = timed_window_active and not ctx.super_expensive
	should_run = should_run_cheap or should_run_timed
	new_minutes = (
		max(ctx.minutes_remaining - TICK_MINUTES, 0)
		if should_run_cheap
		else ctx.minutes_remaining
	)
	new_daily_on = ctx.daily_on + TICK_MINUTES if should_run else ctx.daily_on
	cheap_cutoff_reached = (
		mode_cheap and ctx.cheap_cutoff_hour > 0 and ctx.hour >= ctx.cheap_cutoff_hour
	)
	cheap_budget_done = mode_cheap and ctx.minutes_remaining <= 0
	maintenance_daily_done = mode_maintenance and ctx.daily_on >= ctx.maintenance_target
	timed_session_done = (
		(mode_extended or mode_one_hour)
		and ctx.plan_until is not None
		and now.timestamp() >= ctx.plan_until.timestamp()
	)
	session_done = (
		cheap_budget_done
		or maintenance_daily_done
		or timed_session_done
		or cheap_cutoff_reached
	)
	return {
		"should_run": should_run,
		"new_minutes": new_minutes,
		"new_daily_on": new_daily_on,
		"session_done": session_done,
		"cheap_now": cheap_now,
	}


CASES = [
	("idle_off", PoolContext(), False, 0, 0, False),
	(
		"cheap_runs_on_cheap_leccy",
		PoolContext(mode="cheap", minutes_remaining=360, cheap_leccy=True),
		True,
		345,
		15,
		False,
	),
	(
		"cheap_waits_when_expensive",
		PoolContext(mode="cheap", minutes_remaining=360, price_rank=20, cheap_leccy=False),
		False,
		360,
		0,
		False,
	),
	(
		"cheap_cancelled_at_cutoff",
		PoolContext(
			mode="cheap",
			minutes_remaining=120,
			cheap_leccy=True,
			cheap_cutoff_hour=CHEAP_CUTOFF_HOUR,
			hour=16,
		),
		True,
		105,
		15,
		True,
	),
	(
		"maintenance_runs_cheap",
		PoolContext(mode="maintenance", minutes_remaining=60, cheap_leccy=True, daily_on=120),
		True,
		45,
		135,
		False,
	),
	(
		"maintenance_done_when_daily_met",
		PoolContext(mode="maintenance", minutes_remaining=30, cheap_leccy=True, daily_on=180),
		False,
		30,
		180,
		True,
	),
	(
		"one_hour_runs_expensive",
		PoolContext(
			mode="one_hour",
			price_rank=22,
			plan_until=datetime(2026, 6, 27, 13, 0, 0),
			now=datetime(2026, 6, 27, 12, 30, 0),
		),
		True,
		0,
		15,
		False,
	),
	(
		"one_hour_done",
		PoolContext(
			mode="one_hour",
			plan_until=datetime(2026, 6, 27, 12, 0, 0),
			now=datetime(2026, 6, 27, 12, 5, 0),
		),
		False,
		0,
		0,
		True,
	),
	(
		"extended_pauses_super_expensive",
		PoolContext(
			mode="extended",
			super_expensive=True,
			plan_until=datetime(2026, 6, 27, 18, 0, 0),
			now=datetime(2026, 6, 27, 14, 0, 0),
		),
		False,
		0,
		0,
		False,
	),
	(
		"fixed_price_daytime_cheap",
		PoolContext(mode="cheap", minutes_remaining=60, on_fixed_price=True, hour=10),
		True,
		45,
		15,
		False,
	),
]


def test_pool_pump_cases():
	for name, ctx, exp_run, exp_mins, exp_daily, exp_done in CASES:
		got = evaluate(ctx)
		assert got["should_run"] == exp_run, f"{name}: should_run {got['should_run']} != {exp_run}"
		assert got["new_minutes"] == exp_mins, f"{name}: new_minutes {got['new_minutes']} != {exp_mins}"
		assert got["new_daily_on"] == exp_daily, f"{name}: new_daily_on {got['new_daily_on']} != {exp_daily}"
		assert got["session_done"] == exp_done, f"{name}: session_done {got['session_done']} != {exp_done}"


def test_cheap_rank_boundary():
	ctx = PoolContext(mode="cheap", minutes_remaining=60, price_rank=5, cheap_rank_max=5)
	assert evaluate(ctx)["should_run"] is True
	ctx.price_rank = 6
	assert evaluate(ctx)["should_run"] is False


def test_scheduler_yaml_does_not_self_trigger_on_counters():
	"""Writing minutes_remaining / daily_on must not start a second tick."""
	import pathlib

	import yaml

	cfg = yaml.safe_load(
		(pathlib.Path(__file__).resolve().parents[1] / "PoolPump.yaml").read_text()
	)
	state_entities: list[str] = []
	for trigger in cfg["triggers"]:
		if trigger.get("trigger") == "state":
			state_entities.extend(trigger.get("entity_id") or [])
	assert "number.pool_pump_minutes_remaining" not in state_entities
	assert "number.pool_pump_daily_on_minutes" not in state_entities
	assert "input_number.electricity_price_rank" not in state_entities
	assert "select.pool_pump_pool_pump_plan" in state_entities
	assert cfg["actions"][0].get("delay") == {"milliseconds": 800}


if __name__ == "__main__":
	test_pool_pump_cases()
	test_cheap_rank_boundary()
	test_scheduler_yaml_does_not_self_trigger_on_counters()
	print(f"OK: {len(CASES)} pool pump scenarios + rank boundary + trigger hygiene passed.")
