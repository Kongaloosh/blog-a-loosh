# Running kongaloosh under user systemd

The site is started by hand today, which is why an outage in April went
unnoticed for four and a half months. These units put it under supervision.

Everything here is user-level and survives reboot, but enabling it needs
**one** root command, because lingering (running a user manager without an
active login session) can only be turned on by root.

## Install

```sh
# 1. as root, once - lets the deploy user's systemd run without a login
sudo loginctl enable-linger deploy

# 2. as deploy
systemctl --user daemon-reload
systemctl --user enable --now kongaloosh.service
systemctl --user enable --now kongaloosh-health.timer

# 3. remove the interim cron entries, now redundant
crontab -e   # delete the kongaloosh_health.sh lines
```

The unit files are already in `~/.config/systemd/user/`; this directory is
the copy kept in version control.

## Why there is a health timer as well as Restart=always

`Restart=always` only notices a process that has exited. The April outage
left gunicorn running with every worker blocked on a socket it could not
release, so the process was alive and the port was open while nothing was
being served. systemd would have seen a healthy service.

`kongaloosh-health.timer` fetches an actual page once a minute and restarts
the unit when that fails, which is the failure this site has actually had.

## Checking it

```sh
systemctl --user status kongaloosh.service
systemctl --user list-timers kongaloosh-health.timer
journalctl --user -u kongaloosh.service -n 50
tail -f ~/kongaloosh/watchdog.log       # health-check restarts
```

## Notes

- `ExecStart` deliberately omits `--daemon`: systemd supervises the process.
- `TimeoutStopSec=30` with `KillMode=mixed` overrides gunicorn's 300s
  graceful timeout, so a wedged worker cannot stall a restart for 5 minutes.
- `TMPDIR` points at the data volume; the root filesystem runs near full and
  uploads are buffered to it otherwise.
