# Alarm Automations

This directory contains Home Assistant automations for managing alarm state indicators.

## Setup

### 1. Enable Python Scripts
Add to your `configuration.yaml`:
```yaml
python_script:
```

Then restart Home Assistant.

### 2. Copy Python Script
Copy `update_minidisplay.py` to your Home Assistant `python_scripts` folder:
- Default location: `/config/python_scripts/update_minidisplay.py`
- Create the folder if it doesn't exist

### 3. Load Notification Tracker
Add to your `configuration.yaml`:
```yaml
template: !include Alarm/NotificationTracker.yaml
```

Or if using packages:
```yaml
homeassistant:
  packages:
    notification_tracker: !include Alarm/NotificationTracker.yaml
```

This creates `sensor.persistent_notifications_tracker` that tracks all active notifications.

### 4. Load Helper Entities
Add to your `configuration.yaml`:
```yaml
input_text: !include Alarm/AlarmNotificationHelpers.yaml
```

Or if using packages:
```yaml
homeassistant:
  packages:
    alarm_helpers: !include Alarm/AlarmNotificationHelpers.yaml
```

Then restart Home Assistant or reload templates and input helpers.

### 5. Load Automation
Import `AlarmAutomation.yaml` through the UI or add to your automations configuration

## Why This Approach?

Since Home Assistant 2023.6, persistent notifications are no longer available in `states`. According to the [Python Scripts documentation](https://www.home-assistant.io/integrations/python_script/), the sandbox doesn't allow access to `hass.components` for security reasons.

**Our solution:**
1. **Template sensor** listens for `persistent_notification.create/dismiss` service calls
2. Maintains a list of active notifications in its attributes
3. **Automation** syncs from the sensor to `input_text.minidisplay_notification_registry`
4. **Python script** parses and updates the three display entities

See the [Home Assistant Community discussion](https://community.home-assistant.io/t/heads-up-2023-6-longer-has-persistent-notifications-in-states-what-to-do/578654) for more background.

## How It Works

### `AlarmAutomation.yaml`
- Watches persistent notifications for `Alarm` level in the `data` attribute
- Calculates the highest alarm level present across all current notifications
- Updates `input_select.alarm_level` to one of `OK`, `Notify`, `Take Action`, or `Emergency`
- Stores notification IDs, titles, and messages in three separate `input_text` entities

### `AlarmNotificationHelpers.yaml`
- Declares three `input_text` entities (255 chars each):
  - `minidisplay_notification_ids` - comma-separated IDs
  - `minidisplay_notification_titles` - pipe-separated titles
  - `minidisplay_notification_messages` - pipe-separated messages

## Creating Notifications with Alarm Levels

Use the `data` attribute to set the alarm level:

```yaml
# Level 1 - Notify (single flash per minute)
service: persistent_notification.create
data:
  notification_id: "low_battery"
  title: "Low Battery"
  message: "Kitchen sensor at 15%"
  data:
    Alarm: 1

# Level 2 - Take Action (double flash every 15s)
service: persistent_notification.create
data:
  notification_id: "water_leak"
  title: "Water Leak Detected"
  message: "Bathroom sensor triggered"
  data:
    Alarm: 2

# Level 3 - Emergency (constant quick flash)
service: persistent_notification.create
data:
  notification_id: "fire_alarm"
  title: "FIRE ALARM"
  message: "Smoke detected in kitchen"
  data:
    Alarm: 3
```

## Testing
1. Ensure helper entities are loaded (check Developer Tools → States for `input_text.minidisplay_notification_ids`)
2. Create a test notification with `Alarm: 1` in the data attribute (see example above)
3. Verify `input_select.alarm_level` changes to "Notify"
4. Verify the three `input_text` entities populate with notification data
5. Check MiniDisplay shows the notification as a screen
6. Clear the notification and verify everything resets to `OK`

