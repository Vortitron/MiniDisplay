logger.info("update_minidisplay.py: running script")

MAX_INPUT_LENGTH = 255

def clamp(value):
    if not value:
        return ""
    val_str = str(value)
    if len(val_str) > MAX_INPUT_LENGTH:
        return val_str[:MAX_INPUT_LENGTH]
    return val_str

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

entries = []
notification_ids = []
notification_titles = []
notification_messages = []
max_alarm_level = 0

for raw_notif in notifications:
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

    title = str(raw_title).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ').strip()
    message = str(raw_message).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ').strip()

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

    entries.append(f"{notif_id}|{title}|{message}|{alarm_level}")
    notification_ids.append(notif_id)
    notification_titles.append(title)
    notification_messages.append(message)
    if alarm_level > max_alarm_level:
        max_alarm_level = alarm_level

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

