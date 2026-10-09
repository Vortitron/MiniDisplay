#!/usr/bin/env python3
"""Unit tests for FeedSwapLightRestore.yaml - snapshot/restore of the lights.

Mirrors the two Jinja halves of the automation:

  encode()   the SNAPSHOT branch: one character per tracked light
             ('-' off, '#' on without brightness, 0-9a-z brightness bucket,
             '?' never seen), keeping the previous character for a light that
             is unavailable right now.
  guard()    the jump guard: a surge of newly-lit lights (the power coming
             back) must not overwrite the snapshot, but a real one does after
             max_skips consecutive holds.
  restore()  one pass of the RESTORE branch: which lights to turn off, which
             to turn on plain, which to turn on at a brightness, and the new
             pending string with everything handled marked '.'.

Run: python3 ElectricAutomations/tests/test_feed_swap_light_restore.py
 or: python3 -m pytest ElectricAutomations/tests/test_feed_swap_light_restore.py
"""

from __future__ import annotations

CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"
JUMP = 3
MAX_SKIPS = 3

# A miniature house: two dimmable bulbs, one plain (ISP strip), one dimmable.
LIGHTS = ["light.a", "light.b", "light.strip", "light.c"]
PLAIN = ["light.strip"]


def bucket(brightness: int) -> int:
	return round(brightness / 255 * 35)


def unbucket(b: int) -> int:
	return max(1, round(b * 255 / 35))


def encode(states, old_code, lights=LIGHTS, plain=PLAIN):
	"""states: {entity: (state, brightness|None)}. old_code: '' if unusable."""
	old_ok = len(old_code) == len(lights)
	out = ""
	for i, e in enumerate(lights):
		st, br = states[e]
		if st == "off":
			out += "-"
		elif st == "on":
			out += "#" if (e in plain or br is None) else CHARS[bucket(br)]
		else:  # unavailable / unknown - keep what we knew
			out += old_code[i] if old_ok else "?"
	return out


def lit(code: str) -> int:
	return len(code.replace("-", "").replace("?", ""))


def guard(new_code, old_code, skips, lights=LIGHTS):
	"""Returns (hold, stored_code, stored_skips)."""
	old_ok = len(old_code) == len(lights)
	surge = old_ok and (lit(new_code) - lit(old_code)) >= JUMP
	hold = surge and skips < MAX_SKIPS
	if hold:
		return True, old_code, skips + 1
	return False, new_code, 0


def restore(pending, states, lights=LIGHTS):
	"""One pass. Returns (to_off, to_on_plain, to_on_dim, new_pending)."""
	todo = []
	for i, e in enumerate(lights):
		want = pending[i]
		if want == ".":
			continue
		st, br = states[e]
		if st not in ("on", "off"):
			continue  # still offline - leave it pending for a later pass
		cur = bucket(br) if (st == "on" and br is not None) else -1
		todo.append({"e": e, "want": want, "st": st, "cur": cur})

	to_off = [it["e"] for it in todo if it["want"] == "-" and it["st"] == "on"]
	to_on_plain = [it["e"] for it in todo if it["want"] == "#" and it["st"] == "off"]
	to_on_dim = []
	for it in todo:
		if it["want"] in "-#":
			continue
		wb = CHARS.index(it["want"])
		if it["st"] == "off" or it["cur"] != wb:
			to_on_dim.append({"e": it["e"], "b": unbucket(wb)})

	handled = [it["e"] for it in todo]
	new_pending = "".join(
		"." if e in handled else pending[i] for i, e in enumerate(lights)
	)
	return to_off, to_on_plain, to_on_dim, new_pending


# --- encoding ---------------------------------------------------------------

def test_encode_off_on_and_brightness():
	states = {
		"light.a": ("off", None),
		"light.b": ("on", 255),
		"light.strip": ("on", 128),   # plain -> '#', brightness ignored
		"light.c": ("on", 1),         # lowest bucket
	}
	assert encode(states, "") == "-z#0"


def test_encode_on_without_brightness_is_plain():
	states = {
		"light.a": ("on", None),
		"light.b": ("off", None),
		"light.strip": ("off", None),
		"light.c": ("off", None),
	}
	assert encode(states, "") == "#---"


def test_unavailable_keeps_previous_character():
	# Mid-blackout: everything unavailable. The snapshot must not be erased.
	states = {e: ("unavailable", None) for e in LIGHTS}
	assert encode(states, "-z#0") == "-z#0"


def test_unavailable_with_no_history_is_question_mark():
	states = {e: ("unavailable", None) for e in LIGHTS}
	assert encode(states, "") == "????"


def test_brightness_bucket_round_trip_within_tolerance():
	for b in (1, 12, 60, 115, 128, 200, 255):
		assert abs(unbucket(bucket(b)) - b) <= 4


# --- the jump guard ---------------------------------------------------------

def test_power_on_surge_is_held():
	# Snapshot said one light on; the feed came back and lit three more.
	hold, code, skips = guard("zz#z", "-z--", skips=0)
	assert hold and code == "-z--" and skips == 1


def test_small_change_is_recorded_normally():
	hold, code, skips = guard("-zz-", "-z--", skips=0)
	assert not hold and code == "-zz-" and skips == 0


def test_turning_lights_off_is_never_a_surge():
	hold, code, skips = guard("----", "zz#z", skips=0)
	assert not hold and code == "----"


def test_guard_releases_after_max_skips():
	# You really did put four lights on and left them on.
	code, skips = "-z--", 0
	for _ in range(MAX_SKIPS):
		hold, code, skips = guard("zz#z", code, skips)
		assert hold
	hold, code, skips = guard("zz#z", code, skips)
	assert not hold and code == "zz#z" and skips == 0


def test_no_snapshot_yet_is_not_a_surge():
	hold, code, skips = guard("zz#z", "", skips=0)
	assert not hold and code == "zz#z"


# --- restoring --------------------------------------------------------------

def test_lights_that_came_back_on_are_turned_off():
	# Snapshot: everything was off. The swap lit them all.
	states = {e: ("on", 255) for e in LIGHTS}
	to_off, to_on_plain, to_on_dim, pending = restore("----", states)
	assert to_off == LIGHTS
	assert to_on_plain == [] and to_on_dim == []
	assert pending == "...."


def test_light_is_put_back_to_its_old_brightness():
	states = {
		"light.a": ("on", 255),   # was at bucket 8 (~60)
		"light.b": ("off", None),
		"light.strip": ("off", None),
		"light.c": ("off", None),
	}
	to_off, to_on_plain, to_on_dim, pending = restore("8-#-", states)
	assert to_off == []
	assert to_on_plain == ["light.strip"]          # plain: bare turn_on
	assert to_on_dim == [{"e": "light.a", "b": unbucket(8)}]
	assert pending == "...."


def test_already_correct_light_is_not_touched_but_is_marked_done():
	states = {
		"light.a": ("on", unbucket(8)),
		"light.b": ("off", None),
		"light.strip": ("on", 255),
		"light.c": ("off", None),
	}
	to_off, to_on_plain, to_on_dim, pending = restore("8-#-", states)
	assert to_off == [] and to_on_plain == [] and to_on_dim == []
	assert pending == "...."


def test_offline_light_is_left_for_a_later_pass():
	states = {
		"light.a": ("unavailable", None),
		"light.b": ("on", 255),
		"light.strip": ("unavailable", None),
		"light.c": ("off", None),
	}
	to_off, _, _, pending = restore("----", states)
	assert to_off == ["light.b"]
	assert pending == "-.-."          # a and strip still pending

	# Next pass, a is back and gets dealt with; strip is still missing.
	states["light.a"] = ("on", 255)
	to_off, _, _, pending = restore(pending, states)
	assert to_off == ["light.a"]
	assert pending == "..-."


def test_each_light_is_touched_only_once():
	# a is restored to off on pass 1; if someone switches it on during the
	# restore window, pass 2 must leave it alone.
	states = {
		"light.a": ("on", 255),
		"light.b": ("off", None),
		"light.strip": ("off", None),
		"light.c": ("off", None),
	}
	to_off, _, _, pending = restore("----", states)
	assert to_off == ["light.a"] and pending == "...."
	states["light.a"] = ("on", 255)
	to_off, to_on_plain, to_on_dim, pending = restore(pending, states)
	assert to_off == [] and to_on_plain == [] and to_on_dim == []


def test_never_seen_lights_are_skipped_at_the_start():
	# The automation replaces '?' with '.' before the first pass.
	start = "?-?-".replace("?", ".")
	assert start == ".-.-"
	states = {e: ("on", 255) for e in LIGHTS}
	to_off, _, _, pending = restore(start, states)
	assert to_off == ["light.b", "light.c"]
	assert pending == "...."


def test_restore_finishes_when_nothing_is_pending():
	assert "....".replace(".", "") == ""


def _run_all():
	fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
	for fn in fns:
		fn()
	print(f"OK - {len(fns)} feed-swap light restore tests passed")


if __name__ == "__main__":
	_run_all()
