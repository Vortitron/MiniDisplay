#!/usr/bin/env python3
"""Run Alarm/update_minidisplay.py against a fake hass.

Home Assistant python_scripts cannot be imported (they expect hass and
logger in the sandbox). This loads the file and checks helper writes.

Run:  python3 Alarm/tests/test_update_minidisplay.py
"""

from __future__ import annotations

import pathlib
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "update_minidisplay.py"


class FakeLogger:
	def __init__(self):
		self.messages = []

	def _record(self, level, msg, *args):
		self.messages.append((level, msg % args if args else msg))

	def debug(self, msg, *args):
		self._record("debug", msg, *args)

	def info(self, msg, *args):
		self._record("info", msg, *args)

	def warning(self, msg, *args):
		self._record("warning", msg, *args)


class FakeState:
	def __init__(self, attributes):
		self.attributes = attributes


class FakeStates:
	def __init__(self, entities):
		self._entities = entities

	def get(self, entity_id):
		return self._entities.get(entity_id)


class FakeHass:
	def __init__(self, entities):
		self.states = FakeStates(entities)
		self.calls = []
		self.services = types.SimpleNamespace(call=self._call)

	def _call(self, domain, service, data, blocking=False):
		self.calls.append(
			{
				"domain": domain,
				"service": service,
				"data": data,
				"blocking": blocking,
			}
		)


def _run_script(notifications):
	hass = FakeHass(
		{
			"sensor.persistent_notifications_tracker": FakeState(
				{"notifications": notifications}
			)
		}
	)
	logger = FakeLogger()
	source = SCRIPT_PATH.read_text(encoding="utf-8")
	exec(compile(source, str(SCRIPT_PATH), "exec"), {"hass": hass, "logger": logger})
	return hass, logger


def _helper_value(hass, entity_id):
	for call in hass.calls:
		if call["data"].get("entity_id") == entity_id:
			return call["data"]["value"] if "value" in call["data"] else call["data"].get("option")
	raise AssertionError(f"no service call for {entity_id}")


def test_empty_tracker_clears_helpers_and_alarm():
	hass, logger = _run_script([])
	assert _helper_value(hass, "input_text.minidisplay_notification_registry") == ""
	assert _helper_value(hass, "input_text.minidisplay_notification_ids") == ""
	assert _helper_value(hass, "input_text.minidisplay_notification_titles") == ""
	assert _helper_value(hass, "input_text.minidisplay_notification_messages") == ""
	assert _helper_value(hass, "input_select.alarm_level") == "OK"
	assert any("0 notifications" in msg for _, msg in logger.messages)


def test_alarm_level_and_registry_from_data():
	hass, _logger = _run_script(
		[
			{
				"notification_id": "leak",
				"title": "Water leak",
				"message": "Bathroom sensor triggered alarm: 2 leftover",
				"created": "17:01",
				"data": {"Alarm": 2},
			},
			{
				"notification_id": "http-login",
				"title": "Login attempt failed",
				"message": "Invalid authentication",
				"created": "17:49",
				"data": {},
			},
		]
	)
	assert _helper_value(hass, "input_select.alarm_level") == "Take Action"
	assert _helper_value(hass, "input_text.minidisplay_notification_ids") == "leak,http-login"
	assert "17:01 Water leak" in _helper_value(
		hass, "input_text.minidisplay_notification_titles"
	)
	message = _helper_value(hass, "input_text.minidisplay_notification_messages")
	assert "Bathroom sensor triggered leftover" in message
	assert "alarm:" not in message.lower()
	registry = _helper_value(hass, "input_text.minidisplay_notification_registry")
	assert registry.startswith("leak|")
	assert '"alarm":2' in registry


def test_skips_notifications_without_id():
	hass, logger = _run_script(
		[
			{"title": "orphan", "message": "no id"},
			{
				"notification_id": "kept",
				"title": "Kept",
				"message": "ok",
				"created": "12:00",
				"data": {},
			},
		]
	)
	assert _helper_value(hass, "input_text.minidisplay_notification_ids") == "kept"
	assert any("Skipping notification without ID" in msg for _, msg in logger.messages)


if __name__ == "__main__":
	test_empty_tracker_clears_helpers_and_alarm()
	test_alarm_level_and_registry_from_data()
	test_skips_notifications_without_id()
	print("test_update_minidisplay: ok")
