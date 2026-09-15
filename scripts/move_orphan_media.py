#!/usr/bin/env python
"""Move unplayable, unreferenced video files off the root filesystem.

These are wreckage from the pipeline that wrote encoder output straight to
its destination: truncated files ranging from 52 bytes to several MB, none
of them referenced by any post. They are moved rather than deleted, onto
the data volume, so nothing is lost.
"""

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysrc.video_converter import VIDEO_STORAGE, meta_path_for  # noqa: E402

QUARANTINE = os.path.join(VIDEO_STORAGE, "_unplayable")


def _walk_files(root, suffix):
    """Files under root, without descending into symlinked directories.

    data/ carries alias symlinks for the old unpadded date paths; glob(**)
    follows them and would report every file twice.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            if name.endswith(suffix):
                yield os.path.join(dirpath, name)


def referenced_videos(root="data"):
    """Every video path mentioned by a post."""
    referenced = set()
    for entry in _walk_files(root, ".json"):
        if entry.endswith(".meta.json"):
            continue
        try:
            with open(entry, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        videos = data.get("video") or []
        if isinstance(videos, str):
            videos = [videos]
        referenced.update(str(v).lstrip("/") for v in videos)
    return referenced


def main(root="data", apply=False):
    referenced = referenced_videos(root)
    moved = bytes_freed = 0

    for video in sorted(_walk_files(root, ".mp4")):
        if os.path.islink(video):
            continue  # already on the volume
        if os.path.lexists(meta_path_for(video)):
            continue  # probed and playable
        if video in referenced:
            print(f"  KEEP (unplayable but still linked by a post): {video}")
            continue

        size = os.path.getsize(video)
        target = os.path.join(QUARANTINE, os.path.relpath(video, root))
        if apply:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(video, target)
        print(f"  {'moved' if apply else 'would move'} {size/1024:9.1f} KB  {video}")
        moved += 1
        bytes_freed += size

    print(
        f"\n{'moved' if apply else 'would move'} {moved} files, "
        f"{bytes_freed/1048576:.1f} MB off the root filesystem"
    )
    if not apply:
        print("re-run with --apply to actually move them")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
