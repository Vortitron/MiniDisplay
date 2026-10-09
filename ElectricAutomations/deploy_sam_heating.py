#!/usr/bin/env python3
"""Deploy the Sam heating pair (sam.yaml + DaytimeCheapHeat.yaml) via VomeHome.

  python3 ElectricAutomations/deploy_sam_heating.py

These two automations are the two halves of the two-number system described in
README_SamHVAC.md — DaytimeCheapHeat writes sam_desired/sam_control, sam.yaml
drives climate.sam from them — so they are deployed together to keep the
control ladder and the consumer of it in step.

Note: helpers.yaml and forecast_sensors.yaml are NOT deployed by this script.
They are `!include`d packages and need a Home Assistant restart to take effect
(see "Home Assistant wiring" in README_SamHVAC.md).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
MCP = pathlib.Path.home() / ".cursor" / "mcp.json"
PROJECT_MCP = ROOT.parent / ".mcp.json"
# GamlaBio Hosted — the live house since Sep 2026. The older "GamlaBio" relay
# instance (rly-568e6d697864) is retired; deploying there is a silent no-op as
# far as the real house is concerned. Override with VOMEHOME_INSTANCE_ID.
DEFAULT_INSTANCE = "3d80386f-279a-4388-accb-5d8dd9d1ac71"

AUTOMATIONS = (
	("sync_sam_hvac_with_desired_temperature", "sam.yaml"),
	("1744362298178", "DaytimeCheapHeat.yaml"),
)


def _loads_lenient(text: str) -> dict:
	"""Parse mcp.json, tolerating the trailing commas editors leave behind."""
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))


def load_broker() -> tuple[str, str]:
	"""Find the VomeHome token and instance for the REST broker.

	The MCP config used to carry VOMEHOME_TOKEN / VOMEHOME_INSTANCE_ID in a
	stdio server's `env`. It is now an HTTP server with the token in an
	Authorization header and no instance id at all (the active instance is
	chosen server-side), so the id comes from VOMEHOME_INSTANCE_ID or the
	default below. Project config wins over the user-level one.
	"""
	token = ""
	for path in (PROJECT_MCP, MCP):
		if not path.exists():
			continue
		servers = _loads_lenient(path.read_text()).get("mcpServers", {})
		for name in ("vome", "ha-gamlabio", "home-assistant"):
			server = servers.get(name)
			if not server:
				continue
			env = server.get("env", {})
			token = env.get("VOMEHOME_TOKEN", "").strip()
			if not token:
				auth = server.get("headers", {}).get("Authorization", "")
				token = auth.removeprefix("Bearer ").strip()
			if token:
				break
		if token:
			break
	instance = os.environ.get("VOMEHOME_INSTANCE_ID", DEFAULT_INSTANCE).strip()
	if not token or not instance:
		raise SystemExit(
			"No VomeHome token found. Set VOMEHOME_TOKEN, or add the vome MCP "
			"server to ~/.cursor/mcp.json or the project .mcp.json."
		)
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
	for automation_id, yaml_name in AUTOMATIONS:
		config = yaml.safe_load((ROOT / yaml_name).read_text())
		deploy_automation(base, token, automation_id, config)
		print(f"  ✓ {automation_id} ({yaml_name})")
	print("Done: Sam heating automations deployed.")
	print("Check input_text.sam_preheat_calc for the new abs=/win= fields.")


if __name__ == "__main__":
	main()
