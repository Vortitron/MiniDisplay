#!/usr/bin/env python3
"""
Thread border router watchdog.

Checks whether Home Assistant currently sees the border router via the
Thread panel's live discovery mechanism (thread/discover_routers websocket
subscription), and only restarts the local otbr container if it genuinely
doesn't -- avoids blind periodic restarts and their brief Thread-mesh blip.

Known upstream issue this works around: https://github.com/home-assistant/core/issues/110152

Token is read from TOKEN_FILE on the Pi; do not commit ha_token.txt.
"""
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

HA_WS_URL = "ws://192.168.1.15:8123/api/websocket"
TOKEN_FILE = Path("/root/otbr/watchdog/ha_token.txt")
STATE_FILE = Path("/root/otbr/watchdog/last_restart.txt")
LOG_FILE = Path("/root/otbr/watchdog/watchdog.log")
DISCOVER_WINDOW_SECONDS = 8
MIN_RESTART_INTERVAL_SECONDS = 10 * 60  # don't restart more than once per 10 min

import websockets


def log(msg: str) -> None:
	line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
	print(line)
	with LOG_FILE.open("a") as f:
		f.write(line + "\n")


def last_restart_age() -> float:
	if not STATE_FILE.exists():
		return float("inf")
	try:
		return time.time() - float(STATE_FILE.read_text().strip())
	except (ValueError, OSError):
		return float("inf")


def record_restart() -> None:
	STATE_FILE.write_text(str(time.time()))


async def check_border_router_visible() -> bool:
	token = TOKEN_FILE.read_text().strip()
	async with websockets.connect(HA_WS_URL, open_timeout=10) as ws:
		msg = json.loads(await ws.recv())
		if msg.get("type") != "auth_required":
			raise RuntimeError(f"unexpected first message: {msg}")

		await ws.send(json.dumps({"type": "auth", "access_token": token}))
		msg = json.loads(await ws.recv())
		if msg.get("type") != "auth_ok":
			raise RuntimeError(f"auth failed: {msg}")

		await ws.send(json.dumps({"id": 1, "type": "thread/discover_routers"}))

		# The "result" ack and "router_discovered" events for already-known
		# routers can arrive in either order (observed: event before result),
		# so just read everything in the window and react per-message.
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
					log(f"router_discovered event: {data}")

		if not subscribed and not found:
			raise RuntimeError("never received a result ack or a discovery event")
		return found


def restart_otbr() -> None:
	log("Restarting otbr container...")
	result = subprocess.run(
		["docker", "compose", "restart", "otbr"],
		cwd="/root/otbr",
		capture_output=True,
		text=True,
	)
	log(f"restart exit={result.returncode} stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}")


def main() -> int:
	try:
		visible = asyncio.run(check_border_router_visible())
	except Exception as exc:  # noqa: BLE001 - want to log and exit cleanly either way
		log(f"Check failed with error (not restarting, avoid flapping on transient HA issues): {exc!r}")
		return 1

	if visible:
		log("Border router visible in HA. No action.")
		return 0

	log("Border router NOT visible in HA (no router_discovered event in window).")
	age = last_restart_age()
	if age < MIN_RESTART_INTERVAL_SECONDS:
		log(f"Last restart was {age:.0f}s ago (< {MIN_RESTART_INTERVAL_SECONDS}s cooldown) - skipping to avoid flapping.")
		return 0

	restart_otbr()
	record_restart()
	return 0


if __name__ == "__main__":
	sys.exit(main())
