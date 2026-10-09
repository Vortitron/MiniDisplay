#!/usr/bin/env python3
"""Tests for OTBR / Matter recovery watchdog helpers.

Run with:  python3 OrangePiThreadBorderRouter/tests/test_otbr_watchdog.py
       or:  python3 -m pytest OrangePiThreadBorderRouter/tests/test_otbr_watchdog.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

import otbr_watchdog as w  # noqa: E402


SAMPLE_NEIGHBORS = """\
| Role | RLOC16 | Age | Avg RSSI | Last RSSI |R|D|N| Extended MAC     | Version |
+------+--------+-----+----------+-----------+-+-+-+------------------+---------+
|   R  | 0x3400 |   5 |      -62 |       -62 |1|1|1| 82d5ab067445659a |       5 |
|   R  | 0xc400 |  14 |      -94 |       -94 |1|1|1| 3a18313c9a264167 |       5 |
|   R  | 0xd400 |   5 |      -91 |       -91 |1|1|1| 160469c2a7fb3e3c |       5 |
"""


def test_neighbor_count_counts_routers_and_ignores_header():
	assert w.neighbor_count(SAMPLE_NEIGHBORS) == 3
	assert w.neighbor_count("Done\n") == 0
	assert w.neighbor_count("|   C  | 0x1001 |   1 |      -50 |       -50 |1|0|1| aabb |       5 |\n") == 1


def test_file_age_missing_is_infinite(tmp_path: Path):
	assert w.file_age_seconds(tmp_path / "missing.txt") == float("inf")
	assert w.cooldown_elapsed(tmp_path / "missing.txt", 600) is True


def test_cooldown_respects_timestamp(tmp_path: Path):
	stamp = tmp_path / "last.txt"
	w.record_timestamp(stamp, now=1_000.0)
	assert w.cooldown_elapsed(stamp, 600, now=1_100.0) is False
	assert w.cooldown_elapsed(stamp, 600, now=1_700.0) is True


def test_ha_unreachable_flag(tmp_path: Path):
	flag = tmp_path / "ha_reachable.txt"
	assert w.ha_was_unreachable(flag) is False
	w.write_ha_reachable(False, flag)
	assert w.ha_was_unreachable(flag) is True
	w.write_ha_reachable(True, flag)
	assert w.ha_was_unreachable(flag) is False


def test_matter_controller_stuck_requires_all_lights_down():
	ids = ("light.a", "light.b")
	assert w.matter_controller_stuck({}, ids) is False
	assert w.matter_controller_stuck({"light.a": "unavailable", "light.b": "on"}, ids) is False
	assert w.matter_controller_stuck({"light.a": "unavailable", "light.b": "unavailable"}, ids) is True
	assert w.matter_controller_stuck({"light.a": "unavailable"}, ids) is True
	assert w.matter_controller_stuck({"light.a": "off", "light.b": "on"}, ids) is False


def test_matter_kick_reason_recovery_beats_mesh():
	assert (
		w.matter_kick_reason(ha_recovered=True, controller_stuck=False, mesh_up=False)
		== "HA link recovered after an outage"
	)
	assert (
		w.matter_kick_reason(ha_recovered=False, controller_stuck=True, mesh_up=True)
		== "Matter nodes unavailable while Thread mesh is up"
	)
	assert w.matter_kick_reason(ha_recovered=False, controller_stuck=True, mesh_up=False) is None
	assert w.matter_kick_reason(ha_recovered=False, controller_stuck=False, mesh_up=True) is None


def test_commands_use_absolute_paths_for_cron():
	# Cron runs with PATH=/usr/bin:/bin. A bare "sysctl" (/usr/sbin) made
	# every run die on its first step from 2026-09-20 to 2026-10-05.
	assert w.SYSCTL.startswith("/") and w.DOCKER.startswith("/")
	src = (ROOT / "otbr_watchdog.py").read_text()
	for bare in ('["sysctl"', '["docker"', '["ot-ctl"', '["ip"'):
		assert bare not in src, f"bare command {bare} depends on cron PATH"


def test_matter_action_never_restarts_addon_when_local():
	stuck = "Matter nodes unavailable while Thread mesh is up"
	# Add-on controller (today): both reasons restart the add-on.
	assert w.matter_action(w.HA_RECOVERED_REASON, local=False) == "addon"
	assert w.matter_action(stuck, local=False) == "addon"
	# Local controller: an HA link outage needs nothing, a stuck controller
	# restarts the local container, and the add-on is never touched.
	assert w.matter_action(w.HA_RECOVERED_REASON, local=True) is None
	assert w.matter_action(stuck, local=True) == "local"
	assert w.matter_kick_reason(ha_recovered=True, controller_stuck=False, mesh_up=True) == w.HA_RECOVERED_REASON


def _all_tests():
	return [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


if __name__ == "__main__":
	import tempfile

	tests = _all_tests()
	for t in tests:
		if "tmp_path" in t.__code__.co_varnames:
			with tempfile.TemporaryDirectory() as tmp:
				t(Path(tmp))
		else:
			t()
	print(f"OK: {len(tests)} otbr watchdog tests passed.")
