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
