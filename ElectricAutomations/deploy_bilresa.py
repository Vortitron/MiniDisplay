#!/usr/bin/env python3
"""Deploy the BILRESA button automations via VomeHome.

  python3 ElectricAutomations/deploy_bilresa.py            # all of them
  python3 ElectricAutomations/deploy_bilresa.py Bio Quiet  # names containing these

Each Bilresa*.yaml is one automation, deployed under its own `id`. Run the
tests first: python3 ElectricAutomations/tests/test_bilresa_buttons.py
"""

from __future__ import annotations

import sys

import yaml

from deploy_feed_restore import ROOT, deploy_automation, load_broker


def main() -> None:
	wanted = sys.argv[1:]
	files = sorted(ROOT.glob("Bilresa*.yaml"))
	if wanted:
		files = [f for f in files if any(w.lower() in f.name.lower() for w in wanted)]
	if not files:
		raise SystemExit("No matching Bilresa*.yaml files.")
	base, token = load_broker()
	for path in files:
		config = yaml.safe_load(path.read_text())
		deploy_automation(base, token, config["id"], config)
		print(f"  ✓ {config['id']}  ({path.name})")
	print(f"Done: {len(files)} BILRESA automation(s) deployed.")


if __name__ == "__main__":
	main()
