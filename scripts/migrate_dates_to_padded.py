#!/usr/bin/env python
"""Normalise entry storage to zero-padded YYYY/MM/DD.

Posts were written under unpadded directories (data/2019/2/6/) until the
date format changed, leaving the archive split between two spellings. This
renames the unpadded directories, rewrites the url recorded inside each
entry, and updates the location column in the database.

Links to the old form keep working: the routes resolve either spelling and
redirect the unpadded one to the canonical URL.

Run without --apply first; it prints exactly what it would do.
"""

import configparser
import glob
import json
import os
import re
import shutil
import sqlite3
import sys

YEAR = re.compile(r"^\d{4}$")
NUM = re.compile(r"^\d{1,2}$")

config = configparser.ConfigParser()
config.read("config.ini")
BLOG_STORAGE = config.get("PhotoLocations", "BlogStorage")
DATABASE = config.get("Global", "database")


def unpadded_dirs():
    """data/<yyyy>/<m>/<d>/ where month or day lacks its leading zero."""
    found = []
    for path in sorted(glob.glob(f"{BLOG_STORAGE}/*/*/*/")):
        parts = path.rstrip("/").split(os.sep)
        if len(parts) != 4:
            continue
        _, year, month, day = parts
        if not (YEAR.match(year) and NUM.match(month) and NUM.match(day)):
            continue
        if len(month) == 2 and len(day) == 2:
            continue
        found.append((path.rstrip("/"), year, month, day))
    return found


def move_dir(src, dest):
    """Rename src to dest, merging if dest somehow already exists."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        os.rename(src, dest)
        return
    for name in os.listdir(src):
        target = os.path.join(dest, name)
        if os.path.exists(target):
            print(f"    collision, left in place: {os.path.join(src, name)}")
            continue
        shutil.move(os.path.join(src, name), target)
    if not os.listdir(src):
        os.rmdir(src)


def rewrite_urls(directory, year, month, day):
    """Point each entry's recorded url at the padded path."""
    old = f"/e/{year}/{month}/{day}/"
    new = f"/e/{year}/{int(month):02d}/{int(day):02d}/"
    for entry in glob.glob(os.path.join(directory, "*.json")):
        if entry.endswith(".meta.json"):
            continue
        try:
            with open(entry, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not str(data.get("url", "")).startswith(old):
            continue
        data["url"] = new + str(data["url"])[len(old):]
        tmp = entry + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        os.replace(tmp, entry)


def main(apply=False):
    targets = unpadded_dirs()
    print(f"unpadded directories: {len(targets)}\n")

    for src, year, month, day in targets:
        dest = os.path.join(BLOG_STORAGE, year, f"{int(month):02d}", f"{int(day):02d}")
        print(f"  {'moving' if apply else 'would move'} {src} -> {dest}")
        if apply:
            move_dir(src, dest)
            rewrite_urls(dest, year, month, day)

    # The database stores 'data/<yyyy>/<m>/<d>/<slug>' in entries.location.
    db = sqlite3.connect(DATABASE)
    rows = db.execute("SELECT id, location FROM entries").fetchall()
    updates = []
    for row_id, location in rows:
        if not location:
            continue
        # Some rows were written with a doubled separator ("data//2015/...").
        # POSIX collapses it on open, so they resolved fine and are easy to
        # miss - but they still need the date padded like any other row.
        parts = [p for p in str(location).split("/") if p]
        if len(parts) < 5 or not YEAR.match(parts[1]):
            continue
        normalised = "/".join(parts)
        if len(parts[2]) == 2 and len(parts[3]) == 2:
            if normalised != location:
                updates.append((normalised, row_id))
            continue
        parts[2], parts[3] = f"{int(parts[2]):02d}", f"{int(parts[3]):02d}"
        updates.append(("/".join(parts), row_id))

    print(f"\n  {'updating' if apply else 'would update'} {len(updates)} database rows")
    if apply and updates:
        db.executemany("UPDATE entries SET location = ? WHERE id = ?", updates)
        db.commit()
    db.close()

    if not apply:
        print("\nre-run with --apply")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
