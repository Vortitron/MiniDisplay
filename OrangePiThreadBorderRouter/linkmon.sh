#!/bin/bash
# Link monitor: Pi ↔ GamlaBio Hosted over the HomeLink L2 VPN.
#
# Why (2026-10-05): the Matter Server add-on on the hosted HA loses its
# subscriptions to every Thread device at the same moment, roughly hourly
# (seen ~20:17 and ~21:15). Mains lights recover in under 2 min; BILRESA
# remotes (15 min subscription interval) stay cut off up to 15.5 min.
# This logs every outage on the three paths Matter depends on, so the
# times can be matched against the Matter log and the VPN's own logs.
#
# Probes, once a second, each a single ping with a 1 s timeout:
#   v4      IPv4 to HA (192.168.1.15): the VPN link itself
#   v6      IPv6 to HA's ULA: IPv6 across the L2 bridge (MLD snooping
#           has broken IPv6 here before, see SETUP_LOG.md)
#   thread  IPv6 to HA *from the Pi's Thread-prefix address*, so the
#           reply needs HA's route to fd54:508a:5479:1::/64 (learnt from
#           the Pi's RA/RIO). This is the path Matter actually uses.
#
# Logs only transitions ("DOWN" with start time, "UP" with duration),
# plus an hourly heartbeat. Run as a transient unit:
#   systemd-run --unit=linkmon --property=Restart=always /root/otbr/linkmon/linkmon.sh
# Read:  tail -f /root/otbr/linkmon/linkmon.log
# Stop:  systemctl stop linkmon

HA4=192.168.1.15
HA6=fda8:af1d:5493:0:42af:fdc3:e6c1:71fc
THREAD_SRC=fd54:508a:5479:1:7d8a:5715:a8f6:1b7f
LOG=/root/otbr/linkmon/linkmon.log
MAX_BYTES=2000000

declare -A down_since
last_beat=0

log() {
	if [ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt "$MAX_BYTES" ]; then
		mv "$LOG" "$LOG.1"
	fi
	echo "$(date '+%F %T') $*" >> "$LOG"
}

probe() {
	case "$1" in
		v4) /usr/bin/ping -4 -c1 -W1 "$HA4" > /dev/null 2>&1 ;;
		v6) /usr/bin/ping -6 -c1 -W1 "$HA6" > /dev/null 2>&1 ;;
		thread) /usr/bin/ping -6 -c1 -W1 -I "$THREAD_SRC" "$HA6" > /dev/null 2>&1 ;;
	esac
}

log "start (v4=$HA4 v6=$HA6 thread_src=$THREAD_SRC)"
while true; do
	now=$(date +%s)
	for p in v4 v6 thread; do
		if probe "$p"; then
			if [ -n "${down_since[$p]}" ]; then
				log "UP   $p after $((now - down_since[$p]))s (down since $(date -d @"${down_since[$p]}" '+%T'))"
				unset "down_since[$p]"
			fi
		elif [ -z "${down_since[$p]}" ]; then
			down_since[$p]=$now
			log "DOWN $p"
		fi
	done
	if [ $((now - last_beat)) -ge 3600 ]; then
		log "heartbeat"
		last_beat=$now
	fi
	sleep 1
done
