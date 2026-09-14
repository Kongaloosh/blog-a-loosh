#!/usr/bin/env bash
# Keep upload spooling off the root filesystem; see UPLOAD_TMPDIR in config.py.
export TMPDIR=/mnt/volume-nyc1-01/tmp

pipenv run gunicorn     --config config.py     --access-logfile ./gunicorn-access.log     --error-logfile ./gunicorn-error.log     kongaloosh:app
