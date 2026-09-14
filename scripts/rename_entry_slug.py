#!/usr/bin/env python
"""Give a published entry a new slug (and so a new URL).

Bridgy Publish never posts the same URL twice, even after the silo post is
deleted, so a post that went out wrong can only be redone under a new URL:
delete it on the silo, rename it here, announce again.

Media files keep their names - the entry's video/photo lists still point at
them - and nothing redirects the old URL. Dry run unless --apply is given.

    scripts/rename_entry_slug.py reef-shark reef-sharks --apply --announce
"""

import configparser
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

config = configparser.ConfigParser()
config.read("config.ini")
DATABASE = config.get("Global", "database")
DOMAIN = config.get("Global", "DomainName")


def main(old, new, apply=False, announce=False):
    if "/" in new or not new or new == old:
        sys.exit("new slug must be a single non-empty path segment different from the old one")

    db = sqlite3.connect(DATABASE)
    row = db.execute(
        "SELECT id, published, location FROM entries WHERE slug = ?", (old,)
    ).fetchone()
    if not row:
        sys.exit(f"no entry with slug {old!r}")
    entry_id, published, location = row
    directory = os.path.dirname(location)
    old_json, new_json = location + ".json", os.path.join(directory, new) + ".json"
    if not os.path.isfile(old_json):
        sys.exit(f"entry file missing: {old_json}")
    if os.path.exists(new_json):
        sys.exit(f"target already exists: {new_json}")

    with open(old_json, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("pending_media"):
        sys.exit("this entry is still waiting for its video: the worker holds its current "
                 "path and would lose track of it if renamed now. Wait until it is public.")
    old_url = data.get("url") or ""
    new_url = old_url.rsplit("/", 1)[0] + "/" + new if old_url else "/e/" + directory.split("/", 1)[1] + "/" + new
    categories = db.execute("SELECT id FROM categories WHERE slug = ?", (old,)).fetchall()

    print(f"{'APPLYING' if apply else 'DRY RUN'}: {old} -> {new}")
    print(f"  entry file : {old_json} -> {new_json}")
    print(f"  url        : {old_url} -> {new_url}")
    print(f"  entries row: id={entry_id} slug+location updated")
    print(f"  categories : {len(categories)} rows re-slugged")
    print(f"  media      : {len(data.get('video') or [])} video, {len(data.get('photo') or [])} photo - filenames unchanged")
    if not apply:
        print("\nre-run with --apply" + (" --announce" if not announce else ""))
        return

    data["slug"], data["url"] = new, new_url
    tmp = new_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, new_json)
    os.remove(old_json)
    db.execute("UPDATE entries SET slug = ?, location = ? WHERE id = ?",
               (new, os.path.join(directory, new), entry_id))
    db.execute("UPDATE categories SET slug = ? WHERE slug = ?", (new, old))
    db.commit()
    db.close()
    print(f"  done: https://{DOMAIN}{new_url}")

    if announce:
        from pysrc.python_webmention.mentioner import announce_to_bridgy
        results = announce_to_bridgy(f"https://{DOMAIN}{new_url}")
        for dest, (status, body) in results.items():
            print(f"  bridgy {dest:10s}: {status} {body[:120]!r}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    main(args[0], args[1], apply="--apply" in sys.argv, announce="--announce" in sys.argv)
