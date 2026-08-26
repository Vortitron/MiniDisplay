#!/usr/bin/env python3
"""Publish pool-pump MQTT entities and deploy automations via the VomeHome HA broker.

Run from repo root:
  python3 ElectricAutomations/deploy_pool_pump.py
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
MCP = pathlib.Path.home() / ".cursor" / "mcp.json"

POOL_DEVICE = {
	"identifiers": ["minidisplay_pool_pump"],
	"name": "Pool Pump",
	"manufacturer": "MiniDisplay",
	"model": "Pool Automation",
	"suggested_area": "Back Garden",
}

SELECT_OPTIONS = ["off", "cheap", "maintenance", "extended", "one_hour"]


def load_broker() -> tuple[str, str]:
	servers = json.loads(MCP.read_text()).get("mcpServers", {})
	cfg = servers.get("ha-gamlabio", servers.get("home-assistant", {})).get("env", {})
	return (
		f"https://vome.io/api/v1/instances/{cfg['VOMEHOME_INSTANCE_ID']}/ha",
		cfg["VOMEHOME_TOKEN"],
	)


def broker_post(base: str, token: str, path: str, body: object | None = None, method: str = "POST") -> tuple[int, str]:
	url = f"{base}{path}"
	data = None if body is None else json.dumps(body).encode()
	req = urllib.request.Request(
		url,
		data=data,
		headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
		method=method,
	)
	try:
		with urllib.request.urlopen(req, timeout=30) as resp:
			return resp.status, resp.read().decode()
	except urllib.error.HTTPError as exc:
		return exc.code, exc.read().decode()


def mqtt_publish(base: str, token: str, topic: str, payload: str, retain: bool = True) -> None:
	code, body = broker_post(
		base,
		token,
		"/services/mqtt/publish",
		{"topic": topic, "payload": payload, "retain": retain},
	)
	if code >= 400:
		raise RuntimeError(f"mqtt.publish {topic} failed HTTP {code}: {body[:300]}")


def deploy_automation(base: str, token: str, automation_id: str, config: dict) -> None:
	cfg = dict(config)
	cfg.pop("id", None)
	code, body = broker_post(base, token, f"/config/automation/config/{automation_id}", cfg)
	if code >= 400:
		raise RuntimeError(f"automation {automation_id} failed HTTP {code}: {body[:500]}")


def publish_pool_entities(base: str, token: str) -> None:
	for component, object_id in (
		("number", "pool_pump_turnover_minutes"),
		("number", "pool_cheap_rank_max"),
		("number", "pool_pump_extended_hours"),
		("select", "pool_pump_mode"),
		("datetime", "pool_pump_plan_until"),
		("text", "pool_pump_status"),
		("button", "pool_pump_schedule_cheap"),
		("button", "pool_pump_run_extended"),
		("button", "pool_pump_stop"),
		("button", "pool_pump_pool_cheap_windows"),
		("button", "pool_pump_pool_extended_run"),
		("button", "pool_pump_pool_stop"),
		("button", "pool_one_hour"),
		("button", "pool_pump_run_1_hour"),
	):
		mqtt_publish(base, token, f"homeassistant/{component}/{object_id}/config", "")

	def pub(component: str, object_id: str, config: dict) -> None:
		cfg = {"object_id": object_id, "device": POOL_DEVICE, **config}
		mqtt_publish(base, token, f"homeassistant/{component}/{object_id}/config", json.dumps(cfg))

	pub(
		"number",
		"pool_pump_minutes_remaining",
		{
			"name": "Minutes Remaining",
			"unique_id": "pool_pump_minutes_remaining",
			"state_topic": "pool/pump/mins/state",
			"command_topic": "pool/pump/mins/set",
			"optimistic": True,
			"unit_of_measurement": "min",
			"min": 0,
			"max": 360,
			"step": 15,
			"icon": "mdi:timer-sand",
		},
	)
	pub(
		"number",
		"pool_pump_daily_on_minutes",
		{
			"name": "Daily ON Minutes",
			"unique_id": "pool_pump_daily_on_minutes",
			"state_topic": "pool/pump/daily_on/state",
			"command_topic": "pool/pump/daily_on/set",
			"optimistic": True,
			"unit_of_measurement": "min",
			"min": 0,
			"max": 480,
			"step": 15,
			"icon": "mdi:chart-timeline-variant",
		},
	)
	pub(
		"number",
		"pool_pump_maintenance_daily_target",
		{
			"name": "Maintenance Daily Target",
			"unique_id": "pool_pump_maintenance_daily_minutes",
			"state_topic": "pool/pump/maintenance_target/state",
			"command_topic": "pool/pump/maintenance_target/set",
			"optimistic": True,
			"unit_of_measurement": "min",
			"min": 60,
			"max": 360,
			"step": 15,
			"icon": "mdi:pool",
		},
	)
	pub(
		"number",
		"pool_pump_cheap_cutoff_hour",
		{
			"name": "Cheap Cutoff Hour",
			"unique_id": "pool_pump_cheap_cutoff_hour",
			"state_topic": "pool/pump/cheap_cutoff/state",
			"command_topic": "pool/pump/cheap_cutoff/set",
			"optimistic": True,
			"min": 0,
			"max": 23,
			"step": 1,
			"icon": "mdi:clock-alert",
		},
	)
	pub(
		"number",
		"pool_pump_pool_pump_turnover_minutes",
		{
			"name": "Turnover Minutes",
			"unique_id": "pool_pump_turnover_minutes",
			"state_topic": "pool/pump/turnover/state",
			"command_topic": "pool/pump/turnover/set",
			"optimistic": True,
			"unit_of_measurement": "min",
			"min": 60,
			"max": 360,
			"step": 15,
			"icon": "mdi:pool",
		},
	)
	pub(
		"number",
		"pool_pump_pool_cheap_rank_max",
		{
			"name": "Cheap Rank Max",
			"unique_id": "pool_cheap_rank_max",
			"state_topic": "pool/pump/cheap_rank_max/state",
			"command_topic": "pool/pump/cheap_rank_max/set",
			"optimistic": True,
			"min": 0,
			"max": 23,
			"step": 1,
			"icon": "mdi:cash-clock",
		},
	)
	pub(
		"number",
		"pool_pump_pool_pump_extended_hours",
		{
			"name": "Extended Hours",
			"unique_id": "pool_pump_extended_hours",
			"state_topic": "pool/pump/extended_hours/state",
			"command_topic": "pool/pump/extended_hours/set",
			"optimistic": True,
			"unit_of_measurement": "h",
			"min": 1,
			"max": 12,
			"step": 1,
			"icon": "mdi:clock-outline",
		},
	)
	pub(
		"select",
		"pool_pump_pool_pump_plan",
		{
			"name": "Plan",
			"unique_id": "pool_pump_mode",
			"state_topic": "pool/pump/mode/state",
			"command_topic": "pool/pump/mode/set",
			"optimistic": True,
			"options": SELECT_OPTIONS,
			"icon": "mdi:pool",
		},
	)
	pub(
		"datetime",
		"pool_pump_pool_pump_plan_until",
		{
			"name": "Plan Until",
			"unique_id": "pool_pump_plan_until",
			"state_topic": "pool/pump/plan_until/state",
			"command_topic": "pool/pump/plan_until/set",
			"optimistic": True,
			"icon": "mdi:clock-outline",
		},
	)
	pub(
		"text",
		"pool_pump_pool_pump_status",
		{
			"name": "Status",
			"unique_id": "pool_pump_status",
			"state_topic": "pool/pump/status/state",
			"command_topic": "pool/pump/status/set",
			"optimistic": True,
			"max": 255,
			"icon": "mdi:pool",
		},
	)
	for object_id, name, icon in (
		("pool_cheap_windows", "Cheap Windows (6 h)", "mdi:cash-clock"),
		("pool_extended_run", "Extended Run (6 h)", "mdi:pool"),
		("pool_pump_run_1_hour", "Run 1 Hour", "mdi:timer"),
		("pool_stop", "Stop", "mdi:stop-circle"),
	):
		pub(
			"button",
			object_id,
			{
				"name": name,
				"unique_id": object_id,
				"command_topic": f"pool/pump/btn/{object_id}",
				"payload_press": "pressed",
				"icon": icon,
			},
		)

	for topic, value in (
		("pool/pump/mins/state", "0"),
		("pool/pump/daily_on/state", "0"),
		("pool/pump/maintenance_target/state", "180"),
		("pool/pump/cheap_cutoff/state", "0"),
		("pool/pump/turnover/state", "180"),
		("pool/pump/cheap_rank_max/state", "5"),
		("pool/pump/extended_hours/state", "6"),
		("pool/pump/mode/state", "off"),
		("pool/pump/status/state", "Idle"),
	):
		mqtt_publish(base, token, topic, value)


def load_automation_yaml(name: str) -> dict:
	with (ROOT / name).open() as fh:
		return yaml.safe_load(fh)


def main() -> None:
	base, token = load_broker()
	print("Publishing MQTT pool entities…")
	publish_pool_entities(base, token)
	print("Deploying automations…")
	for automation_id, yaml_name in (
		("pool_pump_price_scheduler", "PoolPump.yaml"),
		("pool_pump_arm_plan", "PoolPumpButtons.yaml"),
		("pool_pump_daily_maintenance", "PoolPumpMaintenance.yaml"),
		("pool_pump_manual_on", "PoolPumpManual.yaml"),
		("super_expensive_load_shedding", "SuperExpensive.yaml"),
	):
		deploy_automation(base, token, automation_id, load_automation_yaml(yaml_name))
		print(f"  ✓ {automation_id}")
	print("Done: pool MQTT entities + automations deployed.")


if __name__ == "__main__":
	main()
