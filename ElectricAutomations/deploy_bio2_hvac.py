#!/usr/bin/env python3
"""Deploy the Bio2 HVAC automation and the bio thermal model via VomeHome.

  python3 ElectricAutomations/deploy_bio2_hvac.py

Bio2Hvac.yaml drives climate.bio2 (the bio hall heat pump) from the wall
sensor there; see README_Bio2HVAC.md. Its five helpers are STORAGE helpers
created over MCP (ha_set_helper), so no restart is needed. sam.yaml and
BioProjectorLights.yaml were changed alongside it (Sam stands aside while
Bio2 is live) — deploy those with deploy_sam_heating.py and ha_set_automation.
Run the tests first: python3 ElectricAutomations/tests/test_bio2_hvac_templates.py
"""

from __future__ import annotations

import yaml

from deploy_feed_restore import ROOT, deploy_automation, load_broker


FILES = ("Bio2Hvac.yaml", "BioThermalModel.yaml")


def main() -> None:
	base, token = load_broker()
	for name in FILES:
		path = ROOT / name
		config = yaml.safe_load(path.read_text())
		deploy_automation(base, token, config["id"], config)
		print(f"  ✓ {config['id']}  ({path.name})")
	print("Done. Watch input_text.bio2_hvac_headline / bio2_preheat_calc and bio_thermal_status.")


if __name__ == "__main__":
	main()
