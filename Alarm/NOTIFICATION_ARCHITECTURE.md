# Notification Architecture

## Overview
The MiniDisplay reads persistent notifications directly from Home Assistant, making each notification an independent screen that can be dismissed individually.

## How It Works

### 1. Home Assistant Automation (`AlarmAutomation.yaml`)
- Triggers on service calls to `persistent_notification.create` and `persistent_notification.dismiss`
- Also triggers on Home Assistant start to sync existing notifications
- Calls Python script to process notifications

### 1.5. Python Script (`process_notifications.py`)
**Required since HA 2023.6** - persistent notifications no longer available in `states`
- Accesses internal notification manager directly
- Extracts notification IDs, titles, messages, and alarm levels
- Stores in three separate `input_text` entities:
  - `minidisplay_notification_ids`: comma-separated IDs (e.g., `"alert_1,warning_2"`)
  - `minidisplay_notification_titles`: pipe-separated titles (e.g., `"Low Battery|System Warning"`)
  - `minidisplay_notification_messages`: pipe-separated messages (e.g., `"Kitchen sensor at 15%|Update available"`)

### 2. ESPHome Device (`minidisplay.yaml`)
- Subscribes to all three `input_text` entities
- Parses comma/pipe-separated data into vectors
- Creates one screen per notification (after the 8 base entity screens)
- Caches titles and messages locally for fast display rendering

### 3. Display Rendering
When viewing a notification screen:
- ESPHome looks up cached title and message from vectors
- Displays: `Alert 1/3` + title + wrapped message + "Push dial to dismiss"
- No runtime queries to Home Assistant needed (data already cached)

### 4. Dismissal
When encoder is pushed on a notification screen:
- ESPHome calls `persistent_notification.dismiss` with the specific notification ID
- Home Assistant removes the notification
- Automation re-triggers, updates ID list
- ESPHome refreshes screen count

## Benefits Over Previous Approach

### Old (Serialised Payload - Single Field)
❌ 255 character limit for all notifications combined  
❌ Truncation when many alerts active  
❌ Complex tab-delimited parsing  

### New (Three-Field Cache)
✅ 255 chars per field (IDs, titles, messages separate)  
✅ ~750 total characters available  
✅ Always shows current data (updated on any notification change)  
✅ Each notification independent  
✅ Simple pipe/comma-separated parsing  
✅ True one-to-one mapping between HA notifications and display screens  
✅ Fast rendering (no runtime HA queries)  

## Limitations
- Maximum ~50 notification IDs in the comma-separated list (255 chars ÷ ~5 chars per ID)
- If you exceed this, only the first ~50 notifications will be accessible
- For most use cases (< 10 active notifications), this is more than sufficient

## Example Flow

```
1. User creates notification in HA:
   persistent_notification.create(
     notification_id="low_battery",
     title="Low Battery",
     message="Kitchen sensor at 15%"
   )

2. Automation triggers → input_text = "low_battery"

3. ESPHome receives update → notification_ids = ["low_battery"]

4. User rotates to screen 9 (8 base + 1 notification)

5. Display queries HA → gets title="Low Battery", message="Kitchen sensor at 15%"

6. User pushes encoder → ESPHome calls persistent_notification.dismiss("low_battery")

7. Automation triggers → input_text = "" (empty)

8. ESPHome receives update → notification_ids = []

9. Display returns to base entities
```

## Scroll Mode Fix
Changed from 2-step jumps to 1-step per encoder click when holding the confirm button, preventing skipped entities.

