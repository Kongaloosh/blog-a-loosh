# A native fediverse account at kongaloosh.com (GoToSocial)

Goal: `@alex@kongaloosh.com` as a real ActivityPub account you can log into
from any Mastodon client, with the 113 followers of the Bridgy Fed bridged
site moved over rather than lost, and the blog posting to it.

Server: GoToSocial v0.22.1 (standard build; the `nowasm` variant is marked
unsupported by the project), installed
under `/mnt/volume-nyc1-01/gotosocial/` (binary, config, SQLite DB, media).
It listens on 127.0.0.1:8080; nginx fronts it at `social.kongaloosh.com`;
accounts are named at the bare domain via `account-domain: kongaloosh.com`.

## Order of operations (the order matters)

1. **DNS** (you): A record `social.kongaloosh.com -> 198.211.97.145`.
2. **nginx + TLS** (root): install `nginx-social.kongaloosh.com.conf` into
   `/etc/nginx/conf.d/`, `nginx -t`, reload, then
   `certbot --nginx -d social.kongaloosh.com`.
3. **Run it** (deploy): user systemd if linger is enabled, else the cron line
   `* * * * * /home/deploy/kongaloosh/scripts/gotosocial_watchdog.sh`.
   Check `https://social.kongaloosh.com/api/v1/instance`.
4. **Create the account** (done 2026-09-14: `alex`, email alex@kongaloosh.com, confirmed + admin; initial password in ~/.gotosocial-alex-initial-password, change it after first login):
   ```
   cd /mnt/volume-nyc1-01/gotosocial
   ./current/gotosocial --config-path config.yaml admin account create \
       --username alex --email alex@kongaloosh.com --password '<strong password>'
   ./current/gotosocial --config-path config.yaml admin account promote --username alex
   ```
   Log in at `https://social.kongaloosh.com/settings` and fill in the profile.
5. **Alias the old identity** (you, in the GoToSocial settings UI): Settings ->
   Migration -> "Alias account" -> add `https://fed.brid.gy/kongaloosh.com`.
   Mastodon-style Move is only accepted if the new account lists the old one.
6. **Hand over discovery** (root): apply `nginx-wellknown-handoff.snippet` to
   the kongaloosh.com server block; reload. Verify:
   `curl 'https://kongaloosh.com/.well-known/webfinger?resource=acct:alex@kongaloosh.com'`
   returns the GoToSocial account.
7. **Move the followers** (you, on fed.brid.gy): the bridged site's settings
   page -> migrate to `@alex@kongaloosh.com`. Bridgy Fed sends a Move; the
   113 followers' servers re-follow the new account automatically. Bridgy Fed
   then disables the bridged site. This step is not reversible.
8. **Blog posts to it**: in GoToSocial's settings panel, *Applications* ->
   create an application (scopes: write:statuses, write:media) and copy its
   access token (verified: the panel issues tokens without the CLI or the
   OAuth dance). Put it in `config.ini` under `[Fediverse]`; the blog's
   syndication step then posts via the Mastodon API (statuses + media), and
   the webmention to fed.brid.gy is removed from the code.

## Operating it
- Find the process by port, never by command-line pattern:
  `ss -ltnp 'sport = :8080'`. Always start it by absolute path
  (`/mnt/volume-nyc1-01/gotosocial/current/gotosocial --config-path /mnt/volume-nyc1-01/gotosocial/config.yaml server start`).
- First boot replays ~150 migrations and takes ~25s before `/readyz` is 200;
  `/livez` answers earlier from a temporary server. That handoff logs a
  "shutting down http server" line - it is not a crash.

## Memory (measured 2026-09-14)
- Idle RSS is ~400MB (413MB, 403MB with GOMEMLIMIT=384MiB). That is the
  embedded WebAssembly ffmpeg runtime, not the Go heap - the `nowasm` build
  idled at 15MB but the project marks it unsupported. Budget 400MB.
- The box has 1967MB and **no swap**; gunicorn uses ~280MB and the video
  worker's ffmpeg spikes during a conversion. Before running GoToSocial
  permanently, add swap (root):
  `fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`
  and `/swapfile none swap sw 0 0` in /etc/fstab.
- GOMEMLIMIT=384MiB is set by the unit and the watchdog; it is harmless and
  keeps the Go heap honest even though it does not touch the WASM memory.

## Notes
- `host` and `account-domain` are baked into the DB on first run; if the
  subdomain changes before go-live, delete `db/sqlite.db` and start again.
- Backups: `db/sqlite.db` and `storage/` (both on the volume).
- Upgrades: download the new `linux_amd64` tarball into `releases/`, extract to
  `vX.Y.Z/`, repoint the `current` symlink, restart. Read the release notes;
  minor versions sometimes need `admin migrations run`.
