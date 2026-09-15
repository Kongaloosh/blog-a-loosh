#!/usr/bin/env bash
# Keep GoToSocial running until user systemd is available (see deploy/gotosocial).
set -u
G=/mnt/volume-nyc1-01/gotosocial
exec 9>/tmp/gotosocial-watchdog.lock; flock -n 9 || exit 0
if curl -fsS --max-time 10 -o /dev/null http://127.0.0.1:8080/readyz; then exit 0; fi
echo "$(date '+%F %T') gotosocial not ready - starting" >> "$G/watchdog.log"
# Find the instance by who owns the port. Matching command lines has misled
# every check today: a relative invocation, or the invoking shell itself.
PIDS=$(ss -ltnp 'sport = :8080' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u | tr '\n' ' ')
[ -n "$PIDS" ] && kill $PIDS 2>/dev/null; sleep 3
# Absolute paths, detached from this shell.
GOMEMLIMIT=384MiB setsid nohup "$G/current/gotosocial" --config-path "$G/config.yaml" server start >> "$G/gotosocial.log" 2>&1 < /dev/null &
sleep 10
curl -fsS --max-time 10 -o /dev/null http://127.0.0.1:8080/readyz && echo "$(date '+%F %T') started" >> "$G/watchdog.log" || echo "$(date '+%F %T') START FAILED" >> "$G/watchdog.log"
