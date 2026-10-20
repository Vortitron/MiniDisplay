#!/usr/bin/env python3
"""Deploy the Bio2 HVAC automation (Bio2Hvac.yaml) via VomeHome.

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


def main() -> None:
	path = ROOT / "Bio2Hvac.yaml"
	config = yaml.safe_load(path.read_text())
	base, token = load_broker()
	deploy_automation(base, token, config["id"], config)
	print(f"  ✓ {config['id']}  ({path.name})")
	print("Done. Watch input_text.bio2_hvac_headline for the first evaluation.")


if __name__ == "__main__":
	main()
