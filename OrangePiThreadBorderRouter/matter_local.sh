#!/bin/bash
# Move the Matter controller from GamlaBio Hosted's Matter Server add-on to
# the Orange Pi (matter.js server 1.4.0, the version add-on 9.2.0 bundles).
#
# Why (2026-10-05): the hosted add-on reaches the Thread devices over the
# HomeLink VPN. Short link drops kill its subscriptions; BILRESA remotes
# (15 min interval) then stay cut off for up to 15.5 min and their presses
# arrive late in a burst. Run locally, the Matter subscriptions never cross
# the VPN; only HA's WebSocket to this server does, and that reconnects in
# seconds. Full runbook: MATTER_LOCAL_MIGRATION.md.
#
# Usage (on the Pi, as root):
#   matter_local.sh unpack <backup.tar>
#                             unpack a partial HA backup of the add-on (made
#                             AFTER the add-on was stopped) into $DATA
#   matter_local.sh start     start the local server on the copied data
#   matter_local.sh status    container state, last log lines, port 5580
#   matter_local.sh stop      stop the local server (rollback step 1)
#
# The Pi's HA token (watchdog) gets 401 on /api/hassio/*, so this script
# cannot back up or inspect the add-on itself: the backup is made via Vome
# (supervisor backups/new/partial), downloaded from Settings → System →
# Backups and copied here. "start" will not run unless
# CONFIRM_ADDON_STOPPED=yes, because the add-on's state cannot be checked
# from here.
#
# Never run the local server while the add-on is running: both would act
# as the same Matter controller on the same fabric.

set -euo pipefail

DATA=${MATTER_DATA:-/root/otbr/matterjs_data}
WORK=${MATTER_WORK:-/root/otbr/matter_migration}
COMPOSE_DIR=/root/otbr
ADDON=core_matter_server
DOCKER=/usr/bin/docker

cmd_unpack() {
	local tarfile=${1:-}
	[ -f "$tarfile" ] || { echo "usage: $0 unpack <backup.tar>" >&2; exit 2; }
	rm -rf "$WORK/unpacked" "$WORK/addon" && mkdir -p "$WORK/unpacked" "$WORK/addon"
	tar -xf "$tarfile" -C "$WORK/unpacked"
	local inner
	inner=$(find "$WORK/unpacked" -maxdepth 1 -name "*${ADDON}*.tar*" | head -1)
	[ -n "$inner" ] || { echo "No $ADDON archive inside the backup:" >&2; ls -la "$WORK/unpacked" >&2; exit 1; }
	tar -xf "$inner" -C "$WORK/addon"
	[ -d "$WORK/addon/data" ] || { echo "No data/ in the add-on archive:" >&2; ls -la "$WORK/addon" >&2; exit 1; }
	if [ -d "$DATA" ]; then
		mv "$DATA" "$DATA.old-$(date +%Y%m%d-%H%M%S)"
	fi
	cp -a "$WORK/addon/data" "$DATA"
	chown -R 1000:1000 "$DATA"   # the image runs as uid 1000
	echo "Add-on data copied to $DATA:"
	du -sh "$DATA"
	ls -la "$DATA"
}

cmd_start() {
	[ -d "$DATA" ] || { echo "$DATA missing; run unpack first." >&2; exit 1; }
	if [ "${CONFIRM_ADDON_STOPPED:-}" != "yes" ]; then
		echo "Set CONFIRM_ADDON_STOPPED=yes once the $ADDON add-on is stopped." >&2
		exit 1
	fi
	cd "$COMPOSE_DIR"
	$DOCKER compose --profile matter-local up -d matterjs-server
	sleep 10
	cmd_status
}

cmd_status() {
	$DOCKER ps -a --filter name=matterjs-server --format '{{.Names}} {{.Image}} {{.Status}}'
	$DOCKER logs --tail 25 matterjs-server 2>&1 || true
	ss -tlpn | grep ':5580' || echo "nothing listening on 5580"
}

cmd_stop() {
	cd "$COMPOSE_DIR"
	$DOCKER compose --profile matter-local stop matterjs-server
	$DOCKER ps -a --filter name=matterjs-server --format '{{.Names}} {{.Status}}'
}

case "${1:-}" in
	unpack) shift; cmd_unpack "$@" ;;
	start) cmd_start ;;
	status) cmd_status ;;
	stop) cmd_stop ;;
	*) echo "usage: $0 unpack <backup.tar>|start|status|stop" >&2; exit 2 ;;
esac
