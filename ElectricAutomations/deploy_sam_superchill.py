#!/usr/bin/env python3
"""Deploy Sam Superchill automations (and refresh Sam HVAC) via VomeHome.

Helpers (input_button / input_datetime) are created once via the HA WebSocket
API — see README_SamHVAC.md. This script only deploys the automations.

  python3 ElectricAutomations/deploy_sam_superchill.py
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
MCP = pathlib.Path.home() / ".cursor" / "mcp.json"


def load_broker() -> tuple[str, str]:
	servers = json.loads(MCP.read_text()).get("mcpServers", {})
	cfg = servers.get("ha-gamlabio", servers.get("home-assistant", {})).get("env", {})
	token = cfg.get("VOMEHOME_TOKEN", "").strip()
	instance = cfg.get("VOMEHOME_INSTANCE_ID", "").strip()
	if not token or not instance:
		raise SystemExit("Missing VOMEHOME_TOKEN / VOMEHOME_INSTANCE_ID in ~/.cursor/mcp.json")
	return f"https://vome.io/api/v1/instances/{instance}/ha", token


def broker_post(base: str, token: str, path: str, body: object) -> tuple[int, str]:
	req = urllib.request.Request(
		f"{base}{path}",
		data=json.dumps(body).encode(),
		headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
		method="POST",
	)
	try:
		with urllib.request.urlopen(req, timeout=60) as resp:
			return resp.status, resp.read().decode()
	except urllib.error.HTTPError as exc:
		return exc.code, exc.read().decode()


def deploy_automation(base: str, token: str, automation_id: str, config: dict) -> None:
	cfg = dict(config)
	cfg.pop("id", None)
	code, body = broker_post(base, token, f"/config/automation/config/{automation_id}", cfg)
	if code >= 400:
		raise RuntimeError(f"automation {automation_id} failed HTTP {code}: {body[:500]}")


def main() -> None:
	base, token = load_broker()
	for automation_id, yaml_name in (
		("sync_sam_hvac_with_desired_temperature", "sam.yaml"),
		("sam_superchill_2h", "SamSuperchill.yaml"),
	):
		config = yaml.safe_load((ROOT / yaml_name).read_text())
		deploy_automation(base, token, automation_id, config)
		print(f"  ✓ {automation_id}")
	print("Done: Sam HVAC + Superchill automations deployed.")
	print("Press input_button.sam_superchill_2h to blast-cool for 2 hours.")


if __name__ == "__main__":
	main()
