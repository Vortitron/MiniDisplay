#!/usr/bin/env python3
"""Deploy hot-water Home Assistant automations via the VomeHome broker.

Run from repo root:
  python3 ElectricAutomations/deploy_hot_water.py
  python3 ElectricAutomations/deploy_hot_water.py HotWaterUnavailable.yaml
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
MCP = pathlib.Path.home() / ".cursor" / "mcp.json"

# Existing HA UI automations keep their numeric ids; new ones use string ids.
AUTOMATIONS: tuple[tuple[str, str], ...] = (
	("1764750330659", "HotWater.yaml"),
	("1762527503683", "HotWaterTemperature.yaml"),
	("1777915315860", "HotWaterReheatTracker.yaml"),
	("1777983905344", "HotWaterBoost.yaml"),
	("hot_water_plug_unavailable", "HotWaterUnavailable.yaml"),
)


def load_broker() -> tuple[str, str]:
	servers = json.loads(MCP.read_text()).get("mcpServers", {})
	cfg = servers.get("ha-gamlabio", servers.get("home-assistant", {})).get("env", {})
	return (
		f"https://vome.io/api/v1/instances/{cfg['VOMEHOME_INSTANCE_ID']}/ha",
		cfg["VOMEHOME_TOKEN"],
	)


def broker_post(base: str, token: str, path: str, body: object) -> tuple[int, str]:
	data = json.dumps(body).encode()
	req = urllib.request.Request(
		f"{base}{path}",
		data=data,
		headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
		method="POST",
	)
	try:
		with urllib.request.urlopen(req, timeout=60) as resp:
			return resp.status, resp.read().decode()
	except urllib.error.HTTPError as exc:
		return exc.code, exc.read().decode()


def load_automation_yaml(name: str) -> dict:
	with (ROOT / name).open() as fh:
		return yaml.safe_load(fh)


def deploy_automation(base: str, token: str, automation_id: str, config: dict) -> None:
	cfg = dict(config)
	cfg.pop("id", None)
	code, body = broker_post(base, token, f"/config/automation/config/{automation_id}", cfg)
	if code >= 400:
		raise RuntimeError(f"automation {automation_id} failed HTTP {code}: {body[:500]}")


def main() -> None:
	wanted = {pathlib.Path(a).name for a in sys.argv[1:]} or None
	base, token = load_broker()
	print("Deploying hot-water automations…")
	for automation_id, yaml_name in AUTOMATIONS:
		if wanted is not None and yaml_name not in wanted:
			continue
		deploy_automation(base, token, automation_id, load_automation_yaml(yaml_name))
		print(f"  ✓ {automation_id} ({yaml_name})")
	print("Done.")


if __name__ == "__main__":
	main()
