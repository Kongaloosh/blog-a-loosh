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
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime
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
DOMAIN_NAME = config.get("Global", "DomainName", fallback="kongaloosh.com")
DATABASE = config.get("Global", "database", fallback="kongaloosh.db")

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


def poster_timestamp(duration: Optional[float]) -> str:
    """A seek offset that exists inside the clip.

    A flat -ss 1 seeks past the end of anything shorter than a second, and
    ffmpeg then exits 0 having written no file at all.
    """
    if not duration or duration <= 0:
        return "0"
    return f"{min(1.0, duration / 2):.3f}"


def poster_command(src: str, dest: str, duration: Optional[float] = None) -> list:
    """Grab a single frame for use as the <video> poster."""
    return [
        "ffmpeg", "-y", "-ss", poster_timestamp(duration), "-i", src,
        "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", dest,
    ]


def enqueue(
    source_path: str,
    final_path: str,
    post_url: Optional[str] = None,
    post_file: Optional[str] = None,
) -> str:
    """Queue a conversion and return the job id.

    final_path is where the finished .mp4 should end up. The worker writes to
    a temporary file and renames it into place, so the destination either does
    not exist or is a complete, playable file - never a truncated one.

    post_url/post_file name the published entry this video belongs to. When
    they are set, the worker sends the Bridgy webmentions once every video of
    that entry is ready - Bridgy fetches a post the moment it hears about it,
    and a page whose video has not landed yet syndicates without it.
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
        "post_url": post_url,
        "post_file": os.path.abspath(post_file) if post_file else None,
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


def meta_path_for(video_path: str) -> str:
    return os.path.splitext(video_path)[0] + ".meta.json"


def write_meta(video_path: str, info: Dict[str, Any]) -> None:
    """Record that this file was probed and found playable."""
    path = meta_path_for(video_path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "width": info.get("width"),
                "height": info.get("height"),
                "duration": info.get("duration"),
            },
            fh,
        )
    os.replace(tmp, path)


def read_meta(video_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(meta_path_for(video_path), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def video_is_ready(path: str) -> bool:
    """True when a playable converted video exists at path.

    Readiness is recorded by whatever produced the file, after probing it -
    not inferred from a thumbnail, and not from size. A truncated encode can
    be any size: the old pipeline left behind files from 52 bytes to 5.1MB,
    all missing their moov atom. Deriving this from the poster would have let
    a missing thumbnail hide a perfectly good video.
    """
    try:
        if os.path.getsize(path) <= 0:
            return False
    except OSError:
        return False
    return read_meta(path) is not None


def pending_videos(entry_json_path: str) -> list:
    """Videos listed by an entry whose converted file has not landed yet."""
    try:
        with open(entry_json_path, encoding="utf-8") as fh:
            videos = json.load(fh).get("video") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return []
    return [v for v in videos if not video_is_ready(str(v).lstrip("/"))]


def _sql_datetime(value):
    """Match the 'YYYY-MM-DD HH:MM:SS' the request path stores in the database."""
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return str(value) if value else None


def index_entry(entry: Dict[str, Any], post_file: str) -> bool:
    """Insert the entries and categories rows for an entry, if absent.

    The index is what the site lists from - homepage, tags, feeds, outbox -
    so this is the moment a post becomes public. Returns True if it inserted.
    """
    from pysrc.database.queries import CategoryQueries, EntryQueries

    location = os.path.splitext(os.path.relpath(post_file))[0]
    slug = entry.get("slug") or os.path.basename(location)
    published = _sql_datetime(entry.get("published"))
    db = sqlite3.connect(DATABASE)
    try:
        if db.execute("SELECT 1 FROM entries WHERE location = ?", (location,)).fetchone():
            return False
        db.execute(EntryQueries.INSERT, [slug, published, location])
        for category in entry.get("category") or []:
            db.execute(CategoryQueries.INSERT_OR_REPLACE, [slug, published, category])
        db.commit()
        return True
    finally:
        db.close()


def finish_post(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """After a conversion, publish the job's post if every video is now ready.

    Publishing is three steps in a fixed order: clear pending_media in the
    entry file, index the entry so it appears on the site, then announce it
    to Bridgy - which fetches the post the instant it hears, so the page must
    already be public and complete. A post that is already public is left
    alone, so retries and multi-video posts never announce twice.

    Returns what changed, {"skipped": reason}, or None when the job does not
    belong to a published post (drafts, backfills).
    """
    post_url, post_file = job.get("post_url"), job.get("post_file")
    if not post_url or not post_file:
        return None
    if not os.path.exists(post_file):
        return {"skipped": "post file missing"}
    still = pending_videos(post_file)
    if still:
        return {"skipped": f"{len(still)} video(s) still converting"}

    with open(post_file, encoding="utf-8") as fh:
        entry = json.load(fh)
    changed: Dict[str, Any] = {}
    if entry.get("pending_media"):
        entry["pending_media"] = False
        tmp = post_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, post_file)
        changed["published"] = True
    if index_entry(entry, post_file):
        changed["indexed"] = True
    if not changed:
        return {"skipped": "already public"}

    from pysrc.python_webmention.mentioner import announce_to_bridgy

    source = post_url if post_url.startswith("http") else f"https://{DOMAIN_NAME}{post_url}"
    changed["announced"] = announce_to_bridgy(source)
    return changed
