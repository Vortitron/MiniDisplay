# Orange Pi Zero 3 as a Thread Border Router for Home Assistant — Setup Log

Raw working log kept during setup, for later reuse as a blog post / how-to guide / Vome.io knowledgebase articles. Written chronologically as things happened, including the dead ends — those are often the most useful part of a write-up.

**Operational guide (what is running, how to add devices, host sysctls): see `README.md` in this folder.** End-to-end commissioning succeeded on 26 Aug 2026 (IKEA Kajplats E14 WS globe → `light.kajplats_e14_ws_globe_806lm` on GamlaBio).

**Hardware/environment:**
- Orange Pi Zero 3, running Armbian 26.8.1 (bookworm), root partition only 3.5GB (eMMC/SD — tight, mattered several times below)
- Radio: Sonoff Dongle Plus MG24 (Silicon Labs EFR32MG24), connected via USB, `/dev/ttyUSB0`
- Home Assistant: "GamlaBio" instance, hosted by Vome in a datacentre (cloud VM, no physical hardware access), reached from the home LAN via an L2 VPN tunnel
- Goal: turn the Orange Pi into a Thread border router Home Assistant can use, then get Matter-over-Thread device commissioning working end to end

---

## 1. Radio firmware — already done

The MG24 dongle was already flashed with OpenThread RCP firmware (`SL-OPENTHREAD/2.4.4.0`), confirmed via:

```
universal-silabs-flasher --device /dev/serial/by-id/usb-SONOFF_SONOFF_Dongle_Plus_MG24_...-if00-port0 probe
```

which detected `ApplicationType.SPINEL` at 460800 baud. No flashing needed — started straight into border router software setup.

## 2. Docker/containerd storage corruption

A `docker compose up` for the (pre-staged, partially-written) `openthread/otbr` container failed with:

```
failed to stat parent: stat /var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/snapshots/10/fs: no such file or directory
```

Root cause: a prior pull had run out of disk space mid-extraction (root partition was 92% full — `/var/cache/apt/archives` alone held 828MB of stale `.deb` files) and left corrupted containerd snapshot metadata referencing a directory that no longer existed. Fresh pulls of the *same* image kept hitting the same stale-metadata error even after clearing space, because the corruption was in containerd's own database, not just missing files.

**Fix:** `apt-get clean` (freed ~828MB), then fully reset containerd/docker local state (`systemctl stop docker containerd`, wipe `/var/lib/containerd/*` and `/var/lib/docker/*`, restart both) since nothing was running yet and it was safe to do. Re-pulled cleanly afterward.

## 3. First otbr container config bugs (openthread/otbr:latest)

Three separate issues surfaced getting the raw upstream `openthread/otbr:latest` image running:

1. **Wrong backbone-interface env var.** The compose file used `INFRA_IF_NAME=end0` — but this image's actual entrypoint script (`/app/etc/docker/test/docker_entrypoint.sh`) reads `BACKBONE_INTERFACE`, not `INFRA_IF_NAME` (that var only exists as a Dockerfile *build* arg, baked in at image build time — irrelevant at runtime). It silently defaulted to `eth0`, which doesn't exist on this box (`end0` is the real interface name). Confirmed by grepping the entrypoint script inside the container.
2. **Serial device symlink didn't map into the container.** `docker-compose.yml` mapped the *stable* `/dev/serial/by-id/usb-SONOFF_...` symlink path via `devices:`. Docker's device mapping doesn't resolve symlinks the way you'd hope — the destination path ended up empty inside the container, and otbr-agent failed with `hdlc_interface.cpp:154: No such file or directory`. Fixed by mapping the real device node `/dev/ttyUSB0` directly instead.
3. **Missing kernel module for the firewall step.** otbr-agent's startup firewall setup (`ip6tables -N OTBR_FORWARD_INGRESS`) failed with `Table does not exist` — the `ip6table_filter` kernel module wasn't loaded. The container's own `sudo modprobe ip6table_filter` silently failed (no `sudo` binary in the image). Loaded the module directly on the host (`modprobe ip_tables iptable_filter ip6table_filter ip6table_nat iptable_nat`), and made it persistent via `/etc/modules-load.d/openthread-border-router.conf` so it survives reboots.

With those three fixed, otbr-agent connected to the RCP, became Thread `leader`, and started advertising `_meshcop._udp` over mDNS.

## 4. Web UI / REST API bound to loopback only

The container's web UI (port 80) and REST API (port 8081) both defaulted to `127.0.0.1` — reachable via `curl localhost` *inside* the container/host, but refused from anywhere else on the LAN, including from Home Assistant. Root cause: `HTTP_HOST` env var (which also feeds the REST listen address) defaults to `127.0.0.1` in this image's entrypoint script. Fixed with `HTTP_HOST=0.0.0.0`.

## 5. Accidentally formed a public/insecure Thread network

After getting the web UI reachable, a "Form Network" click through the OTBR web UI's own form (which ships with the OpenThread project's well-known **tutorial/demo dataset pre-filled** — network key `00112233445566778899aabbccddeeff`, network name `OpenThreadDemo`, PAN ID `0x1234`, ext PAN ID `1111111122222222`) replaced the properly-random network that had been formed via `ot-ctl`. These are values published in every OpenThread getting-started guide — not safe to leave live. Re-formed a fresh network with real random credentials via:

```
ot-ctl dataset init new
ot-ctl dataset commit active
ot-ctl ifconfig up
ot-ctl thread start
```

**Lesson for the write-up:** don't use the OTBR web UI's "Form Network" button as-is; either edit every field or form the network via `ot-ctl`.

## 6. HA said "No border routers were found" despite a healthy, correctly-advertising border router

This was the long middle section of the day. Order of investigation:

1. Manually created an `otbr` Home Assistant integration entry pointing at `http://<pi-ip>:8081` — it loaded successfully (`state: loaded`) but created **zero devices/entities**, and the Thread panel still showed no border router.
2. Chased a theory that the REST API's `/node/dataset/active` endpoint ignores the `Accept: application/octet-stream` header HA's `python-otbr-api` client is believed to send, always returning JSON instead of raw TLV bytes. Verified this behaviour, but it turned out to be true of the community-recommended replacement image too (see next step) — a red herring, not the actual fix.
3. Root-caused (via web search) that the raw `openthread/otbr:latest` Docker Hub image runs the OpenThread project's internal **`test`** entrypoint flavour (there are two shipped inside the image: `test` and `border-router`; only `test` is wired as the actual container ENTRYPOINT on the published tag) — essentially a CI/demo build, not the flavour real HA users run in production. Confirmed via community reports of the exact same "no border routers found" / flaky-disappearing symptom with this image and Home Assistant.
4. **Switched to `ghcr.io/ownbee/hass-otbr-docker`** — a community image built directly from Home Assistant's own official add-on source (carries the HA-team's own patches for compatibility). Pinned to a specific tag (`arm64-v0.3.0`), not `latest`, since the upstream image being effectively a rolling/nightly build was part of what caused trouble above.
   - Different env var names for this image: `DEVICE`, `BACKBONE_IF`, `BAUDRATE`, `FLOW_CONTROL`, `FIREWALL`, `NAT64`, `OTBR_REST_PORT`, `OTBR_WEB_PORT` (7586 by default, not 80), `AUTOFLASH_FIRMWARE=0` (RCP already flashed correctly, don't let it try to reflash).
   - Different persistent-data path too: `/data/thread`, not `/var/lib/thread`. Copied the existing dataset files across before switching so the network wasn't lost.
   - Radio failed to init on first boot with this image (`Wait for response timeout`, `Init() Failure`) — traced to `FLOW_CONTROL: 1` in the reference compose example. This Sonoff dongle doesn't actually support/need UART hardware flow control (the original working setup never enabled it). Set `FLOW_CONTROL: 0` and the radio came up cleanly.
   - This image's mDNS advertisement literally announces itself as `Home Assistant OpenThread Border Router` (vendor-name-aware), vs. the raw upstream image's generic `OpenThread BorderRouter` — a good sign it's built with HA compatibility specifically in mind.
5. Even with the better image, HA *still* showed nothing. Investigated whether HA (a cloud VM reached over the L2 VPN) was even receiving multicast/mDNS traffic at all. Evidence gathered:
   - **Unicast worked fine** — HA's backend successfully made an outbound HTTP call to the border router's REST API during integration setup.
   - **No zeroconf-discovered integration had appeared on this HA instance in 7+ months** (checked every config entry's `source` field and `created_at`) — the most recent was a printer in January. Also found an existing Google Cast device stuck `unavailable` (Cast relies on live mDNS presence).
   - This pointed at multicast specifically not crossing the VPN link, independent of anything Thread/OTBR-specific — flagged this clearly to Vome's network team with concrete evidence rather than a vague "it's not discovering."

## 7. Root cause found by Vome's network team: IPv6 multicast blackholed by IGMP/MLD snooping

Vome's diagnosis (their words, kept verbatim since it's a good explanation for the write-up):

> Multicast was traversing the link — just not IPv6. The bridge had IGMP/MLD snooping on with no querier, which blackholes IPv6 multicast toward the tunnel port. IPv4 is immune because 224.0.0.0/24 is flooded whatever snooping says. That's why this hid so well: every check that looks at IPv4 mDNS reports the link healthy. Meanwhile Thread, Matter and anything else IPv6-native is never discovered.
>
> Enabling a querier — the tidier fix — didn't work: still zero. Disabling snooping did, immediately. So multicast now floods, which on a home LAN is low volume and the tunnel is nowhere near its limit at 293 Mbps.

This is a great, non-obvious gotcha for the write-up: **IPv4 mDNS working is not evidence that IPv6 mDNS works** — they can be handled completely differently by network switches/bridges doing IGMP/MLD snooping, and Thread/Matter are IPv6-native, so this specific failure mode is invisible to almost any "check mDNS is working" test that doesn't specifically test IPv6.

## 8. Verifying the fix, and a false negative caused by our own testing

After the network fix, several rounds of "restart OTBR to force a fresh mDNS announcement, check HA" came back negative — including one full Home Assistant Core restart (which itself got stuck mid-boot at 343/354 components for several minutes before finishing — just needed patience, not intervention).

The border router briefly *did* appear in HA's Thread panel, then vanished again. Best explanation: rapid back-to-back container restarts during testing each send an mDNS "goodbye" (withdrawal) packet for the old service instance right before re-registering — so once multicast started working, HA likely caught a withdrawal from one of our *own* test restarts moments after discovering it. Lesson: once multicast is confirmed working, stop restarting things repeatedly and let it settle — the churn itself was masking success. On the next single, isolated restart, it appeared and stayed.

Note: even once visible in the Thread panel, an explicit `otbr` domain config entry never persisted via the API in our checks — the panel can apparently show a live zeroconf-discovered border router directly from the browse results, distinct from (and without requiring) a saved integration entry. Worth digging into further for the KB article, since it wasn't fully clear whether that's expected end-state behaviour or a sign something's still not 100% wired up.

## 9. Matter-over-Thread commissioning failure — two separate causes

Tried commissioning an IKEA Kajplats (Matter-over-Thread) via the Home Assistant companion app. Failed instantly on QR scan with a generic "something went wrong."

**Cause 1 — no Thread credentials reaching Matter.** Even with the border router visible in the Thread panel, there was no persisted `otbr` integration link, so HA's Matter server had no automatic path to the Thread operational dataset. Home Assistant's Matter integration has a "Thread credentials" section under its config that wants the *raw TLV-encoded dataset as one hex string* (not the individual Network Key / PAN ID / etc. fields) — get this via:

```
ot-ctl dataset active -x
```

Pasting that hex string into the "Dataset" field is what Matter's commissioner hands to new Thread devices during pairing.

**Cause 2 (the real blocker, found after Cause 1 didn't fully fix it) — no Bluetooth anywhere in the commissioning path.** Matter commissioning goes: scan QR → connect via Bluetooth → (only then) hand off WiFi/Thread credentials → device joins network. Failing *instantly* at QR scan meant it never even got to Bluetooth — a strong clue the failure was upstream of Thread entirely.

- Home Assistant's companion app *can* offload BLE commissioning to the phone's own Bluetooth — but **only on iOS**, via Apple's native Matter/Home framework. On **Android**, the app still routes commissioning through the server's own Bluetooth stack regardless of using the native app. User confirmed Android — this fully explained the instant failure, independent of anything else.
- GamlaBio's Home Assistant runs in a Vome-hosted cloud VM with **no physical Bluetooth hardware** — so server-side BLE commissioning had nowhere to go.

Two ways to unblock this: (a) commission via an ecosystem that does full native Android Matter commissioning (e.g. Google Home app), then use Matter's multi-admin "share device" flow to hand it to Home Assistant afterward — no server BLE needed, but not a great long-term pattern; or (b) run Matter Server itself somewhere with real Bluetooth hardware and point HA's Matter integration at it remotely. Went with (b), since the Orange Pi is right there and (per the next section) does have real onboard Bluetooth once its firmware is fixed.

## 10. Fixing the Orange Pi's onboard Bluetooth

The Pi has an onboard Unisoc UWE5622 WiFi+Bluetooth combo chip (Armbian's systemd units for it are oddly named `aw859a-wifi.service` / `aw859a-bluetooth.service` — a generic/reused service name across several different Orange Pi board variants' BSP packages, not actually the right chip vendor name for this specific board). `aw859a-bluetooth.service` was in a **failed** state.

Running the attach command manually (`hciattach_opi -s 1500000 /dev/ttyBT0 sprd`) surfaced the real problem: it was trying to load `/lib/firmware/bt_configure_pskey.ini` and `/lib/firmware/bt_configure_rf.ini`, and finding neither. Checking `dmesg` also showed the WiFi side of the same combo chip failing to load `/lib/firmware/wifi_2355b001_1ant.ini` at boot (`WIFI_CMD_DOWNLOAD_INI`, `LOAD_INI_DATA_FAILED`) — **all three vendor calibration files were simply missing from this Armbian image.** Since this box has always been wired (no WiFi use), nobody had noticed.

Found the exact files in Orange Pi's own official firmware repo, [`orangepi-xunlong/firmware`](https://github.com/orangepi-xunlong/firmware) on GitHub, and pulled just those three small text files directly (a few KB each) rather than installing Armbian's `armbian-firmware-full` package, which would have been a ~700MB download / ~2.1GB installed — more than the entire free space on this box's 3.5GB disk, and mostly firmware for hardware this board doesn't have.

```
curl -sL -o /lib/firmware/wifi_2355b001_1ant.ini   https://raw.githubusercontent.com/orangepi-xunlong/firmware/master/wifi_2355b001_1ant.ini
curl -sL -o /lib/firmware/bt_configure_pskey.ini    https://raw.githubusercontent.com/orangepi-xunlong/firmware/master/bt_configure_pskey.ini
curl -sL -o /lib/firmware/bt_configure_rf.ini       https://raw.githubusercontent.com/orangepi-xunlong/firmware/master/bt_configure_rf.ini
```

Restarting the two systemd services with the files present got further (they were now actually being read) but *still* timed out — because the chip had already crashed at boot (`sprdwl_init_fw failed!`, `WCN_ERR: start_marlin SDIO card dump`), before the firmware files existed, and was left in a wedged state that a service restart alone couldn't clear. **A full reboot** was needed to let the chip initialize cleanly from cold with the firmware now in place.

Confirmed working after reboot:

```
hci0: Type: Primary  Bus: UART
	BD Address: 71:F3:A8:02:E3:27
	UP RUNNING
	Manufacturer: Spreadtrum Communications Shanghai Ltd (492)
```

The border router container came back up automatically after the reboot too (`restart: always` + Thread dataset on a persistent volume), confirming that part of the setup is properly durable across reboots.

---

## 11. Standalone Matter Server on the Orange Pi, using its now-working Bluetooth

With the Pi's onboard Bluetooth working, the cleanest fix for the Android/no-server-BLE problem was to stop relying on GamlaBio's (Bluetooth-less) hosted Matter Server add-on entirely, and instead run Matter Server as its own standalone service right next to the border router — exactly the architecture Home Assistant's own `python-matter-server` project supports for non-HAOS setups, and the same pattern referenced in the `ownbee/hass-otbr-docker` project's example compose file.

Added a second service to the same `~/otbr/docker-compose.yml` used for the border router:

```yaml
  matter-server:
    container_name: matter-server
    image: ghcr.io/home-assistant-libs/python-matter-server:stable
    restart: unless-stopped
    privileged: true
    network_mode: host
    security_opt:
      - apparmor:unconfined
    volumes:
      - /root/otbr/matter_data:/data
      - /run/dbus:/run/dbus:ro
    command: >
      --storage-path /data
      --paa-root-cert-dir /data/credentials
      --bluetooth-adapter 0
      --primary-interface end0
```

Notes on the config:
- `network_mode: host` + `privileged: true` — needed for proper multicast/mDNS operation and Bluetooth access.
- `/run/dbus:/run/dbus:ro` — Matter Server talks to Bluetooth via BlueZ over D-Bus, not raw HCI directly, so the host's D-Bus socket needs to be shared in. Confirmed `bluetooth.service` (bluetoothd) was actually running on the host first — it wasn't obviously visible in a service list at a glance, worth checking explicitly with `systemctl status bluetooth`.
- `--bluetooth-adapter 0` — use `hci0`, now working after the firmware fix in the previous section.
- `--primary-interface end0` — same backbone interface as otbr, for correct link-local address selection.

First `docker compose up` attempt appeared to hang for a couple of minutes at "Container matter-server Creating" — turned out to just be genuinely slow (privileged container setup + D-Bus/device wiring on this SBC's storage), not actually stuck; the shim process was alive under it the whole time. Came up cleanly on its own.

Startup log confirmed:
- CHIP/Matter controller stack initialized, fabric admin allocated
- Fetched PAA root certificates (74 from DCL, 2 from Git) and vendor info (833 vendors) — confirms outbound internet access is fine
- `Matter Server successfully initialized`
- Listening on `0.0.0.0:5580` and `[::]:5580` (WebSocket API)
- One harmless-looking transient error during startup (`Failed to advertise records... Network is unreachable`) — most likely from the newly-appeared (but unconfigured/unused) `wlan0` interface exposed by fixing the Bluetooth/WiFi combo chip's firmware; didn't stop the server from initializing successfully.

**Pointing Home Assistant at it:** the existing `matter` integration entry (originally auto-configured by the HAOS Matter Server add-on, `source: hassio`) reported `supports_reconfigure: false` and `supports_options: false` via the API — looked like it might need deleting and recreating. In practice, starting a *fresh* config flow for the `matter` domain (`handler: matter`) presented the classic "Do you want to use the add-on?" step; answering `false` led to a manual URL field (defaulting to `ws://localhost:5580/ws`), and submitting `ws://192.168.1.7:5580/ws` there **updated the existing entry in place** (`reason: reconfiguration_successful`) rather than creating a duplicate — despite the API describing that entry as not supporting reconfigure. Worth a line in the KB article: the config-flow route works for repointing Matter Server even when the entry's own metadata suggests it shouldn't.

Confirmed: same `entry_id`, fresh `modified_at` timestamp, `state: loaded`, no errors.

**Next to verify:** retry commissioning the IKEA Kajplats now that there's real Bluetooth in the chain end to end.

---

## 12. Matter Server on the Pi wasn't actually being used — and a much better fix existed all along

Tried commissioning the IKEA Kajplats again the next morning with the standalone Orange Pi Matter Server in place. Still instant failure. Investigation:

- `docker logs matter-server` on the Pi showed **zero connection attempts** in the prior 30+ minutes, and only a single stale entry from the night before (`No PONG received after 27.5 seconds` — a dropped WebSocket, right around when the manual reconfigure was done).
- Reloading the `matter` config entry, and even a live retry while tailing the Pi's logs, produced no new connection attempts at all — HA wasn't even trying to reach it.
- A full HA Core restart (same remedy that fixed the earlier zeroconf/Thread issue) didn't fix this one — after it came back up, still zero connection attempts reached the Pi.

While chasing that, checking the local Supervisor add-on's info (`GET /addons/core_matter_server/info`) surfaced something we should have found on day one: **a `ble_proxy` option**, description:

> "Expose the Matter Server's BLE proxy endpoint so the Home Assistant Matter integration can drive BLE commissioning through Home Assistant's own Bluetooth stack (including ESPHome BLE proxies). To actually use the BLE proxy you need Home Assistant 2026.06 or later."

This changes the whole picture. The actual, officially-supported fix for "Home Assistant has no Bluetooth hardware" turns out **not** to be "give some machine real Bluetooth and run Matter Server there" — it's this: newer Home Assistant/Matter-Server versions can drive commissioning through HA's own `bluetooth` integration, which already knows how to use **remote ESPHome Bluetooth proxies**. This home already has 8 of them deployed around the house for other purposes — much better physical BLE coverage near where devices actually get commissioned than a single Bluetooth radio on the Orange Pi could ever offer, and (critically) it goes through the server's Bluetooth stack, so it's **not gated on iOS vs Android** the way phone-side commissioning is.

Enabled it and switched back:

```
POST /addons/core_matter_server/options   {"options": {..., "ble_proxy": true}}
POST /addons/core_matter_server/restart
```

then re-ran the `matter` integration's config flow, answering `use_addon: true` this time (mirrors the earlier "manual URL" flow exactly, just the other branch) — confirmed via `reason: reconfiguration_successful`.

**Lesson for the write-up:** the whole detour through fixing the Orange Pi's onboard Bluetooth firmware (section 10) and standing up a standalone `python-matter-server` (section 11) was real, working, and taught a lot — but ended up being the *harder* path. Worth presenting both in the article: the "hard way" is legitimate and portable to setups without ESPHome Bluetooth proxies already deployed, but check for the `ble_proxy` add-on option first if you're on HAOS/Supervisor with existing Bluetooth proxy coverage — it's much less work.

## 13. HA version update (2026.7.4 → 2026.8.3) and a Thread "no border routers found" regression

Updated Home Assistant core the next morning (had been holding off after unrelated backup issues previously). After the update + restart, **the border router vanished from the Thread panel again** ("No border routers found") despite nothing having changed about the network/multicast fix from section 7 — and the underlying border router container itself was untouched, healthy, still `leader`, 11+ hours uptime, no crashes.

Same fix as before: restart the `otbr` container on the Pi to force a fresh mDNS re-announcement, timed *after* HA's own post-update restart had fully finished. Reappeared within about a minute.

This is now the second time an HA-side restart (whether from an update or a manual restart) has coincided with the border router needing a nudge to reappear, while the OTBR/network side never needed anything — worth flagging as a known pattern for the KB article: **after any Home Assistant restart or update, if Thread shows "no border routers found," try restarting the border router container before assuming something is actually broken.** Also re-confirms the section-8 finding: it shows up live in the Thread panel without ever creating a persisted `otbr` domain config entry via the API — this really does seem to be expected behaviour for this HA version, not a one-off glitch.

---

## 14. A smart watchdog for the "no border routers found" bug

Given section 13's finding is a genuinely unfixed upstream bug, restarting the `otbr` container is the only known remedy — the question was how to do that *only when actually needed*, rather than on a blind timer (which would mean unnecessary Thread-mesh blips for devices that don't need it).

**First, tried to find a lighter-than-a-full-restart way to force a fresh mDNS announcement**, since a full container restart briefly drops the Thread radio connection (~15-20s "detached → leader" reattach window each time):

- The container runs a **separate standalone `mdnsd` process** (Apple's open-source mDNSResponder, "Engineering Build"), managed as its own [s6](https://skarnet.org/software/s6/) service independent from `otbr-agent` — discoverable via `docker exec otbr ls /run/service/` (`mdns`, `otbr-agent`, `otbr-web`, ...). Tried bouncing just that (`s6-svc -r /run/service/mdns`) to force a re-announce without touching the Thread radio at all. The Thread state stayed `leader` throughout (confirmed — this part worked), but `otbr-agent` raced to reconnect to the not-yet-ready new `mdnsd` instance, got `Service Not Running` / `Invalid state` errors on its one attempt, and **didn't retry** — leaving the service completely unpublished until fixed with another restart. Not usable as-is.
- Tried `kill -HUP` on the `otbr-agent` process directly, hoping for a "reload" semantic. Instead, s6-overlay (the container's init system) treated it as a full restart trigger for the whole container — no better than `docker compose restart otbr`.

**Conclusion: no clean partial-refresh path exists** — a full container restart remains the only reliable fix. Worth being explicit in the article that this ~15-20s blip is much less disruptive than it might sound: it doesn't affect already-*commissioned* devices' ongoing operation (they talk to the mesh directly, not through HA's discovery-panel state), it only matters for the admin panel and for commissioning brand-new devices during that exact window.

**Built a watchdog that actually checks Home Assistant**, rather than restarting blind. The relevant Home Assistant websocket API is `thread/discover_routers` — a *subscription* command (not a simple request/response): after acking, HA streams `router_discovered` / `router_removed` events as its zeroconf listener sees them. Found the command name via a public gist of HA websocket commands and confirmed the shape by just running it. One implementation gotcha: the `router_discovered` event for an already-known router can arrive *before or interleaved with* the subscription's own `result` ack — don't assume strict ordering.

Script (`/root/otbr/watchdog/otbr_watchdog.py` on the Pi, Python + `python3-websockets` from apt — avoided `pip install` due to Debian's PEP 668 externally-managed-environment restriction, and avoided the much heavier `armbian-firmware-full`-style mistake from section 10 by reaching for the apt package first):

1. Connects to `ws://192.168.1.15:8123/api/websocket` (Home Assistant's *local* LAN address — reachable directly from the Pi since Vome's L2 VPN bridges the home network and the hosted instance together; no need to go through any relay/broker for this).
2. Authenticates with a Home Assistant long-lived access token (Profile → Security → Long-lived access tokens), stored in a `chmod 600` file, never committed anywhere.
3. Sends `thread/discover_routers`, listens for up to 8 seconds, and treats *any* `router_discovered` event as "still visible" (fine here since there's only one Thread border router on this network — a real multi-router deployment would want to match on `extended_pan_id`/`border_agent_id` from the event's `data` payload instead).
4. If nothing arrives in that window: restarts `otbr` via `docker compose restart otbr`, with a 10-minute cooldown between restarts so a run of failed checks can't cause restart-flapping.
5. Any error (HA unreachable, auth failure, etc.) is logged and treated as "don't restart" — never want a transient HA-side hiccup on *its* end to cause an unnecessary Thread-mesh blip on ours.

Runs via cron every 5 minutes (`*/5 * * * * /usr/bin/python3 /root/otbr/watchdog/otbr_watchdog.py >> /root/otbr/watchdog/cron.log 2>&1`).

## 15. Root cause of the whole multicast saga: a firewall issue, not just the earlier IGMP/MLD snooping fix

Vome's network team found a further firewall issue behind the ongoing flakiness (on top of the section 7 snooping fix) and resolved it. After that fix, the border router became consistently visible in the Thread panel and — notably — creating the `otbr` config entry via `ha_config_flow` (the same call that had never once actually persisted across the whole of sections 6-13, always ending up back at `count: 0` on the next check) **worked and stuck on the very first attempt**. Good evidence that at least some of the entry-not-persisting behaviour documented as an "open question" back in section 8 was this same firewall issue, not an inherent quirk of how HA's Thread panel displays discovery.

**A second-opinion diagnosis (from another troubleshooting agent) at this point claimed the border router had stopped advertising `_meshcop._udp` entirely** (zero packets in a 60s capture, despite other mDNS traffic on the LAN being fine) and suggested checking `avahi-daemon` and which interface `otbr-agent` was publishing on. Worth recording *why* that diagnosis was superseded rather than acted on, since "conflicting reports, which do you trust" is a real scenario worth documenting:

- Re-ran our own watchdog script live and got an immediate `router_discovered` event back from HA, with `192.168.1.7` (the real LAN address) in the resolved `addresses` list — direct proof it was both currently advertising *and* being received, at the exact time the other report claimed zero packets. A 60-second capture window can simply land between two mDNS re-announcements (services don't need to continuously rebroadcast once cached) — a plausible, mundane explanation for a conflicting negative result, not evidence of a real fault.
- The `avahi-daemon` suggestion doesn't apply to this setup at all: `ownbee/hass-otbr-docker` bundles Apple's own `mdnsd` (mDNSResponder) as a separate service, not `avahi` — confirmed nothing avahi-related is even installed on the host.
- The wrong-interface (`wpan0`) theory is directly contradicted by the same `addresses` field above — a Thread-only interface could never produce a real LAN IP in that list.

**Lesson for the write-up:** always weigh a diagnosis against your own freshest first-hand evidence before acting on it, especially in a system with a documented history of intermittent behaviour — a stale or mistimed test can look exactly like a real regression. That said, the second opinion's *sharper* underlying point — "being visible in the Thread panel isn't the same as HA having the dataset" — was correct and worth listening to on its own merits; it's what prompted re-checking (and this time, successfully creating) the `otbr` config entry.

## 16. Kajplats still saying it "needs a Border router" — HA already had one

Tried commissioning the IKEA Kajplats again. Same Android error: "Your device requires a Thread border router" / "needs a Border router." First instinct is that the OTBR has vanished again (sections 6, 8, 13). It hasn't. Live checks this time:

- Orange Pi OTBR container healthy, Thread `leader`, network `OpenThread-2729`, same extended PAN ID / border-agent ID as before.
- Watchdog still getting `router_discovered` from HA every 5 minutes, with `192.168.1.7` plus the IPv6 addresses in `addresses`.
- HA Thread dataset store has exactly one dataset, **preferred: true**, `source: otbr`, preferred border agent matching the live OTBR. The stored TLV matches `ot-ctl dataset active -x` byte-for-byte.
- `otbr` config entry still loaded (the one that finally persisted in section 15). Matter add-on running (`ble_proxy: true`, version 9.2.0). Official HA OTBR *add-on* is installed but **stopped** with `device: null` — that's the leftover Supervisor app, not the Pi. It is *not* the border router the Thread panel is using.

So this is not the "no border routers found" bug. HA already has a preferred Thread network and can see the Pi. The Kajplats error is the well-known **Android companion-app / Google Play Services** one: Matter-over-Thread commissioning on Android goes through Google's Thread stack, which looks for a Google-recognised TBR on the phone. Home Assistant's OTBR does not count until the phone holds the same dataset. The HA Android app does **not** sync those credentials automatically any more (removed in companion-app PR #4150). Same error text, same Kajplats reports, same fix: **Settings → Companion app → Troubleshooting → Sync Thread credentials**, then pair again. Google Home Mini speakers in this house are *not* Thread border routers, so they cannot satisfy that check either.

Two server-side cleanups still worth doing, because they can make that sync/pair step fail even after the user taps the button:

1. **Leftover standalone `matter-server` on the Pi was still running** (the section 11 detour, abandoned in section 12 when we switched back to the HA add-on). It was bound to UDP 5353 on IPv4, IPv6 and several unicast addresses alongside OTBR's `mdnsd`, and it was advertising `_matter._tcp` — a second, unused Matter fabric on the same host. Stopped it, set `restart: "no"`, and parked the compose service behind `profiles: ["unused"]` so a later `docker compose up -d` cannot bring it back by accident. After the stop: `_meshcop._udp` and `_trel._udp` still answer from `192.168.1.7`; `_matter._tcp` is gone; HA still discovers the border router; only `mdnsd` owns port 5353.
2. **Pushed the preferred dataset into the HA Matter Server** with `matter/set_thread` (same TLV HA already had in the Thread store). The add-device flow is supposed to do this itself, but BLE-proxy commissioning (HA 2026.6 + add-on `ble_proxy`) needs the Matter Server to already hold the operational dataset so it can hand Thread credentials to the Kajplats without going through Google Play Services at all.

**To pair the Kajplats now (Android):**

1. Phone on the same home Wi-Fi as the Orange Pi (not guest Wi-Fi, not mobile data).
2. Companion app: Settings → Companion app → Troubleshooting → **Sync Thread credentials**. Expect a confirmation that HA's Thread credentials were added to the phone.
3. If it still says no border router: Android may be clinging to an empty Google Thread network. Clear Google Play Services storage/cache, repeat the sync, then retry.
4. Alternative that skips the phone's Thread stack: put the Kajplats in pairing mode next to an ESPHome Bluetooth proxy (`bluetooth_proxy: active: true` is already on several of them), then add it from HA with the setup code so Matter Server uses BLE proxy + the dataset we just pushed.

Compose file for the Pi is now also in this folder (`docker-compose.yml`) so the "don't auto-start matter-server" pin is versioned.

## 17. Stuck on "checking connectivity to Thread network OpenThread-2729"

After the Android credential sync, commissioning got past "needs a border router" and hung on **checking connectivity to Thread network OpenThread-2729**.

Live evidence that this was not a missing radio / missing dataset problem:

- A second Thread router (`5a1ca712b5205e2c`, RLOC `0x6800`, RSSI around −68 dBm, Thread version 5) appeared in the OTBR neighbor/router table over 802.15.4 while the phone was on that screen — the Kajplats *did* join the mesh.
- Border-router dataplane counters were all zero: inbound/outbound unicast and multicast packets **0**. The OTBR firewall FORWARD chains had also never seen a packet.
- `trel` was enabled but had zero peers and zero packets (Android often uses TREL over Wi-Fi for this check; it never got a path).
- Host sysctls: `net.ipv4.ip_forward = 1` already, but **`net.ipv6.conf.all.forwarding = 0`** (and the same on `end0` / `wpan0`). That is the well-known cause of this exact hang: the device can attach on 15.4, then the phone/HA tries to reach it via the OMR prefix (`fd54:508a:5479:1::/64`) and the kernel refuses to forward IPv6 between LAN and `wpan0`.

Docker cannot fix this for us. `network_mode: host` means compose `sysctls:` are ignored, so the ownbee container never turned forwarding on. IPv4 forwarding had been enabled some other way; IPv6 had not.

**Fix** (applied live, persisted in `/etc/sysctl.d/99-openthread-border-router.conf` on the Pi, copy in this folder):

```
net.ipv6.conf.all.forwarding = 1
net.ipv6.conf.default.forwarding = 1
net.ipv6.conf.end0.accept_ra = 2
net.ipv6.conf.end0.accept_ra_rt_info_max_plen = 64
```

`accept_ra = 2` is required so the Pi keeps learning its LAN default route / global prefix from the home router after it becomes an IPv6 forwarder (kernel treats `accept_ra` as 0 whenever forwarding is on, unless it is explicitly 2).

Verified after apply: `end0` and `wpan0` forwarding both 1, existing RA-learned routes still present. The Kajplats router entry had already gone stale (`Link: 0`, ping to `…:6800` lost) — expected once the failed commissioning attempt timed out. Retry needs a factory-reset of the bulb if it no longer advertises for pairing.

HA's LAN NIC (`enp7s0`) already has working IPv6 (`fda8:af1d:5493:…` and a global `2001:2042:…` address, method auto). Matter Server is `host_network: true`, so once the Pi forwards, the remaining path is OTBR RA/RIO → phone and HA.

## 18. Kajplats commissioned

Worked on the next attempt after the IPv6 forwarding fix. Device on GamlaBio:

- `KAJPLATS E14 WS globe 806lm` → `light.kajplats_e14_ws_globe_806lm` (colour temperature + xy)
- Joined Thread as a router (new neighbour `3a18313c9a264167`, RLOC `0x2000`, RSSI around −67 dBm)
- OTBR `br counters` immediately showed real LAN↔mesh traffic (hundreds of unicast packets in both directions) — the proof that forwarding was the missing piece, not the radio or the dataset
- Matter firmware OTA to 1.2.0 started on its own right after pairing

Android path that actually worked: Sync Thread credentials (section 16) → add device in the companion app, with IPv6 forwarding on the Pi (section 17).

Operational notes (what to keep, what not to start, how to add the next bulb) now live in `README.md`. Compose / sysctl / watchdog / iptables-module files in this folder match what is on the Pi, except the HA long-lived token which stays on the Pi at `chmod 600`.

---

## Open items for the write-up

- Why did the Thread panel show the border router live before an `otbr` config entry ever persisted via the API? Worth a clean-room retest to describe accurately.
- The January 2026 "zeroconf discovery stopped working" mystery (predates the VPN link entirely by ~7 months) — flagged by Vome as unexplained and unrelated to the multicast/snooping fix. Separate investigation if pursued.
- The Google Cast device stuck `unavailable` — Vome's read is this is IPv4 mDNS (which was never broken) and needs separate diagnosis, not covered by any fix here.
- Good "gotcha" pull-quotes for a blog post: the IPv4-vs-IPv6-multicast blind spot, the OTBR web UI's demo-credentials trap, the Android-vs-iOS Matter/BLE commissioning asymmetry, **Android "needs a border router" meaning the phone lacks HA Thread credentials**, and **IPv6 forwarding=0 causing "checking connectivity to Thread network" after the device has already joined the mesh**. Docker `sysctls:` are ignored with `network_mode: host`, so this has to be a host `/etc/sysctl.d/` file.
