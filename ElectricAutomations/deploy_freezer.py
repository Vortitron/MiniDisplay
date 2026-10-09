#!/usr/bin/env python3
"""Deploy the freezer plug automations via VomeHome.

  python3 ElectricAutomations/deploy_freezer.py

Each Freezer*.yaml is one automation, deployed under its own `id`. The helpers
they use (binary_sensor.living_room_freezer_running, input_boolean.
freezer_maintenance, input_select.freezer_alert) are storage helpers created
live over MCP — see README_Freezer.md. Run the tests first:
python3 ElectricAutomations/tests/test_freezer_watch.py
"""

from __future__ import annotations

import yaml

from deploy_feed_restore import ROOT, deploy_automation, load_broker


def main() -> None:
	files = sorted(ROOT.glob("Freezer*.yaml"))
	if not files:
		raise SystemExit("No Freezer*.yaml files.")
	base, token = load_broker()
	for path in files:
		config = yaml.safe_load(path.read_text())
		deploy_automation(base, token, config["id"], config)
		print(f"  ✓ {config['id']}  ({path.name})")
	print(f"Done: {len(files)} freezer automation(s) deployed.")


if __name__ == "__main__":
	main()
