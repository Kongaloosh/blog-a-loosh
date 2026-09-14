#!/usr/bin/env python
"""Mark pre-existing videos as playable, and give them poster frames.

Videos produced before the queue existed carry no metadata sidecar, so the
templates cannot tell a good file from one of the truncated encodes the old
pipeline left behind. This probes each one and records the result.

Safe to re-run: files that already have metadata are skipped, and nothing
is deleted.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysrc.video_converter import (  # noqa: E402
    VIDEO_STORAGE,
    meta_path_for,
    poster_command,
    poster_path_for,
    probe,
    write_meta,
)


def main(root="data"):
    ok = broken = skipped = 0
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            if not name.lower().endswith(".mp4"):
                continue
            video = os.path.join(dirpath, name)
            if os.path.lexists(meta_path_for(video)):
                skipped += 1
                continue

            info = probe(video)
            if not info.get("width") or not info.get("duration"):
                broken += 1
                print(f"  UNPLAYABLE (left in place): {video}")
                continue

            write_meta(video, info)
            ok += 1

            if not os.path.lexists(poster_path_for(video)):
                relative = os.path.relpath(os.path.splitext(video)[0], root)
                poster_real = os.path.join(
                    VIDEO_STORAGE, relative + ".poster.jpg"
                )
                os.makedirs(os.path.dirname(poster_real), exist_ok=True)
                result = subprocess.run(
                    poster_command(video, poster_real, info.get("duration")),
                    capture_output=True, text=True, timeout=120, check=False,
                )
                if result.returncode == 0 and os.path.exists(poster_real) \
                        and os.path.getsize(poster_real) > 0:
                    os.symlink(poster_real, poster_path_for(video))
                else:
                    print(f"  (no poster, video still published): {video}")
            print(f"  ok: {video}  {info.get('width')}x{info.get('height')}")

    print(f"\nplayable={ok} unplayable={broken} already-done={skipped}")


if __name__ == "__main__":
    main(*sys.argv[1:])
