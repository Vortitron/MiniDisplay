# Orange Pi Thread Border Router

Orange Pi Zero 3 plus a Sonoff Dongle Plus MG24, running OpenThread so the cloud-hosted GamlaBio Home Assistant can commission Matter-over-Thread devices (first success: an IKEA Kajplats E14 WS globe).

This file is the operational guide. `SETUP_LOG.md` is the chronological working log (dead ends included) for a later how-to / Vome knowledgebase article.

## What is actually running

| Piece | Where | Role |
|-------|--------|------|
| `otbr` container (`ghcr.io/ownbee/hass-otbr-docker:arm64-v0.3.0`) | Pi `192.168.1.7`, host network | Thread leader, REST API `:8081`, web UI `:7586` |
| Sonoff MG24 RCP | `/dev/ttyUSB0` at 460800, **no** UART flow control | 802.15.4 radio |
| IPv6 forwarding sysctl | Pi host | Forwards LAN ↔ Thread (`wpan0`). Docker cannot set this in host-network mode |
| iptables kernel modules | Pi host, `/etc/modules-load.d/` | OTBR firewall (`ip6table_filter` etc.) |
| OTBR watchdog | Pi cron every 5 min | Restarts `otbr` only if HA's Thread panel cannot see the border router |
| Matter Server add-on `9.2.0` | GamlaBio (HAOS), `ble_proxy: true`, host network | Commissioner. **Not** the leftover Python Matter Server on the Pi |
| ESPHome Bluetooth proxies | Several around the house, `active: true` | BLE for commissioning without server-side Bluetooth |
| Official HA OTBR add-on | GamlaBio, **stopped**, `device: null` | Leftover. Do not start it — there is no radio on the VM |

Thread network name: `OpenThread-2729`. HA Thread integration has this dataset as **preferred**, sourced from the `otbr` config entry pointing at the Pi.

Do **not** start the `matter-server` compose service on the Pi. It is parked behind `profiles: ["unused"]`. Running it shares UDP 5353 with OTBR's `mdnsd` and advertises a second Matter fabric.

## Files in this folder

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Live compose on the Pi (`/root/otbr/docker-compose.yml`) |
| `99-openthread-border-router.conf` | Host sysctl → `/etc/sysctl.d/` on the Pi |
| `openthread-border-router-modules.conf` | Kernel modules → `/etc/modules-load.d/openthread-border-router.conf` |
| `otbr_watchdog.py` | Copy of `/root/otbr/watchdog/otbr_watchdog.py` (token is **not** in git) |
| `SETUP_LOG.md` | Full setup narrative |

## Host requirements (the bits Docker cannot do)

On the Orange Pi:

1. Load iptables modules (already in `/etc/modules-load.d/openthread-border-router.conf`).
2. Enable IPv6 forwarding **and** keep accepting LAN Router Advertisements:

```
net.ipv6.conf.all.forwarding = 1
net.ipv6.conf.default.forwarding = 1
net.ipv6.conf.end0.accept_ra = 2
net.ipv6.conf.end0.accept_ra_rt_info_max_plen = 64
```

`accept_ra = 2` is required: once forwarding is on, the kernel otherwise ignores RAs and the Pi loses its IPv6 default route.

Without forwarding, devices still join the 802.15.4 mesh, then Android hangs on **checking connectivity to Thread network OpenThread-2729**. Confirm forwarding is working with `ot-ctl br counters` — inbound/outbound unicast should climb after a device is commissioned.

## Adding another Matter-over-Thread device (Android)

1. Phone on the same home Wi-Fi as the Pi (not guest Wi-Fi, not mobile data).
2. Companion app: **Settings → Companion app → Troubleshooting → Sync Thread credentials**. Need this once per phone (or after clearing Google Play Services). Google Home Minis in this house are **not** Thread border routers.
3. Put the device in pairing mode close to the Orange Pi (or an ESPHome Bluetooth proxy).
4. Add it from the Home Assistant companion app.

If it still says it needs a border router, Android is holding an empty Google Thread network — clear Google Play Services storage/cache, sync again, retry.

Alternative: add from the HA UI with the setup code so Matter Server commissions via BLE proxy and skips Google Play Services.

## Watchdog

Home Assistant sometimes drops the live Thread border-router discovery after a Core restart, even though OTBR is healthy. Cron on the Pi:

```
*/5 * * * * /usr/bin/python3 /root/otbr/watchdog/otbr_watchdog.py >> /root/otbr/watchdog/cron.log 2>&1
```

The script subscribes to `thread/discover_routers` and only runs `docker compose restart otbr` if nothing appears in 8 seconds (10-minute cooldown). Token lives in `/root/otbr/watchdog/ha_token.txt` (`chmod 600`), never committed.

A full container restart is the only reliable mDNS re-announce; bouncing `mdnsd` alone leaves `otbr-agent` unpublished.

## Useful checks

```
docker exec otbr ot-ctl state          # expect: leader
docker exec otbr ot-ctl neighbor table
docker exec otbr ot-ctl br counters    # unicast counters should be non-zero once devices exist
sysctl net.ipv6.conf.all.forwarding    # expect: 1
```

REST: `http://192.168.1.7:8081/node` — `State: leader`. Web UI on port 7586. Do not use the web UI's pre-filled "Form Network" button (it ships OpenThread demo credentials).

## First commissioned device

IKEA **KAJPLATS E14 WS globe 806lm** on GamlaBio as `light.kajplats_e14_ws_globe_806lm` (colour temperature + xy). It is a Thread router, so later devices can mesh through it rather than only the dongle.
