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

Gallery (17 Oct): `gallery.html`, served at `/local/saga-cam/gallery.html`.
Photos by date, newest first; one card per detection or test (photos a/b/c);
tap for a large view with Prev / Next (buttons, arrow keys, swipe). Notes say
why each fired: the FrontPath Path Trigger gates at that moment (history),
or "radar burst" for test shots taken by `frontpath_burst_photo` (logbook).
It lists the photos through HA's media source, so configuration.yaml adds
`/config/frontpath_snapshots` as the media folder `frontpath` (keeping
`local: /media`), and it signs in with the browser's own HA login
(`hassTokens`) or the Saga camera token.

Later on 17 Oct: the gallery shows one day at a time (Older / Newer, a date
list, the day kept after `#` in the address), and its cards and strip use
480 px thumbnails made on the server, so a phone away from home only
downloads a full-size photo when one is opened. `frontpath_photos.py` (in HA
at `/config/scripts/`, run as `shell_command.frontpath_photos` by
`saga_web_log` after each saved photo) makes the missing thumbnails in
`frontpath_snapshots/thumbs/` and copies the newest photo to `latest.jpg`.
A Local File integration entry (added in the UI: HA no longer takes it in
YAML), `camera.frontpath_latest`, shows that file, so the
latest photo survives a restart (the Push camera keeps its image in memory
only). The front-door dashboard shows it (tap to enlarge, hold for a fresh
one), with "Take photo" (presses `input_button.saga_cam_test_shot`, for a
laptop with no long press) and "Photo gallery" buttons.

Battery (17 Oct evening): the Saga went flat on its charger. Overnight it held
(65% to 62.5% in eight hours) but from dawn it lost ~9% an hour, charging all
the while: by day the camera ran uncapped at 2592x1944 and ~30 fps, at night
it slows itself for long exposures. The page now asks for at most 10 fps,
and in live mode lets go of the camera at 15% battery (Battery Status API),
taking it back at 35%, the door dashboard staying up. `saga_web_watchdog`
no longer reopens the page below 35%: reopening it at 1% kept the Saga from
charging for five hours.

Installable app (18 Oct): `manifest.json`, `sw.js` and two icons make the
page installable from Chrome as "Front door" (Chrome menu, Install app /
Add to Home screen): full screen with no address bar, opening straight into
live mode (`index.html?app=1#facing=environment&live=1`). The webhook id is
not in the manifest; the page keeps it in the browser (`sagaHook`) from the
first visit with `#hook=`, and the installed app shares that storage. The
service worker only passes the app's own files through (no caching; the
/api webhook and websocket are untouched). HA stays the Saga's Home app.

Who is it (20 Oct): FrontPath now has a twitchy "Path Motion" sensor
(binary_sensor.front_walkway_frontpath_ble_processing_path_motion) beside
the unchanged Path Person Detected that drives the lights; the camera page
photographs every Path Motion (cats and the tree included) and runs an
object detector on the photo set in the browser (MediaPipe
EfficientDet-Lite0 from jsDelivr / Google storage, loaded once at live
start). The best person and animal scores go to webhook `<hook>_seen`;
automation `frontpath_seen` (FrontPathSeen.yaml) calls a person at 50%+ a
person, and sends an unsure or night stack (input_text.frontpath_last_stack_photo,
recorded by saga_web_log) to an AI task for a second opinion. Results:
input_text.frontpath_seen, input_datetime.frontpath_person_seen, and a
"FrontPath seen" logbook line the gallery adds to each card's note. The AI
task is ai_task.claude_ai_task (Anthropic integration, added 20 Oct; the
key must be made inside a Console workspace, or HA's setup says "unexpected
error"). Tested 20 Oct: empty steps "nothing", the 16 Oct 23:28 night stack
"animal (likely fox or deer)", ~5 s a call.


Where it is (20 Oct evening): the page also sends where the best person and
animal were (`person_box` / `animal_box`: photo a/b/c and [left, top,
width, height] as fractions), and the AI is asked for a rough box too. The
verdict ends with them, e.g. "cat 41% (Saga) [b cat 0.41,0.32,0.08,0.2]",
"~b" for the AI's guess. The gallery circles them on the card and the large
photo: solid for the Saga, dashed for the AI, faint on the set's other
photos. Only photos from then on have boxes.

In the HA phone app (20 Oct): the gallery said "Not logged in" because the
app keeps its login to itself (no localStorage "hassTokens"). It now asks
the app for a token the way HA's own frontend does (Android
window.externalApp.getExternalAuth, iOS webkit getExternalAuth), and when
shown in a dashboard card it borrows the dashboard's login.

Person alert (20 Oct, FrontPathPersonAlert.yaml): a "person" verdict sends
the photo they are in to the Pixel 8 (tap opens the gallery), unless the
Pixel's Bluetooth beacon is in Bermuda area "Front walkway" (now, in the
last 3 min, or within 30 s), or it came home by GPS in the last 5 min.
saga_web_log now also keeps the current set's saved file names in
input_text.frontpath_last_photos for it.
