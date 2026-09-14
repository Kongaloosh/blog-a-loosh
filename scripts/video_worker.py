#!/usr/bin/env python
"""Process queued video conversions, one at a time.

Run from cron every minute; an flock ensures only one instance is ever
active, so encodes never compete with each other for this host's two cores.

Each job converts a source upload into a finished .mp4. The bytes are
written to the data volume and symlinked into the blog's data directory,
which keeps URLs and the nginx config unchanged while keeping large media
off the root filesystem. Output is written to a temporary file and renamed
into place, so a post never links a half-written video.
"""

import fcntl
import json
import logging
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysrc.video_converter import (  # noqa: E402
    JOB_QUEUE,
    VIDEO_STORAGE,
    ffmpeg_command,
    maybe_announce,
    meta_path_for,
    plan_for,
    poster_command,
    poster_path_for,
    probe,
    write_meta,
)

LOG_PATH = os.environ.get("VIDEO_WORKER_LOG", "video-worker.log")
LOCK_PATH = os.path.join(JOB_QUEUE, ".worker.lock")
MAX_ATTEMPTS = 3

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("video_worker")


def encode_timeout(duration):
    """Allow 15x realtime, with a floor and a ceiling.

    The old fixed 300s killed anything longer than about 30 seconds of
    1080p on this host, leaving posts pointing at files that never arrived.
    """
    if not duration:
        return 1800
    return int(min(max(duration * 15, 300), 7200))


def storage_path_for(destination):
    """Map data/2026/9/14/clip-0.mp4 -> <VIDEO_STORAGE>/2026/9/14/clip-0.mp4."""
    parts = os.path.normpath(destination).split(os.sep)
    if "data" in parts:
        relative = os.path.join(*parts[parts.index("data") + 1:])
    else:
        relative = os.path.basename(destination)
    return os.path.join(VIDEO_STORAGE, relative)


def link_into_place(real_path, destination):
    """Point destination at real_path, replacing whatever is there."""
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    tmp_link = destination + ".linktmp"
    if os.path.lexists(tmp_link):
        os.unlink(tmp_link)
    os.symlink(real_path, tmp_link)
    os.replace(tmp_link, destination)


def run(command, timeout):
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=timeout, check=False,
    )
    return result.returncode, result.stderr[-2000:]


def write_job(path, job):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=2)
    os.replace(tmp, path)


def process(path):
    with open(path, encoding="utf-8") as fh:
        job = json.load(fh)

    if job.get("state") not in ("queued", "running"):
        return

    source, destination = job["source"], job["destination"]
    if not os.path.exists(source):
        job.update(state="failed", error="source file is gone", finished=time.time())
        write_job(path, job)
        log.error("job %s: source missing: %s", job["id"], source)
        return

    info = probe(source)
    plan = plan_for(info)
    job.update(
        state="running", plan=plan, probe=info,
        attempts=job.get("attempts", 0) + 1, started=time.time(),
    )
    write_job(path, job)
    log.info("job %s: %s %s (%s)", job["id"], plan, source, info)

    real_path = storage_path_for(destination)
    os.makedirs(os.path.dirname(real_path), exist_ok=True)
    partial = real_path + ".part"

    timeout = encode_timeout(info.get("duration"))
    started = time.time()
    try:
        code, stderr = run(ffmpeg_command(plan, source, partial), timeout)
    except subprocess.TimeoutExpired:
        code, stderr = -1, f"timed out after {timeout}s"

    if code != 0 or not os.path.exists(partial) or os.path.getsize(partial) == 0:
        if os.path.exists(partial):
            os.unlink(partial)
        retry = job["attempts"] < MAX_ATTEMPTS
        job.update(
            state="queued" if retry else "failed",
            error=stderr, finished=time.time(),
        )
        write_job(path, job)
        log.error("job %s failed (attempt %s): %s", job["id"], job["attempts"], stderr)
        return

    os.replace(partial, real_path)

    # Probe what we actually produced. This, not the thumbnail, is what marks
    # the file publishable: ffmpeg can exit 0 having written something that
    # will not play, which is how the previous pipeline left broken videos
    # linked from live posts.
    out_info = probe(real_path)
    if not out_info.get("width") or not out_info.get("duration"):
        os.unlink(real_path)
        retry = job["attempts"] < MAX_ATTEMPTS
        job.update(
            state="queued" if retry else "failed",
            error=f"output did not probe as playable: {out_info}",
            finished=time.time(),
        )
        write_job(path, job)
        log.error("job %s: output failed probe, discarded", job["id"])
        return

    write_meta(real_path, out_info)
    link_into_place(real_path, destination)
    link_into_place(meta_path_for(real_path), meta_path_for(destination))

    # Poster frame: nice to have, and deliberately not a gate. A missing
    # thumbnail must never hide a video that converted correctly.
    poster_real = poster_path_for(real_path)
    try:
        pcode, pstderr = run(
            poster_command(real_path, poster_real, out_info.get("duration")), 120
        )
        if pcode == 0 and os.path.exists(poster_real) \
                and os.path.getsize(poster_real) > 0:
            link_into_place(poster_real, poster_path_for(destination))
        else:
            log.warning("job %s: no poster produced: %s", job["id"], pstderr[-200:])
    except (subprocess.TimeoutExpired, OSError) as e:
        log.warning("job %s: poster failed: %s", job["id"], e)

    # The post is complete once its last video lands: this is the moment to
    # tell Bridgy, not publish time.
    try:
        announced = maybe_announce(job)
    except Exception as e:  # syndication must never fail the conversion
        log.exception("job %s: announce failed: %s", job["id"], e)
        announced = {"error": str(e)[:200]}
    if announced:
        log.info("job %s: syndication: %s", job["id"], announced)

    job.update(
        state="done", finished=time.time(),
        elapsed=round(time.time() - started, 1),
        output=real_path, output_bytes=os.path.getsize(real_path),
        announced=announced,
    )
    write_job(path, job)
    log.info(
        "job %s done in %ss: %s (%.1f MB)",
        job["id"], job["elapsed"], real_path, job["output_bytes"] / 1048576,
    )


def main():
    os.makedirs(JOB_QUEUE, exist_ok=True)
    with open(LOCK_PATH, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0  # another worker is already running

        jobs = sorted(
            os.path.join(JOB_QUEUE, n)
            for n in os.listdir(JOB_QUEUE)
            if n.endswith(".json")
        )
        for job_path in jobs:
            try:
                process(job_path)
            except Exception as e:  # one bad job must not stop the queue
                log.exception("error processing %s: %s", job_path, e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
