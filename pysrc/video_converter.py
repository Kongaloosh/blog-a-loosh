"""Video ingest: decide what a source file needs, and queue the work.

Nothing here transcodes in the web process. Encoding runs in a separate
worker (scripts/video_worker.py) driven by a directory of JSON job files,
so a gunicorn restart cannot lose an in-flight conversion and a slow
encode cannot compete with request handling for this host's two cores.

The choice of remux vs re-encode matters more than the encoder preset. A
phone recording is already H.264, so copying it into an .mp4 container is
lossless and effectively instant. Re-encoding is only worth its cost when
the source bitrate is too high to play smoothly over a slow connection.
"""

import configparser
import json
import logging
import os
import subprocess
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read("config.ini")

VIDEO_STORAGE = config.get(
    "VideoStorage", "storage", fallback="/mnt/volume-nyc1-01/video/"
)
JOB_QUEUE = config.get(
    "VideoStorage", "jobqueue", fallback="/mnt/volume-nyc1-01/video-jobs/"
)

# Above this bitrate a re-encode is worth the CPU: the viewer needs to sustain
# it to play without stalling. Below it, remux and keep the original quality.
REENCODE_ABOVE_BPS = 8_000_000
MAX_HEIGHT = 1080

# Web-delivery settings. The previous crf 18 / preset slow ran at ~9x realtime
# on this host and produced files larger than the source.
CRF = "23"
PRESET = "veryfast"
AUDIO_BITRATE = "128k"


def probe(path: str) -> Dict[str, Any]:
    """Return {codec, width, height, bitrate, duration} for a video file."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height,bit_rate",
                "-show_entries", "format=duration,bit_rate",
                "-of", "json", path,
            ],
            capture_output=True, text=True, timeout=60, check=False,
        )
        data = json.loads(out.stdout or "{}")
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
        logger.warning("ffprobe failed for %s: %s", path, e)
        return {}

    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}

    def as_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def as_float(value) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # Stream bitrate is often absent in .mov; fall back to the container's.
    bitrate = as_int(stream.get("bit_rate")) or as_int(fmt.get("bit_rate"))
    return {
        "codec": stream.get("codec_name"),
        "width": as_int(stream.get("width")),
        "height": as_int(stream.get("height")),
        "bitrate": bitrate,
        "duration": as_float(fmt.get("duration")),
    }


def plan_for(info: Dict[str, Any]) -> str:
    """'remux' if the source can be copied as-is, else 'reencode'."""
    if info.get("codec") != "h264":
        return "reencode"
    height = info.get("height")
    if height and height > MAX_HEIGHT:
        return "reencode"
    bitrate = info.get("bitrate")
    if bitrate and bitrate > REENCODE_ABOVE_BPS:
        return "reencode"
    return "remux"


def ffmpeg_command(plan: str, src: str, dest: str) -> list:
    """The ffmpeg invocation for a plan. dest is a temporary path."""
    # dest is a temporary name ending in .part, so the container has to be
    # stated explicitly: ffmpeg cannot infer it from that extension.
    if plan == "remux":
        return [
            "ffmpeg", "-y", "-i", src,
            "-c", "copy", "-movflags", "+faststart", "-f", "mp4", dest,
        ]
    return [
        "ffmpeg", "-y", "-i", src,
        "-c:v", "libx264", "-crf", CRF, "-preset", PRESET,
        "-vf", f"scale='min({MAX_HEIGHT*16//9},iw)':-2,format=yuv420p",
        "-c:a", "aac", "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart", "-f", "mp4", dest,
    ]


def poster_command(src: str, dest: str) -> list:
    """Grab a single frame for use as the <video> poster."""
    return [
        "ffmpeg", "-y", "-ss", "1", "-i", src,
        "-frames:v", "1", "-vf", f"scale='min(1280,iw)':-2", dest,
    ]


def enqueue(source_path: str, final_path: str) -> str:
    """Queue a conversion and return the job id.

    final_path is where the finished .mp4 should end up. The worker writes to
    a temporary file and renames it into place, so the destination either does
    not exist or is a complete, playable file - never a truncated one.
    """
    os.makedirs(JOB_QUEUE, exist_ok=True)
    job_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    job = {
        "id": job_id,
        "source": os.path.abspath(source_path),
        "destination": os.path.abspath(final_path),
        "state": "queued",
        "created": time.time(),
        "attempts": 0,
    }
    # Write then rename so the worker never reads a half-written job file.
    tmp = os.path.join(JOB_QUEUE, f".{job_id}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=2)
    os.replace(tmp, os.path.join(JOB_QUEUE, f"{job_id}.json"))
    logger.info("queued video job %s: %s -> %s", job_id, source_path, final_path)
    return job_id


def job_state(job_id: str) -> Optional[str]:
    path = os.path.join(JOB_QUEUE, f"{job_id}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("state")
    except (OSError, json.JSONDecodeError):
        return None


def poster_path_for(video_path: str) -> str:
    return os.path.splitext(video_path)[0] + ".poster.jpg"


def video_is_ready(path: str) -> bool:
    """True when a playable converted video exists at path.

    The poster is the gate rather than the file size. A truncated encode can
    be any size - the old pipeline left behind files of 52 bytes and of 5MB,
    both missing their moov atom and both unplayable - but a poster only
    exists if ffmpeg could actually decode a frame.
    """
    try:
        if os.path.getsize(path) <= 0:
            return False
        return os.path.getsize(poster_path_for(path)) > 0
    except OSError:
        return False
