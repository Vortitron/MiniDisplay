# Saga camera test

`index.html` is served by Home Assistant from `/config/www/saga-cam/index.html`
(`/local/saga-cam/index.html`). Open it on the Saga in Chrome over the
HTTPS (Vome hosted) address, with the Push camera's webhook id after `#`:

    https://<hosted address>/local/saga-cam/index.html?v=<n>#hook=<id>&facing=environment&auto=1

The id is not in this repo or in the page. It lives in `configuration.yaml`
(`camera: platform: push, name: Saga Web`) and in the two webhook automations.

- `auto=1` runs a test unattended: night stack, then full-sensor photo, both
  sent to `camera.saga_web`. Chrome must already allow the camera for the site.
- Status lines go to webhook `<id>_log`; automation `saga_web_log` writes them
  to the logbook ("Saga camera page") and, on "Sent <name>.jpg", saves the photo
  to `/config/frontpath_snapshots/web-<time>-<name>`.
- Remote start: `notify.mobile_app_saga` with `message: command_activity`,
  `intent_action: android.intent.action.VIEW`, `intent_uri: <the address>`,
  `intent_package_name: com.android.chrome`. Change `?v=` each time so Chrome
  loads the page afresh.
- Uploads over the Vome hosted address are refused from about 1 MB (413), so
  the page re-encodes big photos under 950 KB.

16 Oct 2026, by day: the rear camera gives the page 4096x3072 (Fully Kiosk's
snapshots are 352x288).

Night comparison, 16-18 Oct: automation `saga_web_night_test` at 20:00 and
23:30 sends `command_screen_on`, opens the page with `auto=1` (a fresh `?v=`
each time), and two minutes later `command_launch_app`
`io.homeassistant.companion.android` returns the Saga to the HA app, its
launcher. The Saga has no screen lock, so waking it lands straight on Chrome.
Tested by day on 16 Oct: both photos saved, Saga back on HA.

Live mode (16 Oct): the page stays open on the Saga with the camera running
and, with an access token pasted into its box (a non-admin HA user's token,
kept in the Saga's browser only), subscribes to Path Person Detected and
input_button.saga_cam_test_shot. Each one gets three photos, detect<HHMMSS>-a
(a frame at once), -b (night stack), -c (a frame ~3 s on).
- `saga_web_watchdog`: every 5 min, if `input_datetime.saga_cam_last_seen` is
  over 25 min old, wakes the Saga and reopens the page with `live=1`.
- `frontpath_trigger_snapshot` (Fully still) now runs only while the page is
  down, so Fully's motion detection never takes the camera from Chrome.
- `saga_web_night_test` presses the test-shot button at 20:00 and 23:30 until
  18 Oct.

Door view (16 Oct evening): live mode now shows the front-door dashboard
(`/front-door/door`) full screen in an iframe, with the camera running
underneath, so the Saga no longer needs Fully Kiosk. Chrome on the Saga is
logged in to HA as the Saga camera user. The dot in the bottom-right corner
is green when the camera is on and HA connected; tap it for the camera tools.
`input_button.saga_cam_reload` reloads the page in place after an update.
Photos go up full size first and are only squeezed after a 413, so a higher
upload limit on the Vome hosted route takes effect by itself (still about
1 MB when tested on 16 Oct at 20:16, despite the announced 8 MB).
