#!/usr/bin/env python3
"""Pin the BILRESA button automations.

Renders each automation's own Jinja with jinja2 and plays its conditions
and actions against a small model of Home Assistant (light states with
brightness, event entities with timestamps, areas, the Sam desired
temperature helper):

  Living Room / Bio remote
  - a tap walks off → first only → all → flood only → off → first only,
    with the dim preset on every light it turns on
  - a double tap turns both off; a hold goes to 100% daylight and fades
    down to the floor, never to 0 (which would turn the lights off)
  - on every cycling button, the first tap more than a minute after that
    button's last press turns its lights off, wherever the cycle is

  Living Room / Bio hold from off: both lights on at 50% in their warm
  settings, then 100% daylight if still held; a hold when lit is the old
  100% daylight + fade

  Quiet room remote
  - bedroom light button: tap off → on in the last colour, on → next of
    10 colours; a tap after a minute turns it off; double tap off, after
    a minute every quiet-room light off (candle lamp too)
  - stand button: tap steps all off → stand + candle lamp (50%, 2000 K) →
    stand off, candle stays → off, with no minute rule; double tap stand
    and candle off, after a minute everything off
  - hold: brightness steps through the old ESPHome levels, wrapping round
    (the stand button steps the candle when only the candle is on)

  Kid's Room remote
  - Button 1 steps stand + spot 10 → 25 → 50 → 75 → 100 → off, carrying
    on from whatever brightness is lit (night mode's 10% stand → 25); at
    night the spot stays off below 50%; the night light counts as off at
    any time, so a tap brings the light up and never puts it out (double
    tap still does)
  - Button 2 at night: spot and Living Room off, stand candle 10%, Sky
    Lite on at 50%, desired temperature untouched; tapped again, Sky Lite
    off with the candle stand left on; 06:00-10:00: Living Room + stand +
    spot at 40% / 4000 K and never the Sky Lite; 10:00-18:00: those at 50%
    daylight, and a second tap within a minute adds the Sky Lite at 100%

  All remotes
  - turning lights on raises the desired temperature to 20 if lower (not
    when turning off, not in holiday mode, never lowers it)
  - both buttons of one remote HELD within 0.5 s: the per-button
    automations stop, BILRESA Going Out turns off every lit light except
    the stairs, the front walkway, the fish tank and status LEDs, and
    sets 16; tapping both is not Going Out, each button just acts on
    its own tap (taps never wait for a partner, holds wait 0.5 s)
  - while a remote's firmware update runs, nothing reacts to it
  - with dry_run on (as shipped) Going Out only posts a notification
    naming the lights and the gap between presses, and changes nothing
  - holds further apart, or a pair of releases, are not Going Out
  - a copy of an event (same button, same type, under 0.3 s later) is
    dropped, so it neither acts twice nor restarts the first run, and the
    one-minute rule still sees the real previous press; a quick hold's
    long_release 0.2 s after long_press is not a copy
  - automation-level variables are constants (or the self-contained
    `combo` test), so key-sorted round trips cannot break them

Run:  python3 ElectricAutomations/tests/test_bilresa_buttons.py
"""

from __future__ import annotations

import ast
import datetime as dt
import pathlib

import jinja2
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

LR_BTN = "event.bilresa_dual_button_button_1"
BIO_BTN = "event.bilresa_dual_button_button_2"
KID_CYCLE_BTN = "event.bedroom_kid_s_room_bilresa_button_1"
KID_NIGHT_BTN = "event.bedroom_kid_s_room_bilresa_button_2"
QR_LIGHT_BTN = "event.quiet_room_quiet_room_bilresa_button_1"
QR_STAND_BTN = "event.quiet_room_quiet_room_bilresa_button_2"
QR_LIGHT_HELPER = "input_number.quiet_room_light_colour"
QR_STAND_HELPER = "input_number.quiet_room_stand_colour"
DESIRED = "input_number.sam_desired_temperature"
HOLIDAY = "input_boolean.holiday_mode"

STAIRS = "light.isp_0db21e_b21e"
FISH = "light.antela_smart_power_strip_socket_2"
PORCH = "light.front_porch_local"
LR_SPOT = "light.kajplats_e14_ws_globe_806lm_2"
LR_FLOOD = "light.led_flood_light"
GOLD = "light.gold_light"
BIO_FLOOD = "light.bio_floodlight"
STAND = "light.living_office_stand"
KID_SPOT = "light.bedroom_kajplats_kids_bedroom_spot"
SKY = "light.sky_lite"
SKY_FADING = "switch.sky_lite_fading"
QR_LIGHT = "light.bedroom_light"
QR_STAND = "light.bedroom_light_stand"
QR_CANDLE = "light.candle_lamp_w505z2"
AREAS = {"front_walkway": [PORCH, "light.front_porch"]}

# Two-light rooms on the Living Room / Bio remote:
# file, own button, first light var, first light preset key
ROOMS = (
	("BilresaBio.yaml", BIO_BTN, "gold", "hs_color"),
	("BilresaLivingRoom.yaml", LR_BTN, "spot", "color_temp_kelvin"),
)
PER_BUTTON = (
	("BilresaBio.yaml", BIO_BTN, LR_BTN),
	("BilresaLivingRoom.yaml", LR_BTN, BIO_BTN),
	("BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, KID_NIGHT_BTN),
	("BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, KID_CYCLE_BTN),
	("BilresaQuietRoomLight.yaml", QR_LIGHT_BTN, QR_STAND_BTN),
	("BilresaQuietRoomStand.yaml", QR_STAND_BTN, QR_LIGHT_BTN),
)


class Stop(Exception):
	pass


class St:
	"""A state object as templates see it (states[e], states.light)."""

	def __init__(self, entity_id: str, state: str, attributes: dict | None = None):
		self.entity_id = entity_id
		self.state = state
		self.attributes = attributes or {}
		self.name = entity_id


class House:
	"""A tiny HA: states, a clock, and the light / helper services."""

	def __init__(self, now: dt.datetime):
		self.now = now
		self.s: dict[str, St] = {}
		self.calls: list = []
		self.prev: dict[str, St] = {}
		for e in (DESIRED,):
			self.set(e, "16.0")
		self.set(HOLIDAY, "off")
		for e in (LR_BTN, BIO_BTN, KID_CYCLE_BTN, KID_NIGHT_BTN, QR_LIGHT_BTN, QR_STAND_BTN):
			self.set(e, "unknown", {"event_type": None})
		for e in (QR_LIGHT_HELPER, QR_STAND_HELPER):
			self.set(e, "1.0")

	def set(self, e: str, state: str, attrs: dict | None = None) -> None:
		self.s[e] = St(e, state, attrs)

	def light(self, e: str, on: bool, pct: int | None = None) -> None:
		attrs = {"brightness": round(pct * 255 / 100)} if on and pct is not None else {}
		self.set(e, "on" if on else "off", attrs)

	def state(self, e: str) -> str:
		return self.s[e].state if e in self.s else "unknown"

	def pct(self, e: str) -> int | None:
		b = self.s[e].attributes.get("brightness")
		return None if b is None else round(b * 100 / 255)

	# -- template environment -------------------------------------------

	def env(self) -> jinja2.Environment:
		house = self

		class States:
			def __call__(self, e):
				return house.state(e)

			def __getitem__(self, e):
				return house.s.get(e)

			def __getattr__(self, domain):
				return [v for k, v in house.s.items() if k.startswith(domain + ".")]

		def as_datetime(value, default=None):
			try:
				return dt.datetime.fromisoformat(value)
			except (TypeError, ValueError):
				return default

		env = jinja2.Environment()
		env.globals.update(
			states=States(),
			is_state=lambda e, v: house.state(e) == v,
			state_attr=lambda e, a: house.s[e].attributes.get(a) if e in house.s else None,
			is_state_attr=lambda e, a, v: e in house.s and house.s[e].attributes.get(a) == v,
			now=lambda: house.now,
			as_datetime=as_datetime,
			area_entities=lambda a: AREAS.get(a, []),
		)
		env.tests["is_state"] = lambda e, v: house.state(e) == v
		return env

	def render(self, value, ctx: dict):
		"""Render a template value the way HA does (native types: Python
		literals only, so "a: b" stays a string)."""
		if isinstance(value, list):
			return [self.render(v, ctx) for v in value]
		if isinstance(value, dict):
			return {k: self.render(v, ctx) for k, v in value.items()}
		if not isinstance(value, str) or "{" not in value:
			return value
		out = self.env().from_string(value).render(**ctx).strip()
		try:
			return ast.literal_eval(out)
		except (ValueError, SyntaxError):
			return out

	# -- script runner --------------------------------------------------

	def _cond(self, cond, ctx) -> bool:
		if isinstance(cond, list):
			return all(self._cond(c, ctx) for c in cond)
		if isinstance(cond, dict):
			assert cond["condition"] == "template", cond
			cond = cond["value_template"]
		return self.render(cond, ctx) is True

	def run(self, seq: list, ctx: dict) -> None:
		for step in seq:
			if "variables" in step:
				for key, value in step["variables"].items():
					ctx[key] = self.render(value, ctx)
			elif "if" in step:
				branch = "then" if self._cond(step["if"], ctx) else "else"
				self.run(step.get(branch, []), ctx)
			elif "choose" in step:
				for option in step["choose"]:
					if self._cond(option["conditions"], ctx):
						self.run(option["sequence"], ctx)
						break
				else:
					self.run(step.get("default", []), ctx)
			elif "repeat" in step:
				count = int(self.render(step["repeat"]["count"], ctx))
				for i in range(1, count + 1):
					self.run(step["repeat"]["sequence"], {**ctx, "repeat": {"index": i}})
			elif "stop" in step:
				raise Stop(step["stop"])
			elif "delay" in step:
				pass
			else:
				self._service(step, ctx)

	def _service(self, step: dict, ctx: dict) -> None:
		action = step["action"]
		data = self.render(step.get("data") or {}, ctx)
		targets = self.render((step.get("target") or {}).get("entity_id", []), ctx)
		targets = targets if isinstance(targets, list) else [targets]
		for e in targets:
			self.calls.append((action, e, data))
			if action == "light.turn_on" and "brightness" in data:
				self.set(e, "on", {"brightness": int(data["brightness"])})
			elif action == "light.turn_on":
				pct = data.get("brightness_pct", self.pct(e) if e in self.s else None)
				self.light(e, True, pct)
			elif action == "light.turn_off":
				self.light(e, False)
			elif action in ("switch.turn_on", "switch.turn_off"):
				self.set(e, "on" if action == "switch.turn_on" else "off")
			elif action == "input_number.set_value":
				self.set(e, str(float(data["value"])))
			else:
				assert action in ("logbook.log", "persistent_notification.create"), action
		if not targets:
			self.calls.append((action, None, data))

	def fire(self, name: str, button: str, event_type: str, overrides: dict | None = None) -> str:
		"""Deliver an already-recorded button event to one automation.

		from_state is the button's previous event, as in HA.
		Returns 'blocked' (conditions), 'stopped' or 'ran'.
		"""
		doc = load(name)
		cur = self.s[button]
		trigger = {
			"entity_id": button,
			"from_state": {
				"state": self.prev[button].state if button in self.prev else "unknown",
				"attributes": self.prev[button].attributes if button in self.prev else {},
			},
			"to_state": {"state": cur.state, "attributes": cur.attributes, "name": button},
		}
		ctx = {"trigger": trigger}
		for key, value in {**doc["variables"], **(overrides or {})}.items():
			ctx[key] = self.render(value, ctx)
		if not all(self._cond(c, ctx) for c in doc["conditions"]):
			return "blocked"
		try:
			self.run(doc["actions"], ctx)
		except Stop:
			return "stopped"
		return "ran"

	def press(self, button: str, event_type: str, after_s: float = 0.0) -> None:
		self.now += dt.timedelta(seconds=after_s)
		self.prev[button] = self.s[button]
		self.set(button, self.now.isoformat(), {"event_type": event_type})


def load(name: str) -> dict:
	return yaml.safe_load((ROOT / name).read_text())


def house_at(hour: int) -> House:
	return House(dt.datetime(2026, 9, 25, hour, 0, 0, tzinfo=dt.timezone.utc))


def tap(h: House, name: str, button: str, event_type: str = "multi_press_1", after_s: float = 10) -> str:
	h.press(button, event_type, after_s=after_s)
	return h.fire(name, button, event_type)


# ---------------------------------------------------------------------------


def test_shape():
	for name, own, sibling in PER_BUTTON:
		doc = load(name)
		assert doc["mode"] == "restart", name
		assert doc["triggers"] == [{"trigger": "state", "entity_id": [own, sibling]}], name
		assert doc["variables"]["own"] == own, name
		# combo names both buttons of this remote, and nothing else.
		combo = doc["variables"]["combo"]
		assert own in combo and sibling in combo, name
		for key, value in doc["variables"].items():
			if key != "combo":
				assert "{{" not in str(value), f"{name}: {key} must be a constant"
		assert "from_state.state != 'unavailable'" in doc["conditions"][0]["value_template"]
		# Taps wait only 0.1 s (2026-09-27: a 0.5 s wait on every tap made
		# the buttons feel dead), just long enough for a burst of stored-up
		# presses (all within 40 ms) to collapse onto the last one; holds
		# wait 0.5 s for Going Out; releases not at all.
		waits = [a for a in doc["actions"]
		         if "if" in a and any("delay" in t for t in a.get("then", []))]
		assert len(waits) == 1, name
		assert waits[0]["if"][0]["value_template"] == "{{ press != 'long_release' }}", name
		delay = [t for t in waits[0]["then"] if "delay" in t][0]["delay"]["milliseconds"]
		assert delay == "{{ 500 if press == 'long_press' else 100 }}", (name, delay)
		assert "!= 'long_press'" in combo, f"{name}: combo must be holds only"
	going = load("BilresaGoingOut.yaml")
	assert going["mode"] == "single"
	buttons = {LR_BTN, BIO_BTN, KID_CYCLE_BTN, KID_NIGHT_BTN, QR_LIGHT_BTN, QR_STAND_BTN}
	assert set(going["triggers"][0]["entity_id"]) == buttons
	partner = going["variables"]["partner"]
	assert all(partner[partner[b]] == b for b in buttons)


def test_room_tap_cycle():
	for name, own, first_var, preset_key in ROOMS:
		doc = load(name)
		first, flood = doc["variables"][first_var], doc["variables"]["flood"]
		h = house_at(20)
		h.light(first, False)
		h.light(flood, False)
		for want in [("on", "off"), ("on", "on"), ("off", "on"), ("off", "off"), ("on", "off")]:
			h.calls.clear()
			assert tap(h, name, own) == "ran"
			assert (h.state(first), h.state(flood)) == want, (name, want)
			for action, entity, data in h.calls:
				if action != "light.turn_on":
					continue
				assert data["brightness_pct"] == doc["variables"]["dim_pct"], (name, entity)
				key = preset_key if entity == first else "color_temp_kelvin"
				assert key in data, (name, entity, data)


def test_room_double_tap_and_release():
	for name, own, first_var, _ in ROOMS:
		doc = load(name)
		first, flood = doc["variables"][first_var], doc["variables"]["flood"]
		h = house_at(20)
		h.light(first, True, 20)
		h.light(flood, True, 20)
		tap(h, name, own, "multi_press_2")
		assert (h.state(first), h.state(flood)) == ("off", "off"), name
		h.calls.clear()
		tap(h, name, own, "long_release")
		assert [c for c in h.calls if c[0].startswith("light.")] == [], name


def test_hold_fade():
	for name, own, first_var in (
		("BilresaBio.yaml", BIO_BTN, "gold"),
		("BilresaLivingRoom.yaml", LR_BTN, "spot"),
		("BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, "stand"),
	):
		doc = load(name)
		v = doc["variables"]
		other = v["flood"] if "flood" in v else v["spot"]
		h = house_at(20)
		# Only one lit: the hold leaves the other alone.
		h.light(v[first_var], False)
		h.light(other, True, 20)
		tap(h, name, own, "long_press")
		lights = [c for c in h.calls if c[0] == "light.turn_on"]
		assert {e for _, e, _ in lights} == {other}, name
		assert lights[0][2]["brightness_pct"] == 100
		assert lights[0][2]["color_temp_kelvin"] == v["daylight_k"]
		fade = [d["brightness_pct"] for _, _, d in lights[1:]]
		assert fade == sorted(fade, reverse=True), name
		assert fade[-1] == v["fade_floor_pct"] > 0, name
		# Nothing lit: the hold lights both.
		h.light(v[first_var], False)
		h.light(other, False)
		tap(h, name, own, "long_press")
		assert h.state(v[first_var]) == h.state(other) == "on", name


def test_kids_cycle_steps_up_then_off():
	# By day both lights come on at every step.
	h = house_at(12)
	h.light(STAND, False)
	h.light(KID_SPOT, False)
	for want in (10, 25, 50, 75, 100):
		tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN)
		assert h.state(STAND) == h.state(KID_SPOT) == "on", want
		assert h.pct(STAND) == h.pct(KID_SPOT) == want
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN)
	assert h.state(STAND) == h.state(KID_SPOT) == "off"
	# Double tap: both off.
	h.light(STAND, True, 50)
	h.light(KID_SPOT, True, 50)
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, "multi_press_2")
	assert h.state(STAND) == h.state(KID_SPOT) == "off"


def test_kids_cycle_night_keeps_spot_off_when_dim():
	for hour in (18, 23, 3, 5):
		h = house_at(hour)
		h.light(STAND, False)
		h.light(KID_SPOT, False)
		seen = []
		for _ in range(6):
			tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN)
			seen.append((h.pct(STAND) if h.state(STAND) == "on" else 0,
			             h.pct(KID_SPOT) if h.state(KID_SPOT) == "on" else 0))
		assert seen == [(10, 0), (25, 0), (50, 50), (75, 75), (100, 100), (0, 0)], (hour, seen)
	# From the night light (stand 10% candle, spot off) the next step is
	# 25%, still stand only, even though this button has been idle for
	# ages: the minute rule must not put the night light out.
	h = house_at(21)
	h.light(STAND, True, 10)
	h.light(KID_SPOT, False)
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, after_s=3600)
	assert h.pct(STAND) == 25 and h.state(KID_SPOT) == "off"
	# The exception is for the night light only: 25% idle at night → off.
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, after_s=61)
	assert h.state(STAND) == "off"
	# The night light counts as off by day too (still on at 06:30 from the
	# night): a tap brings the lights up, stand and spot together by day.
	h = house_at(6)
	h.light(STAND, True, 10)
	h.light(KID_SPOT, False)
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, after_s=1800)
	assert h.pct(STAND) == 25 and h.pct(KID_SPOT) == 25, (h.pct(STAND), h.state(KID_SPOT))
	# ...and a double tap still turns it off.
	h = house_at(21)
	h.light(STAND, True, 10)
	h.light(KID_SPOT, False)
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, "multi_press_2", after_s=3600)
	assert h.state(STAND) == "off"
	# A spot left on by hand is turned off by a dim night step.
	h = house_at(21)
	h.press(KID_CYCLE_BTN, "multi_press_1")
	h.light(STAND, True, 10)
	h.light(KID_SPOT, True, 10)
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN)
	assert h.pct(STAND) == 25 and h.state(KID_SPOT) == "off"
	# Double tap: both off.
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, "multi_press_2")
	assert h.state(STAND) == h.state(KID_SPOT) == "off"


def test_kids_night_mode():
	h = house_at(21)
	for e in (LR_SPOT, LR_FLOOD, KID_SPOT):
		h.light(e, True, 50)
	h.light(STAND, False)
	h.light(SKY, False)
	h.set(SKY_FADING, "on")
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN)
	assert [h.state(e) for e in (LR_SPOT, LR_FLOOD, KID_SPOT)] == ["off"] * 3
	assert h.state(STAND) == "on" and h.pct(STAND) == 10
	stand_call = [d for a, e, d in h.calls if a == "light.turn_on" and e == STAND][-1]
	assert "hs_color" in stand_call
	assert h.state(SKY) == "on" and h.pct(SKY) == 50
	sky_calls = [d for a, e, d in h.calls if a == "light.turn_on" and e == SKY]
	# One turn_on with scene and brightness: the integration powers it on
	# and orders them itself. Then fading off.
	assert sky_calls == [{"effect": "Stars against nebula", "brightness_pct": 50}], sky_calls
	assert ("switch.turn_off", SKY_FADING, {}) in h.calls
	assert h.state(SKY_FADING) == "off"
	assert h.state(DESIRED) == "16.0", "night mode must not touch the temperature"
	# Tap again: Sky Lite off, candle stand stays as a night light.
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN)
	assert h.state(SKY) == "off"
	assert h.state(STAND) == "on" and h.pct(STAND) == 10
	# And again: full night mode, Sky Lite back on.
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN)
	assert h.state(SKY) == "on" and h.pct(STAND) == 10
	# Sky Lite on but the spot is on too: not night mode yet, so apply it.
	h.light(KID_SPOT, True, 80)
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN)
	assert h.state(SKY) == "on" and h.state(KID_SPOT) == "off"
	# Double tap: bedroom off, Sky Lite included.
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, "multi_press_2")
	assert [h.state(e) for e in (STAND, KID_SPOT, SKY)] == ["off"] * 3


def test_kids_night_after_light_button():
	# 2026-09-27 evening: star → night mode; light button → stand up to
	# 25%; star again should give night mode back, not just Sky Lite off.
	h = house_at(20)
	for e in (LR_SPOT, LR_FLOOD, KID_SPOT, STAND, SKY):
		h.light(e, False)
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=3600)
	assert h.pct(STAND) == 10 and h.state(SKY) == "on"
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, after_s=24)
	assert h.pct(STAND) == 25 and h.state(KID_SPOT) == "off"
	h.calls.clear()
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=900)
	assert h.pct(STAND) == 10 and h.state(SKY) == "on", (h.pct(STAND), h.state(SKY))
	stand_call = [d for a, e, d in h.calls if a == "light.turn_on" and e == STAND][-1]
	assert "hs_color" in stand_call, "back to the candle colour"
	# Now it is as night mode left it: the next tap is Sky Lite off.
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=30)
	assert h.state(SKY) == "off" and h.pct(STAND) == 10


def test_kids_morning_mode():
	for hour in (6, 7, 9):
		h = house_at(hour)
		for e in (LR_SPOT, LR_FLOOD, KID_SPOT, STAND, SKY):
			h.light(e, False)
		h.calls.clear()
		# (Keep gaps short: the model's clock moves on by after_s.)
		tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=600)
		for e in (LR_SPOT, LR_FLOOD, KID_SPOT, STAND):
			assert h.state(e) == "on" and h.pct(e) == 40, (hour, e)
		temps = {d.get("color_temp_kelvin") for a, e, d in h.calls if a == "light.turn_on"}
		assert temps == {4000}, (hour, temps)
		assert h.state(DESIRED) == "20.0", hour
		# Repeated taps (and a tap straight after a double tap, as on
		# 2026-09-28 06:50) never bring the Sky Lite on in the morning.
		tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=3)
		tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, "multi_press_2", after_s=1)
		tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=4)
		assert h.state(SKY) == "off", hour
		assert h.state(STAND) == "on" and h.pct(STAND) == 40, hour


def test_kids_day_mode():
	for hour in (10, 12, 17):
		h = house_at(hour)
		for e in (LR_SPOT, LR_FLOOD, KID_SPOT, STAND):
			h.light(e, False)
		tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN)
		for e in (LR_SPOT, LR_FLOOD, KID_SPOT, STAND):
			assert h.state(e) == "on" and h.pct(e) == 50, (hour, e)
		assert h.state(DESIRED) == "20.0", hour
	h = house_at(18)
	h.light(STAND, False)
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN)
	assert h.pct(STAND) == 10, "18:00 is already night"


def test_kids_day_second_tap_sky_lite():
	h = house_at(13)
	for e in (LR_SPOT, LR_FLOOD, KID_SPOT, STAND, SKY):
		h.light(e, False)
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=3600)
	assert h.state(STAND) == "on" and h.state(SKY) == "off"
	# Second tap within a minute: Sky Lite on at 100%, nothing else changes.
	h.calls.clear()
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=5)
	assert h.state(SKY) == "on" and h.pct(SKY) == 100
	sky_calls = [(a, e, d) for a, e, d in h.calls if a.startswith("light.")]
	assert sky_calls == [("light.turn_on", SKY, {"brightness_pct": 100})], sky_calls
	# Much later, a tap is day mode again (Sky Lite left as it is).
	h.light(STAND, False)
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=120)
	assert h.state(STAND) == "on" and h.pct(STAND) == 50
	assert h.state(SKY) == "on"
	# A copy of the first tap (the kid's remote sends some presses twice)
	# is dropped, not taken as a second tap.
	h = house_at(13)
	h.light(SKY, False)
	tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=3600)
	assert tap(h, "BilresaKidsRoomNight.yaml", KID_NIGHT_BTN, after_s=0.005) == "blocked"
	assert h.state(SKY) == "off"


def test_desired_temperature():
	# Turning on raises 16 → 20.
	h = house_at(20)
	h.light(GOLD, False)
	h.light(BIO_FLOOD, False)
	tap(h, "BilresaBio.yaml", BIO_BTN)
	assert h.state(DESIRED) == "20.0"
	# Never lowers.
	h.set(DESIRED, "22.0")
	tap(h, "BilresaBio.yaml", BIO_BTN)
	assert h.state(DESIRED) == "22.0"
	# Turning off does not touch it.
	h = house_at(20)
	h.light(GOLD, False)
	h.light(BIO_FLOOD, True, 20)
	tap(h, "BilresaBio.yaml", BIO_BTN)
	assert h.state(BIO_FLOOD) == "off" and h.state(DESIRED) == "16.0"
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, "multi_press_2")
	assert h.state(DESIRED) == "16.0"
	# Holiday mode: leave it to DaytimeCheapHeat.
	h = house_at(20)
	h.set(HOLIDAY, "on")
	h.light(LR_SPOT, False)
	h.light(LR_FLOOD, False)
	tap(h, "BilresaLivingRoom.yaml", LR_BTN)
	assert h.state(DESIRED) == "16.0"


def test_duplicate_events_dropped():
	for name, own, *_ in PER_BUTTON:
		h = house_at(20)
		h.press(own, "multi_press_1", after_s=10)
		assert h.fire(name, own, "multi_press_1") != "blocked", name
		h.press(own, "multi_press_1", after_s=0.005)
		assert h.fire(name, own, "multi_press_1") == "blocked", name
		# A different type straight after is a real event.
		h.press(own, "long_press", after_s=10)
		h.fire(name, own, "long_press")
		h.press(own, "long_release", after_s=0.2)
		assert h.fire(name, own, "long_release") != "blocked", name
	h = house_at(20)
	h.press(LR_BTN, "multi_press_1", after_s=10)
	h.press(BIO_BTN, "multi_press_1", after_s=0.1)
	h.press(BIO_BTN, "multi_press_1", after_s=0.005)
	assert h.fire("BilresaGoingOut.yaml", BIO_BTN, "multi_press_1") == "blocked"


def test_idle_survives_duplicates():
	# Kid's remote: every press arrives twice. 60% lit, then a minute's
	# quiet: the first copy turns them off, the second is dropped.
	h = house_at(20)
	h.light(STAND, True, 60)
	h.light(KID_SPOT, True, 60)
	for gap in (10, 0.004):
		h.press(KID_CYCLE_BTN, "multi_press_1", after_s=gap)
		h.fire("BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, "multi_press_1")
	h.light(STAND, True, 60)
	h.light(KID_SPOT, True, 60)
	results = []
	for gap in (61, 0.004):
		h.press(KID_CYCLE_BTN, "multi_press_1", after_s=gap)
		results.append(h.fire("BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, "multi_press_1"))
	assert results == ["ran", "blocked"]
	assert h.state(STAND) == h.state(KID_SPOT) == "off"


def test_idle_tap_turns_off():
	for name, own, first_var, _ in ROOMS:
		doc = load(name)
		first, flood = doc["variables"][first_var], doc["variables"]["flood"]
		for lit in (("on", "off"), ("on", "on"), ("off", "on")):
			h = house_at(20)
			h.light(first, lit[0] == "on", 20)
			h.light(flood, lit[1] == "on", 20)
			tap(h, name, own, after_s=10)          # a recent press...
			h.light(first, lit[0] == "on", 20)     # ...put back where we were
			h.light(flood, lit[1] == "on", 20)
			tap(h, name, own, after_s=61)          # then a minute's quiet
			assert (h.state(first), h.state(flood)) == ("off", "off"), (name, lit)
		# From off, a tap after a long wait still starts the cycle.
		h = house_at(20)
		h.light(first, False)
		h.light(flood, False)
		tap(h, name, own, after_s=600)
		assert (h.state(first), h.state(flood)) == ("on", "off"), name
		# Quick taps keep cycling.
		tap(h, name, own, after_s=59)
		assert (h.state(first), h.state(flood)) == ("on", "on"), name
	# Kid's room: 60% lit, a minute's quiet → off, not 100%.
	h = house_at(20)
	h.light(STAND, False)
	h.light(KID_SPOT, False)
	for _ in range(3):
		tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN)
	assert h.pct(STAND) == 50
	desired = h.state(DESIRED)
	tap(h, "BilresaKidsRoomCycle.yaml", KID_CYCLE_BTN, after_s=61)
	assert h.state(STAND) == h.state(KID_SPOT) == "off"
	assert h.state(DESIRED) == desired


def _both(h: House, first: str, second: str, gap_s: float, event_type="multi_press_1", dry_run=False):
	"""Press two buttons gap_s apart; deliver each event to every automation."""
	names = [n for n, own, sib in PER_BUTTON if {own, sib} == {first, second}]
	going_out = {"dry_run": dry_run}
	results = {}
	h.press(first, event_type, after_s=10)
	for n in names:
		results[(n, first)] = h.fire(n, first, event_type)
	results[("BilresaGoingOut.yaml", first)] = h.fire("BilresaGoingOut.yaml", first, event_type, going_out)
	h.press(second, event_type, after_s=gap_s)
	for n in names:
		results[(n, second)] = h.fire(n, second, event_type)
	results[("BilresaGoingOut.yaml", second)] = h.fire("BilresaGoingOut.yaml", second, event_type, going_out)
	return results


def test_going_out_dry_run_changes_nothing():
	assert load("BilresaGoingOut.yaml")["variables"]["dry_run"] is True, "shipped in test mode"
	h = house_at(20)
	for e in (STAIRS, LR_SPOT, GOLD, STAND):
		h.light(e, True, 40)
	h.set(DESIRED, "21.0")
	h.calls.clear()
	r = _both(h, KID_CYCLE_BTN, KID_NIGHT_BTN, gap_s=0.2, event_type="long_press", dry_run=True)
	assert r[("BilresaGoingOut.yaml", KID_NIGHT_BTN)] == "stopped"
	for e in (LR_SPOT, GOLD):
		assert h.state(e) == "on", e
	assert h.state(DESIRED) == "21.0"
	notes = [d for a, _, d in h.calls if a == "persistent_notification.create"]
	assert len(notes) == 1
	assert "0.2 s apart" in notes[0]["message"]
	assert GOLD in notes[0]["message"] and STAIRS not in notes[0]["message"]


def test_going_out_both_buttons():
	for first, second in ((LR_BTN, BIO_BTN), (KID_NIGHT_BTN, KID_CYCLE_BTN)):
		h = house_at(20)
		for e in (STAIRS, FISH, PORCH, LR_SPOT, GOLD, STAND, SKY):
			h.light(e, True, 40)
		h.set(DESIRED, "21.0")
		# In HA the first press is still in its 0.5 s wait when the second
		# lands, and the second restarts it. The model runs it to the end,
		# which only lights things Going Out then turns off.
		r = _both(h, first, second, gap_s=0.2, event_type="long_press")
		assert r[("BilresaGoingOut.yaml", first)] == "blocked"
		assert r[("BilresaGoingOut.yaml", second)] == "ran"
		for n, own, sib in PER_BUTTON:
			if {own, sib} == {first, second}:
				assert r[(n, second)] == "stopped", (n, second)
		for e in (LR_SPOT, GOLD, STAND, SKY):
			assert h.state(e) == "off", e
		for e in (STAIRS, FISH, PORCH):
			assert h.state(e) == "on", e
		assert h.state(DESIRED) == "16.0"


def test_going_out_needs_a_hold():
	# Hold both: Going Out.
	h = house_at(20)
	r = _both(h, LR_BTN, BIO_BTN, gap_s=0.2, event_type="long_press")
	assert r[("BilresaGoingOut.yaml", BIO_BTN)] == "ran"
	# Tap both (what the 2026-09-26 replay looked like): not Going Out.
	# Taps no longer wait for a partner (2026-09-27), so each button just
	# does its own tap and the sibling's tap is filtered out.
	h = house_at(20)
	for e in (LR_SPOT, LR_FLOOD, GOLD, BIO_FLOOD):
		h.light(e, False)
	r = _both(h, LR_BTN, BIO_BTN, gap_s=0.005)
	assert r[("BilresaGoingOut.yaml", BIO_BTN)] == "blocked"
	assert r[("BilresaLivingRoom.yaml", LR_BTN)] == "ran"
	assert r[("BilresaLivingRoom.yaml", BIO_BTN)] == "blocked"
	assert r[("BilresaBio.yaml", BIO_BTN)] == "ran"
	assert h.state(LR_SPOT) == "on" and h.state(GOLD) == "on"
	assert h.state(DESIRED) != "16.0"
	# A pair of releases is not Going Out either.
	h = house_at(20)
	r = _both(h, LR_BTN, BIO_BTN, gap_s=0.2, event_type="long_release")
	assert r[("BilresaGoingOut.yaml", BIO_BTN)] == "blocked"


def test_ignored_during_firmware_update():
	updates = {
		LR_BTN: "update.bilresa_dual_button_firmware",
		BIO_BTN: "update.bilresa_dual_button_firmware",
		KID_CYCLE_BTN: "update.bedroom_kid_s_room_bilresa_firmware",
		KID_NIGHT_BTN: "update.bedroom_kid_s_room_bilresa_firmware",
		QR_LIGHT_BTN: "update.quiet_room_quiet_room_bilresa_firmware",
		QR_STAND_BTN: "update.quiet_room_quiet_room_bilresa_firmware",
	}
	for name, own, sibling in PER_BUTTON:
		h = house_at(20)
		h.set(updates[own], "on", {"in_progress": True})
		h.press(own, "multi_press_1", after_s=10)
		assert h.fire(name, own, "multi_press_1") == "blocked", name
		h.set(updates[own], "on", {"in_progress": False})
		h.press(own, "multi_press_1", after_s=10)
		assert h.fire(name, own, "multi_press_1") != "blocked", name
	h = house_at(20)
	h.set(updates[LR_BTN], "on", {"in_progress": True})
	r = _both(h, LR_BTN, BIO_BTN, gap_s=0.2, event_type="long_press")
	assert r[("BilresaGoingOut.yaml", BIO_BTN)] == "blocked"
	# The other remote is unaffected.
	r = _both(h, KID_CYCLE_BTN, KID_NIGHT_BTN, gap_s=0.2, event_type="long_press")
	assert r[("BilresaGoingOut.yaml", KID_NIGHT_BTN)] == "ran"


def test_not_going_out_when_apart():
	h = house_at(20)
	h.light(STAIRS, True, 40)
	h.light(LR_SPOT, False)
	h.light(LR_FLOOD, False)
	h.light(GOLD, False)
	h.light(BIO_FLOOD, False)
	r = _both(h, LR_BTN, BIO_BTN, gap_s=1.0)
	assert r[("BilresaGoingOut.yaml", BIO_BTN)] == "blocked"
	# Each button did its own thing; the sibling event was filtered out.
	assert r[("BilresaLivingRoom.yaml", LR_BTN)] == "ran"
	assert r[("BilresaLivingRoom.yaml", BIO_BTN)] == "blocked"
	assert r[("BilresaBio.yaml", BIO_BTN)] == "ran"
	assert h.state(LR_SPOT) == "on" and h.state(GOLD) == "on"
	assert h.state(DESIRED) == "20.0"


def test_room_hold_from_off():
	for name, own, first_var, preset_key in ROOMS:
		doc = load(name)
		v = doc["variables"]
		first, flood = v[first_var], v["flood"]
		h = house_at(20)
		h.light(first, False)
		h.light(flood, False)
		h.calls.clear()
		tap(h, name, own, "long_press")
		ons = [(e, d) for a, e, d in h.calls if a == "light.turn_on"]
		# Both on at 50% in their warm settings first...
		assert ons[0] == (first, {"brightness_pct": 50, preset_key: ons[0][1][preset_key]}), (name, ons)
		assert ons[1] == (flood, {"brightness_pct": 50, "color_temp_kelvin": v["flood_warm_k"]}), (name, ons)
		# ...then, still held, both to 100% daylight, and that is all.
		assert ons[2:] == [(first, {"brightness_pct": 100, "color_temp_kelvin": v["daylight_k"]}),
		                   (flood, {"brightness_pct": 100, "color_temp_kelvin": v["daylight_k"]})], (name, ons)
		# Hold again (now lit): the old 100% daylight + fade.
		h.calls.clear()
		tap(h, name, own, "long_press")
		fade = [d["brightness_pct"] for a, e, d in h.calls if a == "light.turn_on" and e == flood]
		assert fade[0] == 100 and fade[-1] == v["fade_floor_pct"], (name, fade)


# Button 1 (bedroom light). The stand button has its own tests below:
# since 2026-10-05 it steps stand + candle lamp instead of colours.
QR = (
	("BilresaQuietRoomLight.yaml", QR_LIGHT_BTN, QR_LIGHT, QR_STAND, QR_LIGHT_HELPER, 10),
)


def _colour(call_data):
	return call_data.get("color_temp_kelvin", call_data.get("hs_color"))


def test_quiet_room_tap_cycles_colours():
	for name, btn, lamp, other, helper, n in QR:
		palette = load(name)["variables"]["palette"]
		assert len(palette) == n, name
		h = house_at(22)
		h.light(lamp, False)
		# From off: on in the last colour (helper starts at 1, warm white).
		h.calls.clear()
		tap(h, name, btn, after_s=3600)
		assert h.state(lamp) == "on"
		assert _colour(h.calls[-1][2]) == 2700 and "brightness" not in h.calls[-1][2], h.calls
		# Each quick tap moves to the next colour, wrapping round.
		seen = []
		for _ in range(n):
			h.calls.clear()
			tap(h, name, btn, after_s=5)
			seen.append(_colour([c for c in h.calls if c[0] == "light.turn_on"][-1][2]))
		expected = [p.get("k", p.get("hs")) for p in palette]
		assert seen == expected[2:] + expected[:2], (name, seen)
		assert h.state(helper) == "1.0", (name, h.state(helper))
	# The bedroom light palette matches the old ESPHome box.
	names = [p["name"] for p in load("BilresaQuietRoomLight.yaml")["variables"]["palette"]]
	assert names == ["Candle", "Warm white", "Neutral", "Daylight", "Red", "Orange",
	                 "Purple", "Blue", "Green", "Pink"], names


def test_quiet_room_idle_and_double_taps():
	for name, btn, lamp, other, helper, n in QR:
		# A tap after a minute of quiet turns it off.
		h = house_at(22)
		h.light(lamp, True, 50)
		h.light(other, True, 50)
		tap(h, name, btn, after_s=61)
		assert h.state(lamp) == "off" and h.state(other) == "on", name
		# Double tap (recent): this light only.
		h = house_at(22)
		h.light(lamp, True, 50)
		h.light(other, True, 50)
		h.press(btn, "multi_press_1")
		tap(h, name, btn, "multi_press_2", after_s=5)
		assert h.state(lamp) == "off" and h.state(other) == "on", name
		# Double tap after a minute of quiet: every quiet-room light off,
		# the candle lamp included.
		h = house_at(22)
		h.light(lamp, True, 50)
		h.light(other, True, 50)
		h.light(QR_CANDLE, True, 50)
		tap(h, name, btn, "multi_press_2", after_s=61)
		assert h.state(lamp) == h.state(other) == h.state(QR_CANDLE) == "off", name
		# The desired temperature is never touched here.
		assert h.state(DESIRED) == "16.0"


def test_quiet_room_hold_steps_brightness():
	levels = [10, 30, 60, 90, 130, 180, 230, 255]
	for name, btn, lamp, other, helper, n in QR:
		# Lit at 130: steps from the next level up, wrapping round.
		h = house_at(22)
		h.set(lamp, "on", {"brightness": 128})
		h.calls.clear()
		tap(h, name, btn, "long_press")
		steps = [d["brightness"] for a, e, d in h.calls if a == "light.turn_on"]
		assert steps[:6] == [180, 230, 255, 10, 30, 60], (name, steps[:6])
		assert len(steps) == load(name)["variables"]["max_steps"]
		# From off: on in the last colour at the lowest level, then up.
		h = house_at(22)
		h.light(lamp, False)
		h.calls.clear()
		tap(h, name, btn, "long_press")
		ons = [d for a, e, d in h.calls if a == "light.turn_on"]
		assert ons[0] == {"color_temp_kelvin": 2700, "brightness": 10}, (name, ons[0])
		assert [d["brightness"] for d in ons[1:4]] == [30, 60, 90], (name, ons[:4])


STAND_FILE = "BilresaQuietRoomStand.yaml"


def _qr_off(h):
	for e in (QR_STAND, QR_CANDLE, QR_LIGHT):
		h.light(e, False)


def test_quiet_room_stand_tap_steps():
	h = house_at(21)
	_qr_off(h)
	# All off → stand on in its last colour + candle at 50% warm white.
	h.calls.clear()
	tap(h, STAND_FILE, QR_STAND_BTN, after_s=3600)
	assert h.state(QR_STAND) == "on" and h.state(QR_CANDLE) == "on"
	candle = [d for a, e, d in h.calls if a == "light.turn_on" and e == QR_CANDLE][-1]
	assert candle == {"brightness_pct": 50, "color_temp_kelvin": 2000}, candle
	stand = [d for a, e, d in h.calls if a == "light.turn_on" and e == QR_STAND][-1]
	assert stand == {"color_temp_kelvin": 2700}, stand  # helper 1 = warm white
	# Hours later: stand off, candle stays (no minute rule on this button).
	tap(h, STAND_FILE, QR_STAND_BTN, after_s=3 * 3600)
	assert h.state(QR_STAND) == "off" and h.state(QR_CANDLE) == "on"
	# Next tap: candle off, all off.
	tap(h, STAND_FILE, QR_STAND_BTN, after_s=600)
	assert h.state(QR_STAND) == h.state(QR_CANDLE) == "off"
	# And round again.
	tap(h, STAND_FILE, QR_STAND_BTN, after_s=5)
	assert h.state(QR_STAND) == h.state(QR_CANDLE) == "on"
	# Stand on by other means, candle off: the tap still leaves the candle on.
	h = house_at(21)
	_qr_off(h)
	h.light(QR_STAND, True, 50)
	tap(h, STAND_FILE, QR_STAND_BTN, after_s=600)
	assert h.state(QR_STAND) == "off" and h.state(QR_CANDLE) == "on"
	assert h.pct(QR_CANDLE) == 50
	# The bedroom light is never touched by a tap, and nor is the heating.
	assert h.state(QR_LIGHT) == "off" and h.state(DESIRED) == "16.0"


def test_quiet_room_stand_double_taps():
	# Recent double tap: stand and candle off, bedroom light left alone.
	h = house_at(21)
	for e in (QR_STAND, QR_CANDLE, QR_LIGHT):
		h.light(e, True, 50)
	h.press(QR_STAND_BTN, "multi_press_1")
	tap(h, STAND_FILE, QR_STAND_BTN, "multi_press_2", after_s=5)
	assert h.state(QR_STAND) == h.state(QR_CANDLE) == "off"
	assert h.state(QR_LIGHT) == "on"
	# After a minute of quiet: every quiet-room light off.
	h = house_at(21)
	for e in (QR_STAND, QR_CANDLE, QR_LIGHT):
		h.light(e, True, 50)
	tap(h, STAND_FILE, QR_STAND_BTN, "multi_press_2", after_s=61)
	assert h.state(QR_STAND) == h.state(QR_CANDLE) == h.state(QR_LIGHT) == "off"


def test_quiet_room_stand_hold():
	# Stand lit at 130: steps the stand from the next level up.
	h = house_at(21)
	_qr_off(h)
	h.set(QR_STAND, "on", {"brightness": 128})
	h.light(QR_CANDLE, True, 50)
	h.calls.clear()
	tap(h, STAND_FILE, QR_STAND_BTN, "long_press")
	steps = [(e, d["brightness"]) for a, e, d in h.calls if a == "light.turn_on"]
	assert steps[:3] == [(QR_STAND, 180), (QR_STAND, 230), (QR_STAND, 255)], steps[:3]
	# Only the candle on: steps the candle.
	h = house_at(21)
	_qr_off(h)
	h.set(QR_CANDLE, "on", {"brightness": 128})
	h.calls.clear()
	tap(h, STAND_FILE, QR_STAND_BTN, "long_press")
	ents = {e for a, e, d in h.calls if a == "light.turn_on"}
	assert ents == {QR_CANDLE}, ents
	# All off: stand at the lowest level + candle, then the stand steps up.
	h = house_at(21)
	_qr_off(h)
	h.calls.clear()
	tap(h, STAND_FILE, QR_STAND_BTN, "long_press")
	ons = [(e, d) for a, e, d in h.calls if a == "light.turn_on"]
	assert ons[0] == (QR_STAND, {"color_temp_kelvin": 2700, "brightness": 10}), ons[0]
	assert ons[1] == (QR_CANDLE, {"brightness_pct": 50, "color_temp_kelvin": 2000}), ons[1]
	assert [d["brightness"] for e, d in ons[2:5]] == [30, 60, 90], ons[2:5]
	assert all(e == QR_STAND for e, d in ons[2:]), "only the stand steps"


def test_quiet_room_both_buttons():
	h = house_at(22)
	h.light(QR_LIGHT, True, 50)
	r = _both(h, QR_LIGHT_BTN, QR_STAND_BTN, gap_s=0.2, event_type="long_press")
	assert r[("BilresaQuietRoomLight.yaml", QR_STAND_BTN)] == "stopped"
	assert r[("BilresaQuietRoomStand.yaml", QR_STAND_BTN)] == "stopped"
	assert r[("BilresaGoingOut.yaml", QR_STAND_BTN)] == "ran"


if __name__ == "__main__":
	for fn in (
		test_shape,
		test_room_tap_cycle,
		test_room_double_tap_and_release,
		test_hold_fade,
		test_kids_cycle_steps_up_then_off,
		test_kids_cycle_night_keeps_spot_off_when_dim,
		test_kids_night_mode,
		test_kids_night_after_light_button,
		test_kids_morning_mode,
		test_kids_day_mode,
		test_kids_day_second_tap_sky_lite,
		test_desired_temperature,
		test_idle_tap_turns_off,
		test_duplicate_events_dropped,
		test_idle_survives_duplicates,
		test_going_out_dry_run_changes_nothing,
		test_going_out_both_buttons,
		test_going_out_needs_a_hold,
		test_ignored_during_firmware_update,
		test_room_hold_from_off,
		test_quiet_room_tap_cycles_colours,
		test_quiet_room_idle_and_double_taps,
		test_quiet_room_hold_steps_brightness,
		test_quiet_room_stand_tap_steps,
		test_quiet_room_stand_double_taps,
		test_quiet_room_stand_hold,
		test_quiet_room_both_buttons,
		test_not_going_out_when_apart,
	):
		fn()
		print(f"ok  {fn.__name__}")
