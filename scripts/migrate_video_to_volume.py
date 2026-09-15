#!/usr/bin/env python
"""Move published videos onto the data volume, leaving symlinks behind.

This is the layout scripts/video_worker.py already produces for new uploads:
the bytes live on the volume and data/ holds a symlink, so URLs and the nginx
config are unchanged while large media stays off the root filesystem.

Each file is copied, verified byte-for-byte, and only then replaced by the
symlink. Safe to re-run; already-migrated files are skipped.
"""

import filecmp
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysrc.video_converter import VIDEO_STORAGE  # noqa: E402

SUFFIXES = (".mp4", ".poster.jpg", ".meta.json")


def migrate(path, root):
    relative = os.path.relpath(path, root)
    target = os.path.join(VIDEO_STORAGE, relative)
    os.makedirs(os.path.dirname(target), exist_ok=True)

    if not os.path.exists(target):
        # Copy first, never move: a failure must leave the original in place.
        tmp = target + ".partial"
        with open(path, "rb") as src, open(tmp, "wb") as dst:
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
        os.replace(tmp, target)

    if not filecmp.cmp(path, target, shallow=False):
        print(f"  MISMATCH, left alone: {path}")
        return 0

    size = os.path.getsize(path)
    os.unlink(path)
    os.symlink(os.path.abspath(target), path)
    return size


def main(root="data", apply=False):
    moved = freed = 0
    # os.walk rather than glob(**): data/ carries alias symlinks for the old
    # unpadded date paths, and glob would visit every file twice.
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        paths += [os.path.join(dirpath, n) for n in filenames]
    for path in sorted(paths):
        if os.path.islink(path) or not os.path.isfile(path):
            continue
        if not path.endswith(SUFFIXES):
            continue
        if not apply:
            print(f"  would move {os.path.getsize(path)/1048576:7.1f} MB  {path}")
            moved += 1
            freed += os.path.getsize(path)
            continue
        size = migrate(path, root)
        if size:
            moved += 1
            freed += size
            print(f"  moved {size/1048576:7.1f} MB  {path}")

    print(f"\n{'moved' if apply else 'would move'} {moved} files, "
          f"{freed/1048576:.1f} MB off the root filesystem")
    if not apply:
        print("re-run with --apply")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
