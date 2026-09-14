#!/usr/bin/env python
"""Generate poster frames for videos that predate the poster pipeline.

Posters live beside the video on the data volume and are symlinked into the
blog's data directory, matching what scripts/video_worker.py produces.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysrc.video_converter import VIDEO_STORAGE, poster_command  # noqa: E402

MIN_VIDEO_BYTES = 1024  # anything smaller is a failed conversion, not a video


def main(root="data"):
    made = skipped = failed = 0
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.lower().endswith(".mp4"):
                continue
            video = os.path.join(dirpath, name)
            poster_link = os.path.splitext(video)[0] + ".poster.jpg"
            if os.path.lexists(poster_link):
                skipped += 1
                continue
            try:
                if os.path.getsize(video) < MIN_VIDEO_BYTES:
                    print(f"  skip (truncated): {video}")
                    skipped += 1
                    continue
            except OSError:
                continue

            relative = os.path.relpath(os.path.splitext(video)[0], root)
            poster_real = os.path.join(VIDEO_STORAGE, relative + ".poster.jpg")
            os.makedirs(os.path.dirname(poster_real), exist_ok=True)
            result = subprocess.run(
                poster_command(video, poster_real),
                capture_output=True, text=True, timeout=120, check=False,
            )
            if result.returncode == 0 and os.path.exists(poster_real) \
                    and os.path.getsize(poster_real) > 0:
                os.symlink(poster_real, poster_link)
                made += 1
                print(f"  poster: {poster_link}")
            else:
                failed += 1
                print(f"  FAILED: {video}")
    print(f"\nposters created={made} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main(*sys.argv[1:])
