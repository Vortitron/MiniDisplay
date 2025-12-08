logger.info("update_minidisplay.py: running script")

MAX_INPUT_LENGTH = 255
ALARM_TITLE_PREFIXES = {
	1: "Notification",
	2: "Action Required",
	3: "ACT NOW!",
}


def clamp(value):
	if not value:
		return ""
	val_str = str(value)
	if len(val_str) > MAX_INPUT_LENGTH:
		return val_str[:MAX_INPUT_LENGTH]
	return val_str


def normalise_text(value):
	if value is None:
		return ""
	text = str(value).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')
	return text.strip()


def strip_alarm_marker(text):
	if not text:
		return ""
	normalised = normalise_text(text)
	parts = normalised.split(' ')
	clean_parts = []
	skip_next_number = False

	for part in parts:
		lower_part = part.lower()

		if skip_next_number:
			if lower_part in ('0', '1', '2', '3'):
				skip_next_number = False
				continue
			skip_next_number = False

		if lower_part.startswith('alarm:'):
			number_part = lower_part.replace('alarm:', '')
			if number_part in ('', '0', '1', '2', '3'):
				if number_part == '':
					skip_next_number = True
				continue

		if lower_part == 'alarm:':
			skip_next_number = True
			continue

		clean_parts.append(part)

	return ' '.join(clean_parts).strip()


tracker_state = hass.states.get('sensor.persistent_notifications_tracker')
notifications = []
if tracker_state:
	raw_notifications = tracker_state.attributes.get('notifications', [])
	if raw_notifications is None:
		notifications = []
	else:
		try:
			notifications = list(raw_notifications)
		except Exception:
			logger.warning("Tracker notifications attribute cannot be converted to list")
			notifications = []
else:
	logger.warning("Persistent notification tracker not found; skipping update")
	notifications = []

entries_data = []

for idx, raw_notif in enumerate(notifications):
	try:
		notif_id = str(raw_notif.get('notification_id', '')).strip()
	except Exception:
		logger.warning("Skipping notification without get method")
		continue

	if not notif_id:
		logger.debug("Skipping notification without ID")
		continue

	try:
		raw_title = raw_notif.get('title', 'Notification') or 'Notification'
		raw_message = raw_notif.get('message', '') or ''
		data_block = raw_notif.get('data') or {}
	except Exception:
		logger.warning("Skipping notification %s with invalid structure", notif_id)
		continue

	title = normalise_text(raw_title)
	message = normalise_text(raw_message)

	alarm_from_data = 0
	if 'Alarm' in data_block:
		try:
			alarm_from_data = int(data_block['Alarm'])
		except (ValueError, TypeError):
			logger.debug("Notification %s has non-integer Alarm value: %s", notif_id, data_block['Alarm'])

	combined_text = f"{title} {message}".lower()
	alarm_from_message = 0
	if 'alarm:3' in combined_text or 'alarm: 3' in combined_text or 'emergency' in combined_text:
		alarm_from_message = 3
	elif 'alarm:2' in combined_text or 'alarm: 2' in combined_text or 'take action' in combined_text:
		alarm_from_message = 2
	elif 'alarm:1' in combined_text or 'alarm: 1' in combined_text or 'notify' in combined_text:
		alarm_from_message = 1

	alarm_level = max(0, min(3, max(alarm_from_data, alarm_from_message)))

	display_title_prefix = ALARM_TITLE_PREFIXES.get(alarm_level)
	# If title is generic/empty and we have an alarm prefix, just use the prefix
	if display_title_prefix:
		if title in ('Notification', '', 'None', 'none'):
			effective_title = display_title_prefix
		else:
			effective_title = f"{display_title_prefix} - {title}"
	else:
		effective_title = title if title not in ('', 'None', 'none') else 'Notification'
	display_message = strip_alarm_marker(message)

	entries_data.append({
		'idx': idx,
		'notif_id': notif_id,
		'title': effective_title,
		'message': display_message,
		'alarm_level': alarm_level,
		'data': {'alarm': alarm_level},
	})

sorted_entries = sorted(entries_data, key=lambda item: (-item['alarm_level'], -item['idx']))

entries = []
notification_ids = []
notification_titles = []
notification_messages = []
max_alarm_level = 0

for entry in sorted_entries:
	data_block = '{"alarm":%s}' % entry['alarm_level']
	entries.append(f"{entry['notif_id']}|{entry['title']}|{entry['message']}|{entry['alarm_level']}|{data_block}")
	notification_ids.append(entry['notif_id'])
	notification_titles.append(entry['title'])
	notification_messages.append(entry['message'])
	if entry['alarm_level'] > max_alarm_level:
		max_alarm_level = entry['alarm_level']

registry_value = '||'.join(entries)

# Update registry helper first (even if empty)
hass.services.call(
	'input_text',
	'set_value',
	{
		'entity_id': 'input_text.minidisplay_notification_registry',
		'value': clamp(registry_value),
	},
	blocking=False,
)

# Update individual helper fields
hass.services.call(
	'input_text',
	'set_value',
	{
		'entity_id': 'input_text.minidisplay_notification_ids',
		'value': clamp(','.join(notification_ids)),
	},
	blocking=False,
)

hass.services.call(
	'input_text',
	'set_value',
	{
		'entity_id': 'input_text.minidisplay_notification_titles',
		'value': clamp('|'.join(notification_titles)),
	},
	blocking=False,
)

hass.services.call(
	'input_text',
	'set_value',
	{
		'entity_id': 'input_text.minidisplay_notification_messages',
		'value': clamp('|'.join(notification_messages)),
	},
	blocking=False,
)

alarm_options = ['OK', 'Notify', 'Take Action', 'Emergency']
alarm_level_name = alarm_options[max_alarm_level] if max_alarm_level < len(alarm_options) else 'OK'

hass.services.call(
	'input_select',
	'select_option',
	{
		'entity_id': 'input_select.alarm_level',
		'option': alarm_level_name,
	},
	blocking=False,
)

logger.info(
	"Updated MiniDisplay: %s notifications, max alarm level: %s", len(notification_ids), max_alarm_level
)
