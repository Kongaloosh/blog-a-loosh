#!/usr/bin/env bash
# Restart the blog if it stops answering requests.
#
# This checks that the site actually responds, not merely that a process
# exists. The April outage left gunicorn running with every worker wedged and
# unable to accept connections, which Restart=always would never have caught.
#
# Works with or without user systemd: if the unit is loaded it restarts
# through systemd, otherwise it starts gunicorn directly. Run it from the
# kongaloosh-health.timer, or from cron until lingering is enabled.
set -u

APP_DIR=/home/deploy/kongaloosh
VENV=/home/deploy/.local/share/virtualenvs/kongaloosh-IfGDV1zi
HEALTH_URL="http://127.0.0.1:8500/"
UNIT=kongaloosh.service
LOCK=/tmp/kongaloosh-health.lock
LOG="${APP_DIR}/watchdog.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

exec 9>"$LOCK"
flock -n 9 || exit 0

cd "$APP_DIR" || { log "FATAL: cannot cd to $APP_DIR"; exit 1; }

if curl -fsS --max-time 20 -o /dev/null "$HEALTH_URL"; then
    exit 0
fi
log "health check failed"

if systemctl --user list-unit-files "$UNIT" >/dev/null 2>&1; then
    log "restarting via user systemd"
    systemctl --user restart "$UNIT"
else
    # No systemd for this user yet: stop whatever is left and start it by hand.
    PIDS=$(pgrep -f "${VENV}/bin/gunicorn" || true)
    if [ -n "$PIDS" ]; then
        log "stopping stale pids: $PIDS"
        # shellcheck disable=SC2086
        kill -TERM $PIDS 2>/dev/null || true
        sleep 8
        PIDS=$(pgrep -f "${VENV}/bin/gunicorn" || true)
        if [ -n "$PIDS" ]; then
            log "forcing: $PIDS"
            # shellcheck disable=SC2086
            kill -9 $PIDS 2>/dev/null || true
            sleep 2
        fi
    fi
    export TMPDIR=/mnt/volume-nyc1-01/tmp
    "${VENV}/bin/gunicorn" --config config.py \
        --access-logfile ./gunicorn-access.log \
        --error-logfile ./gunicorn-error.log \
        kongaloosh:app --daemon
fi

sleep 8
if curl -fsS --max-time 20 -o /dev/null "$HEALTH_URL"; then
    log "restart OK"
else
    log "RESTART FAILED - still not answering"
fi
