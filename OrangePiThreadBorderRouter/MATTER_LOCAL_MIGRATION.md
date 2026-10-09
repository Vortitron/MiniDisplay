# Moving the Matter controller onto the Orange Pi

**Done 2026-10-06** (Matter offline 10:39–11:13 local).
All 7 nodes (4 Kajplats, 3 BILRESA) subscribed within 10 s of start; all
57 Matter entities available in HA right after the repoint.

What differed from the plan:
- The standalone image ignored the copied storage at first and created an
  empty controller (`server-1-fff1`, "Found 0 nodes"): it defaults to vendor
  0xFFF1 / fabric 1, the add-on uses **vendor 0x134B (4939) / fabric 2**
  (`server-2-134b`). Fixed with `VENDOR_ID`/`FABRIC_ID` in the compose file;
  the stray `server-1-fff1` was deleted. Check for `server-2-134b` and
  "Found legacy data / N node(s)" in the log on any rebuild.
- The hosted HA has no Backups page, the Pi's token is not admin and Vome
  cannot download backups, so the backup was fetched from this PC with a
  temporary admin long-lived token straight from `http://192.168.1.15:8123
  /api/hassio/backups/<slug>/download` (token file shredded afterwards).
- `POST /addons/core_matter_server/stop` through Vome returned 502 and the
  add-on kept running; `hassio.addon_stop` (service call) stopped it.
- mDNS: no conflict with OTBR's `mdnsd` on 5353; the server published its
  operational `_matter._tcp` record fine.

**Afterwards (found 2026-10-07):** Vome CHAP restarted the add-on within
the hour. It "holds" the home's add-ons for the GamlaBio.local standby, and
every hour it sets each one to boot auto and starts it on the active
install. With both controllers on the fabric, light subscriptions timed out
every ~1m40s and the remotes went dead. `core_matter_server` must be
unticked from CHAP's add-on list in the Vome portal, or it comes back at
about :40 past each hour. If Matter goes flaky, check the add-on's state
first.

Rollback material: HA backup `matter-to-pi` (slug `a94179b7`) and a root-only
copy at `/root/otbr/matter_migration/matter-to-pi.tar` on the Pi.

---

Original plan (prepared 2026-10-05):

## Why

GamlaBio Hosted runs in the cloud; the Thread border router is this Pi.
The Matter Server add-on therefore reaches every Thread device over the
HomeLink L2 VPN. Its log shows every device's subscription timing out at
the same moment, roughly hourly (seen ~20:17 and ~21:15 on 2026-10-05):
short link drops. Mains lights resubscribe within 2 minutes. The BILRESA
remotes negotiate a 15-minute interval, so after a drop the server only
notices 15 m 38 s later; presses in between are held on the remote and
then arrive in one burst. That is the "buttons stopped working".

With the controller on the Pi, Matter traffic never leaves the house. Only
HA's WebSocket to the server crosses the VPN, and HA reconnects that in
seconds. `linkmon.sh` (running on the Pi since 2026-10-05 21:38) records
the drops themselves.

## What is ready

| Piece | State |
|-------|-------|
| `docker-compose.yml` service `matterjs-server` | **On the Pi** (old copy kept as `docker-compose.yml.bak-20261005`); behind profile `matter-local`, so a plain `docker compose up -d` still only sees `otbr` |
| Image `ghcr.io/matter-js/matterjs-server:1.4.0` | **Pulled** (arm64, runs as uid 1000, = add-on 9.2.0). SD card 805 MB free after |
| `matter_local.sh` | **On the Pi** at `/root/otbr/matter_local.sh`: `unpack <backup.tar>`, `start` (needs `CONFIRM_ADDON_STOPPED=yes`), `status`, `stop`. Unpack tested against a mock backup |
| `otbr_watchdog.py` | **Deployed.** Never restarts the add-on once a `matterjs-server` container exists; restarts the local container instead when every Matter light is unavailable while the mesh is up; skips the "HA link recovered" kick (not needed locally) |
| Parked Python `matter-server` | **Removed** 2026-10-05 (container and 644 MB image), with Andy's OK |

## Switch-over (about 10 minutes with every Matter device offline)

Never have the add-on and the local server running at the same time: both
would be the same controller on the same fabric.

1. **Snapshot** (Claude, via Vome): list Matter devices and which are
   available, so the result can be compared.
2. **Stop the add-on and keep it stopped** (Claude, Vome
   `ha_supervisor_api`): `POST /addons/core_matter_server/options`
   `{"boot": "manual", "watchdog": false}`, then
   `POST /addons/core_matter_server/stop`. Confirm `state: stopped`.
3. **Back it up** (Claude): `POST /backups/new/partial`
   `{"name": "matter-to-pi", "addons": ["core_matter_server"]}`. Taken after
   the stop, so the data is final.
4. **Download it** (Andy): Settings → System → Backups → `matter-to-pi` →
   Download, to this PC. The Pi's HA token gets 401 on `/api/hassio/*` and
   Vome cannot download backups, so this step is manual.
5. **Copy and start** (Claude, over SSH):
   `scp <backup>.tar root@192.168.1.7:/root/otbr/matter_migration/`, then
   `matter_local.sh unpack /root/otbr/matter_migration/<backup>.tar` and
   `CONFIRM_ADDON_STOPPED=yes matter_local.sh start`. Check the log: fabric
   loaded, nodes listed, WebSocket on 5580, no mDNS/5353 errors (OTBR's
   `mdnsd` also uses 5353).
6. **Repoint HA** (Claude, Vome `ha_config_flow`): start a `matter` flow,
   answer "use the add-on" = no, URL `ws://192.168.1.7:5580/ws`. In
   September this updated the existing entry in place
   (`reconfiguration_successful`), see SETUP_LOG.md section 11.
7. **Verify**: every Matter light available again and switchable; each
   BILRESA button pressed once and seen in HA; the local log shows the
   remotes' subscriptions (15 min interval). Then watch for a day: no
   presses should arrive late or in bursts.
8. **Tidy up**: README "What is actually running" table, memory notes.
   The GamlaBio.local standby (CHAP) should also point at
   `ws://192.168.1.7:5580/ws` if it ever takes over.

## Rollback

1. `matter_local.sh stop` on the Pi (and `docker rm matterjs-server`, so
   the watchdog goes back to managing the add-on).
2. `POST /addons/core_matter_server/options {"boot": "auto", "watchdog": true}`
   and `POST /addons/core_matter_server/start`.
3. Repoint HA: `matter` flow, "use the add-on" = yes.

The add-on's own data is untouched by all of this, and the fabric is the
same, so the devices accept it again.

## Unknowns

- Whether matter.js on the Pi coexists with OTBR's `mdnsd` on UDP 5353.
  The old Python server did bind alongside it but caused trouble
  (SETUP_LOG section 16).
- Whether pairing new devices through HA's Bluetooth proxies (the add-on's
  `ble_proxy` option) works against a standalone server.
- The add-on's internal data layout: `unpack` expects `data/` inside the
  add-on archive and stops with a listing if it is not there.
