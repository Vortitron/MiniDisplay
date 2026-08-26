#!/usr/bin/env python3
"""Deploy dashboard_sam_energy.yaml via VomeHome /ws/command (Lovelace API).

  python3 ElectricAutomations/deploy_sam_energy_dashboard.py

Falls back to direct HA WebSocket if HA_TOKEN is set.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import socket
import ssl
import struct
import urllib.error
import urllib.request
from urllib.parse import urlparse

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
MCP = pathlib.Path.home() / ".cursor" / "mcp.json"
DASHBOARD_PATH = "sam-energy"
CONFIG_FILE = ROOT / "dashboard_sam_energy.yaml"


def load_dashboard_config() -> dict:
	return yaml.safe_load(CONFIG_FILE.read_text())


def load_vome_broker() -> tuple[str, str] | None:
	if not MCP.is_file():
		return None
	servers = json.loads(MCP.read_text()).get("mcpServers", {})
	cfg = servers.get("ha-gamlabio", servers.get("home-assistant", {})).get("env", {})
	token = cfg.get("VOMEHOME_TOKEN", "").strip()
	instance = cfg.get("VOMEHOME_INSTANCE_ID", "").strip()
	if not token or not instance:
		return None
	return f"https://vome.io/api/v1/instances/{instance}/ha", token


def ws_command(base: str, token: str, command: dict) -> object:
	"""Send a Lovelace WebSocket command through the VomeHome broker."""
	req = urllib.request.Request(
		f"{base}/ws/command",
		data=json.dumps(command).encode(),
		headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
		method="POST",
	)
	try:
		with urllib.request.urlopen(req, timeout=60) as resp:
			envelope = json.loads(resp.read().decode())
	except urllib.error.HTTPError as exc:
		body = exc.read().decode()
		raise RuntimeError(f"ws/command HTTP {exc.code}: {body[:500]}") from exc
	if isinstance(envelope, dict) and "result" in envelope:
		return envelope["result"]
	return envelope


def deploy_via_vome(config: dict) -> None:
	broker = load_vome_broker()
	if broker is None:
		raise RuntimeError("No VOMEHOME_TOKEN in ~/.cursor/mcp.json")
	base, token = broker
	print("VomeHome broker: listing dashboards…")
	try:
		dashboards = ws_command(base, token, {"type": "lovelace/dashboards/list"})
	except RuntimeError as exc:
		raise RuntimeError(
			f"{exc}\n\nThe broker exposes /ws/command but the relay returned an error.\n"
			"Check: GamlaBio Vome relay add-on is updated, and the API token has ha:config\n"
			"for instance rly-d157b3477ede."
		) from exc

	rows = dashboards if isinstance(dashboards, list) else []
	urls = {row.get("url_path") for row in rows if isinstance(row, dict)}
	print(f"  Found {len(rows)} dashboard(s): {sorted(urls)}")

	if DASHBOARD_PATH not in urls:
		print(f"  Creating dashboard '{DASHBOARD_PATH}'…")
		created = ws_command(
			base,
			token,
			{
				"type": "lovelace/dashboards/create",
				"url_path": DASHBOARD_PATH,
				"title": config.get("title", "Sam & Energy"),
				"mode": "storage",
				"show_in_sidebar": True,
				"require_admin": False,
				"icon": "mdi:home-lightning-bolt",
			},
		)
		print(f"  Created: {created}")

	print(f"  Saving config to '{DASHBOARD_PATH}' ({len(config.get('views', []))} views)…")
	ws_command(
		base,
		token,
		{"type": "lovelace/config/save", "url_path": DASHBOARD_PATH, "config": config},
	)
	print(f"Done: https://…/sam-energy/overview and /sam-energy/back-garden")


def ha_ws_url() -> str:
	base = os.environ.get("HA_URL", "").rstrip("/")
	if not base:
		ip = os.environ.get("HA_IP", "192.168.1.15")
		port = os.environ.get("HA_PORT", "8123")
		base = f"http://{ip}:{port}"
	return base.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"


def load_ha_token() -> str:
	token = os.environ.get("HA_TOKEN", "").strip()
	if token:
		return token
	for candidate in (
		pathlib.Path.home() / "energy-sensor-generator" / ".env",
		pathlib.Path.home() / ".homeassistant" / "token",
	):
		if not candidate.is_file():
			continue
		for line in candidate.read_text().splitlines():
			line = line.strip()
			if line.startswith("HA_TOKEN="):
				return line.split("=", 1)[1].strip()
			if candidate.name == "token" and line and not line.startswith("#"):
				return line
	raise SystemExit(
		"VomeHome relay failed and HA_TOKEN is not set for direct WebSocket deploy."
	)


class HaWebSocket:
	"""Minimal Home Assistant WebSocket client (stdlib only)."""

	def __init__(self, url: str, token: str) -> None:
		self._url = url
		self._token = token
		self._sock: socket.socket | ssl.SSLSocket | None = None
		self._buf = bytearray()
		self._msg_id = 0

	def __enter__(self) -> HaWebSocket:
		parsed = urlparse(self._url)
		host = parsed.hostname or "localhost"
		port = parsed.port or (443 if parsed.scheme == "wss" else 80)
		path = parsed.path or "/api/websocket"
		raw = socket.create_connection((host, port), timeout=20)
		if parsed.scheme == "wss":
			ctx = ssl.create_default_context()
			self._sock = ctx.wrap_socket(raw, server_hostname=host)
		else:
			self._sock = raw
		key = base64.b64encode(os.urandom(16)).decode()
		req = (
			f"GET {path} HTTP/1.1\r\n"
			f"Host: {host}\r\n"
			"Upgrade: websocket\r\n"
			"Connection: Upgrade\r\n"
			f"Sec-WebSocket-Key: {key}\r\n"
			"Sec-WebSocket-Version: 13\r\n"
			"\r\n"
		)
		assert self._sock is not None
		self._sock.sendall(req.encode())
		response = b""
		while b"\r\n\r\n" not in response:
			chunk = self._sock.recv(4096)
			if not chunk:
				raise RuntimeError("WebSocket handshake failed")
			response += chunk
		if b" 101 " not in response.split(b"\r\n", 1)[0]:
			raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")
		# Keep any WebSocket bytes that arrived with the HTTP response.
		_, _, leftover = response.partition(b"\r\n\r\n")
		self._buf.extend(leftover)

		auth_required = json.loads(self._recv_text())
		assert auth_required["type"] == "auth_required"
		self._send_json({"type": "auth", "access_token": self._token})
		auth_ok = json.loads(self._recv_text())
		if auth_ok.get("type") != "auth_ok":
			raise RuntimeError(f"HA auth failed: {auth_ok}")
		return self

	def __exit__(self, *_args: object) -> None:
		if self._sock is not None:
			self._sock.close()
			self._sock = None

	def _recv_exact(self, size: int) -> bytes:
		assert self._sock is not None
		while len(self._buf) < size:
			chunk = self._sock.recv(max(4096, size - len(self._buf)))
			if not chunk:
				raise RuntimeError("WebSocket connection closed")
			self._buf.extend(chunk)
		out = bytes(self._buf[:size])
		del self._buf[:size]
		return out

	def _recv_text(self) -> str:
		payload_parts: list[bytes] = []
		while True:
			header = self._recv_exact(2)
			opcode = header[0] & 0x0F
			fin = bool(header[0] & 0x80)
			length = header[1] & 0x7F
			if length == 126:
				length = struct.unpack("!H", self._recv_exact(2))[0]
			elif length == 127:
				length = struct.unpack("!Q", self._recv_exact(8))[0]
			masked = bool(header[1] & 0x80)
			mask = self._recv_exact(4) if masked else b""
			payload = self._recv_exact(length)
			if masked:
				payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
			if opcode == 0x8:
				raise RuntimeError("WebSocket closed by peer")
			if opcode == 0x9:
				# Ping — ignore (HA rarely sends these during short scripts).
				continue
			if opcode in (0x1, 0x0):
				payload_parts.append(payload)
				if fin:
					return b"".join(payload_parts).decode()
			else:
				# Skip unexpected control/binary frames.
				if fin and not payload_parts:
					continue
				raise RuntimeError(f"Unexpected WebSocket opcode {opcode}")

	def _send_json(self, payload: dict) -> None:
		assert self._sock is not None
		data = json.dumps(payload).encode()
		frame = bytearray([0x81])
		mask_bit = 0x80
		if len(data) < 126:
			frame.append(mask_bit | len(data))
		elif len(data) < 65536:
			frame.append(mask_bit | 126)
			frame.extend(struct.pack("!H", len(data)))
		else:
			frame.append(mask_bit | 127)
			frame.extend(struct.pack("!Q", len(data)))
		mask = os.urandom(4)
		frame.extend(mask)
		frame.extend(bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
		self._sock.sendall(frame)

	def call(self, msg_type: str, **kwargs: object) -> dict:
		self._msg_id += 1
		msg_id = self._msg_id
		self._send_json({"id": msg_id, "type": msg_type, **kwargs})
		while True:
			data = json.loads(self._recv_text())
			if data.get("id") == msg_id:
				if data.get("type") == "result" and data.get("success") is False:
					raise RuntimeError(f"{msg_type} failed: {data}")
				if data.get("type") == "result" and "error" in data:
					raise RuntimeError(f"{msg_type} failed: {data['error']}")
				return data


def deploy_via_websocket(config: dict) -> None:
	url = ha_ws_url()
	token = load_ha_token()
	print(f"Direct HA WebSocket: {url}")
	with HaWebSocket(url, token) as ws:
		dashboards = ws.call("lovelace/dashboards/list")
		rows = dashboards.get("result", [])
		urls = {row.get("url_path") for row in rows if isinstance(row, dict)}
		print(f"  Found {len(rows)} dashboard(s)")
		if DASHBOARD_PATH not in urls:
			try:
				ws.call(
					"lovelace/dashboards/create",
					url_path=DASHBOARD_PATH,
					title=config.get("title", "Sam & Energy"),
					icon="mdi:home-lightning-bolt",
					show_in_sidebar=True,
					require_admin=False,
				)
				print(f"  Created dashboard '{DASHBOARD_PATH}'")
			except RuntimeError as exc:
				if "already exists" not in str(exc).lower():
					print(f"  Note: create skipped ({exc})")
		ws.call("lovelace/config/save", url_path=DASHBOARD_PATH, config=config)
	print(f"Dashboard saved at /{DASHBOARD_PATH}/overview and /{DASHBOARD_PATH}/back-garden")


def main() -> None:
	config = load_dashboard_config()
	try:
		deploy_via_vome(config)
	except RuntimeError as exc:
		print(exc)
		print("\nFalling back to direct LAN WebSocket…")
		try:
			deploy_via_websocket(config)
		except SystemExit:
			raise
		except OSError as lan_exc:
			raise SystemExit(
				f"Direct deploy also failed ({lan_exc}). "
				"Set HA_URL and HA_TOKEN, or fix the Vome relay Lovelace proxy."
			) from lan_exc


if __name__ == "__main__":
	main()
