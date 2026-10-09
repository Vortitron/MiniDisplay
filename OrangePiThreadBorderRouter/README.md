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
| OTBR watchdog | Pi cron every 5 min (was dead 2026-09-20 → 10-05: cron PATH had no `sysctl`; now absolute paths) | Restarts `otbr` if HA's Thread panel cannot see the border router; restarts the Matter add-on after a GamlaBio link drop or when every Matter light is unavailable while the mesh is up |
| `matterjs-server` container (matter.js 1.4.0) | **This Pi**, host network, data `/root/otbr/matterjs_data`, vendor 0x134B / fabric 2 | Matter controller since 2026-10-06. HA's Matter integration points at `ws://192.168.1.7:5580/ws`. The hosted add-on is **stopped, boot manual** (never start it alongside: same fabric). See `MATTER_LOCAL_MIGRATION.md` |
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
| `linkmon.sh` | Link monitor (Pi ↔ GamlaBio Hosted, IPv4 / IPv6 / Thread return route); runs as transient unit `linkmon` since 2026-10-05, log `/root/otbr/linkmon/linkmon.log` |
| `matter_local.sh`, `MATTER_LOCAL_MIGRATION.md` | Moving the Matter controller from the hosted add-on onto this Pi (done 2026-10-06) |

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

Each run:

1. Re-applies `accept_ra=2` / IPv6 forwarding (otbr-agent can reset these).
2. Subscribes to `thread/discover_routers`. If HA is unreachable, it records that and **does not** restart OTBR (a down VPN must not blip the mesh).
3. When HA is reachable again after an outage, it restarts the Matter Server add-on (`core_matter_server`). CHIP reconnect backoff after a VPN drop can sit at 30–60 minutes; an add-on restart clears it. Same kick if every Kajplats light is `unavailable` while `ot-ctl neighbor table` still has routers.
4. Restarts `otbr` only if the Thread panel still cannot see the border router (10-minute cooldown).

Token lives in `/root/otbr/watchdog/ha_token.txt` (`chmod 600`), never committed. A full OTBR container restart is the only reliable mDNS re-announce; bouncing `mdnsd` alone leaves `otbr-agent` unpublished.

## Useful checks

```
docker exec otbr ot-ctl state          # expect: leader
docker exec otbr ot-ctl neighbor table
docker exec otbr ot-ctl br counters    # unicast counters should be non-zero once devices exist
sysctl net.ipv6.conf.all.forwarding    # expect: 1
```

REST: `http://192.168.1.7:8081/node` — `State: leader`. Web UI on port 7586. Do not use the web UI's pre-filled "Form Network" button (it ships OpenThread demo credentials).

Also confirm:

```
sysctl net.ipv6.conf.end0.accept_ra    # expect: 2 (kernel resets this to 0 when forwarding=1)
docker exec otbr ot-ctl ping <device-omr-ipv6>
```

## Commissioned devices

IKEA **KAJPLATS E14 WS globe 806lm** bulbs on GamlaBio (all Thread routers):

| HA entity | Matter node | Typical OMR address |
|-----------|-------------|---------------------|
| `light.kajplats_e14_ws_globe_806lm` (North spot, loft) | `@1:1` | `fd54:508a:5479:1:46b5:6caa:6bf:ea31` |
| `light.loft_desk_kajplats` (Desk, loft) | `@1:2` | `fd54:508a:5479:1:d0f7:2227:7192:a73` |
| `light.kajplats_e14_ws_globe_806lm_2` (Living room spot) | `@1:3` | hops the loft bulbs; RSSI to the dongle around −62 dBm |

Matter Server is the HAOS add-on on the cloud VM (`host_network: true`), talking IPv6 UDP/5540 to those OMR addresses via the L2 VPN and this Pi.

## Matter shows unavailable while the bulbs are still on

This is usually **not** a dead OTBR. Check in this order:

1. **Thread mesh vs Matter session.** `ot-ctl state` = `leader` and `ot-ctl ping` to the OMR address succeeding means the bulbs are on the 802.15.4 mesh. HA `unavailable` then means the *Matter controller* (cloud VM) lost its IPv6 UDP session, not that the lamp has powered off. Typical Matter log: subscribe succeeds, then `Subscription … timed out after 1m 44s`, `Probe … (failed)`, sometimes `address is unreachable`.
2. **RF to the dongle.** Neighbour RSSI around −90 dBm and Link Quality 1 is the dropout edge. The living-room Kajplats is the useful hop (about −62 dBm, LQ 3); loft bulbs still look weak to the dongle and should go via that router. Channel is 17 (2.4 GHz, overlaps Wi-Fi channel 6).
3. **IPv6 path from GamlaBio.** Matter uses `fd54:508a:5479:1::/64` (OTBR OMR prefix). The Pi advertises that as a Route Information Option, lifetime 1800 s. The HA VM must install that RIO; unicast IPv6 Pi↔HA is fine (~20 ms over the VPN) but IPv6 multicast/RA has failed on this link before. `br counters` unicast climbing means LAN↔mesh forwarding is working.
4. **`accept_ra` on `end0`.** The sysctl file sets `accept_ra=2`; `otbr-agent` / the kernel can still show `0` at runtime once forwarding is on. The watchdog re-applies this every five minutes.
5. **Watchdog recovery.** After a GamlaBio/VPN outage the Matter add-on is restarted on the next successful HA check (10-minute cooldown). OTBR is only restarted if the Thread panel still cannot see the border router.

Do **not** start the leftover HA OTBR add-on or the Pi `matter-server` compose profile — both fight this setup.
