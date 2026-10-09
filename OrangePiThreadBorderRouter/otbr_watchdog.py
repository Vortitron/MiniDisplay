#!/usr/bin/env python3
"""
Thread border router + Matter recovery watchdog.

1. Re-applies IPv6 sysctls that otbr-agent/the kernel can reset.
2. Restarts the local otbr container only if HA's Thread panel cannot see
   the border router (https://github.com/home-assistant/core/issues/110152).
3. Restarts the GamlaBio Matter Server add-on when the HA link comes back
   after an outage, or when every Matter light is unavailable while the
   Thread mesh still has neighbours. CHIP's reconnect backoff can sit at
   30–60 minutes after a VPN blip; an add-on restart clears it.

Token is read from TOKEN_FILE on the Pi; do not commit ha_token.txt.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HA_WS_URL = "ws://192.168.1.15:8123/api/websocket"
HA_REST_URL = "http://192.168.1.15:8123"
TOKEN_FILE = Path("/root/otbr/watchdog/ha_token.txt")
STATE_FILE = Path("/root/otbr/watchdog/last_restart.txt")
MATTER_RESTART_FILE = Path("/root/otbr/watchdog/last_matter_restart.txt")
HA_REACHABLE_FILE = Path("/root/otbr/watchdog/ha_reachable.txt")
LOG_FILE = Path("/root/otbr/watchdog/watchdog.log")
DISCOVER_WINDOW_SECONDS = 8
MIN_RESTART_INTERVAL_SECONDS = 10 * 60
LOG_ROTATE_BYTES = 2 * 1024 * 1024
MATTER_ADDON = "core_matter_server"
UNAVAILABLE_STATES = frozenset({"unavailable", "unknown", "none", ""})
MATTER_LIGHT_ENTITY_IDS = (
	"light.kajplats_e14_ws_globe_806lm",
	"light.loft_desk_kajplats",
	"light.kajplats_e14_ws_globe_806lm_2",
)
SYSCTL_ASSIGNMENTS = (
	"net.ipv6.conf.all.forwarding=1",
	"net.ipv6.conf.default.forwarding=1",
	"net.ipv6.conf.end0.accept_ra=2",
	"net.ipv6.conf.end0.accept_ra_rt_info_max_plen=64",
)
NEIGHBOR_ROLES = frozenset({"R", "C"})
# Absolute paths: cron's PATH is /usr/bin:/bin, so a bare "sysctl"
# (/usr/sbin) raised FileNotFoundError on every run from 2026-09-20 until
# 2026-10-05 and the watchdog never got past its first step.
SYSCTL = "/usr/sbin/sysctl"
DOCKER = "/usr/bin/docker"
# Local Matter controller on this Pi (matter_local.sh). When its container
# exists, the HA add-on is stopped and must stay stopped: restarting it
# would put a second controller on the same fabric.
LOCAL_MATTER_CONTAINER = "matterjs-server"
HA_RECOVERED_REASON = "HA link recovered after an outage"


def log(msg: str) -> None:
	rotate_log_if_needed()
	line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
	print(line)
	with LOG_FILE.open("a") as f:
		f.write(line + "\n")


def rotate_log_if_needed(path: Path = LOG_FILE, limit: int = LOG_ROTATE_BYTES) -> None:
	try:
		if path.exists() and path.stat().st_size > limit:
			backup = path.with_suffix(path.suffix + ".old")
			backup.unlink(missing_ok=True)
			path.replace(backup)
	except OSError:
		pass


def file_age_seconds(path: Path, now: float | None = None) -> float:
	if not path.exists():
		return float("inf")
	try:
		return (now if now is not None else time.time()) - float(path.read_text().strip())
	except (ValueError, OSError):
		return float("inf")


def cooldown_elapsed(path: Path, min_interval: float, now: float | None = None) -> bool:
	return file_age_seconds(path, now) >= min_interval


def record_timestamp(path: Path, now: float | None = None) -> None:
	path.write_text(str(now if now is not None else time.time()))


def ha_was_unreachable(path: Path = HA_REACHABLE_FILE) -> bool:
	try:
		return path.read_text().strip() in {"0", "false", "down"}
	except OSError:
		return False


def write_ha_reachable(reachable: bool, path: Path = HA_REACHABLE_FILE) -> None:
	path.write_text("1" if reachable else "0")


def neighbor_count(table: str) -> int:
	count = 0
	for line in table.splitlines():
		stripped = line.strip()
		if not stripped.startswith("|") or stripped.startswith("| Role") or stripped.startswith("|---"):
			continue
		parts = [p.strip() for p in stripped.split("|")]
		if len(parts) > 2 and parts[1] in NEIGHBOR_ROLES:
			count += 1
	return count


def matter_controller_stuck(
	states: dict[str, str],
	expected_ids: tuple[str, ...] = MATTER_LIGHT_ENTITY_IDS,
) -> bool:
	if not expected_ids:
		return False
	if not states:
		return False
	return all(states.get(entity_id, "unavailable") in UNAVAILABLE_STATES for entity_id in expected_ids)


def matter_kick_reason(
	*,
	ha_recovered: bool,
	controller_stuck: bool,
	mesh_up: bool,
) -> str | None:
	if ha_recovered:
		return "HA link recovered after an outage"
	if controller_stuck and mesh_up:
		return "Matter nodes unavailable while Thread mesh is up"
	return None


def last_restart_age() -> float:
	return file_age_seconds(STATE_FILE)


def record_restart() -> None:
	record_timestamp(STATE_FILE)


def ensure_sysctl() -> None:
	for assignment in SYSCTL_ASSIGNMENTS:
		result = subprocess.run(
			[SYSCTL, "-w", assignment],
			capture_output=True,
			text=True,
		)
		if result.returncode != 0:
			log(f"sysctl {assignment} failed: {result.stderr.strip() or result.stdout.strip()}")


def thread_mesh_has_neighbours() -> bool:
	result = subprocess.run(
		[DOCKER, "exec", "otbr", "ot-ctl", "neighbor", "table"],
		capture_output=True,
		text=True,
	)
	if result.returncode != 0:
		log(f"ot-ctl neighbor table failed: {result.stderr.strip() or result.stdout.strip()}")
		return False
	return neighbor_count(result.stdout) > 0


def _token() -> str:
	return TOKEN_FILE.read_text().strip()


def ha_rest(method: str, path: str, body: dict | None = None, timeout: int = 15) -> tuple[int, object]:
	url = f"{HA_REST_URL}{path}"
	data = None if body is None else json.dumps(body).encode()
	req = urllib.request.Request(
		url,
		data=data,
		method=method,
		headers={
			"Authorization": f"Bearer {_token()}",
			"Content-Type": "application/json",
		},
	)
	try:
		with urllib.request.urlopen(req, timeout=timeout) as resp:
			raw = resp.read()
			payload: object = json.loads(raw.decode()) if raw else None
			return resp.status, payload
	except urllib.error.HTTPError as exc:
		return exc.code, None


def matter_light_states(entity_ids: tuple[str, ...] = MATTER_LIGHT_ENTITY_IDS) -> dict[str, str]:
	states: dict[str, str] = {}
	for entity_id in entity_ids:
		status, payload = ha_rest("GET", f"/api/states/{entity_id}")
		if status == 200 and isinstance(payload, dict):
			states[entity_id] = str(payload.get("state", "unavailable"))
		else:
			states[entity_id] = "unavailable"
	return states


def restart_matter_addon(reason: str) -> None:
	log(f"Restarting Matter Server add-on ({MATTER_ADDON}): {reason}")
	status, payload = ha_rest(
		"POST",
		"/api/services/hassio/addon_restart",
		{"addon": MATTER_ADDON},
		timeout=60,
	)
	log(f"Matter add-on restart HTTP {status} payload={payload!r}")
	if status in {200, 201}:
		record_timestamp(MATTER_RESTART_FILE)


async def check_border_router_visible() -> bool:
	import websockets

	token = _token()
	async with websockets.connect(HA_WS_URL, open_timeout=10) as ws:
		msg = json.loads(await ws.recv())
		if msg.get("type") != "auth_required":
			raise RuntimeError(f"unexpected first message: {msg}")

		await ws.send(json.dumps({"type": "auth", "access_token": token}))
		msg = json.loads(await ws.recv())
		if msg.get("type") != "auth_ok":
			raise RuntimeError(f"auth failed: {msg}")

		await ws.send(json.dumps({"id": 1, "type": "thread/discover_routers"}))

		found = False
		subscribed = False
		deadline = time.monotonic() + DISCOVER_WINDOW_SECONDS
		while time.monotonic() < deadline:
			remaining = deadline - time.monotonic()
			try:
				raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
			except asyncio.TimeoutError:
				break
			msg = json.loads(raw)
			if msg.get("id") != 1:
				continue
			if msg.get("type") == "result":
				if not msg.get("success"):
					raise RuntimeError(f"subscribe failed: {msg}")
				subscribed = True
			elif msg.get("type") == "event":
				data = msg.get("event", {})
				if data.get("type") == "router_discovered":
					found = True
					event_data = data.get("data") or {}
					addresses = event_data.get("addresses") or []
					name = event_data.get("instance_name") or event_data.get("network_name") or "border router"
					log(f"router_discovered {name} addresses={addresses}")

		if not subscribed and not found:
			raise RuntimeError("never received a result ack or a discovery event")
		return found


def restart_otbr() -> None:
	log("Restarting otbr container...")
	result = subprocess.run(
		[DOCKER, "compose", "restart", "otbr"],
		cwd="/root/otbr",
		capture_output=True,
		text=True,
	)
	log(f"restart exit={result.returncode} stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}")


def local_matter_present() -> bool:
	result = subprocess.run(
		[DOCKER, "ps", "-a", "--filter", f"name=^{LOCAL_MATTER_CONTAINER}$", "--format", "{{.Names}}"],
		capture_output=True,
		text=True,
	)
	return result.returncode == 0 and result.stdout.strip() == LOCAL_MATTER_CONTAINER


def matter_action(reason: str, local: bool) -> str | None:
	"""What to restart for a Matter kick: "local", "addon" or nothing.

	With the controller on this Pi, Matter subscriptions no longer cross the
	VPN and HA reconnects its WebSocket by itself, so an HA link outage is
	no reason to drop every device. Never "addon" while local: that would
	start a second controller on the same fabric.
	"""
	if local:
		return None if reason == HA_RECOVERED_REASON else "local"
	return "addon"


def restart_local_matter(reason: str) -> None:
	log(f"Restarting local Matter server ({LOCAL_MATTER_CONTAINER}): {reason}")
	result = subprocess.run(
		[DOCKER, "restart", LOCAL_MATTER_CONTAINER],
		capture_output=True,
		text=True,
		timeout=120,
	)
	log(f"local Matter restart exit={result.returncode} stderr={result.stderr.strip()!r}")
	if result.returncode == 0:
		record_timestamp(MATTER_RESTART_FILE)


def maybe_restart_matter(reason: str) -> None:
	action = matter_action(reason, local_matter_present())
	if action is None:
		log(f"Matter kick not needed with the local server ({reason}).")
		return
	if not cooldown_elapsed(MATTER_RESTART_FILE, MIN_RESTART_INTERVAL_SECONDS):
		age = file_age_seconds(MATTER_RESTART_FILE)
		log(f"Matter restart skipped ({reason}); last restart was {age:.0f}s ago.")
		return
	if action == "local":
		restart_local_matter(reason)
	else:
		restart_matter_addon(reason)


def main() -> int:
	ensure_sysctl()
	try:
		visible = asyncio.run(check_border_router_visible())
	except Exception as exc:  # noqa: BLE001 - want to log and exit cleanly either way
		write_ha_reachable(False)
		log(f"Check failed with error (not restarting, avoid flapping on transient HA issues): {exc!r}")
		return 1

	recovered = ha_was_unreachable()
	write_ha_reachable(True)
	if recovered:
		maybe_restart_matter(HA_RECOVERED_REASON)

	if not visible:
		log("Border router NOT visible in HA (no router_discovered event in window).")
		age = last_restart_age()
		if age < MIN_RESTART_INTERVAL_SECONDS:
			log(f"Last OTBR restart was {age:.0f}s ago (< {MIN_RESTART_INTERVAL_SECONDS}s cooldown) - skipping to avoid flapping.")
			return 0
		restart_otbr()
		record_restart()
		return 0

	log("Border router visible in HA. No OTBR action.")
	if recovered:
		return 0

	try:
		states = matter_light_states()
	except Exception as exc:  # noqa: BLE001
		log(f"Matter state check failed (not restarting add-on): {exc!r}")
		return 0

	reason = matter_kick_reason(
		ha_recovered=False,
		controller_stuck=matter_controller_stuck(states),
		mesh_up=thread_mesh_has_neighbours(),
	)
	if reason:
		log(f"Matter lights={states}")
		maybe_restart_matter(reason)
	return 0


if __name__ == "__main__":
	sys.exit(main())
