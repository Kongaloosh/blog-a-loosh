"""Tests for video ingest: the remux/re-encode decision, the job queue, and
the template's handling of a video that has not finished converting.

Background: conversion used to run on a bare thread inside a gunicorn worker
with a fixed 300s timeout and crf 18 / preset slow. On this host those
settings ran at ~9x realtime and produced files larger than the source, so
anything longer than about 30 seconds of 1080p was killed and the post was
left pointing at a file that never arrived.
"""

import json
import os
from unittest.mock import patch

import pytest

from pysrc import video_converter as vc


# --------------------------------------------------------------------------
# Choosing between remux and re-encode
# --------------------------------------------------------------------------


def test_h264_at_modest_bitrate_is_remuxed():
    """Already-H.264 material should be copied, not re-encoded."""
    plan = vc.plan_for(
        {"codec": "h264", "width": 1920, "height": 1080, "bitrate": 4_000_000}
    )
    assert plan == "remux"


def test_high_bitrate_source_is_reencoded():
    """A phone's ~15 Mbps recording is too heavy to stream comfortably."""
    plan = vc.plan_for(
        {"codec": "h264", "width": 1920, "height": 1080, "bitrate": 15_227_712}
    )
    assert plan == "reencode"


def test_oversized_source_is_reencoded():
    plan = vc.plan_for(
        {"codec": "h264", "width": 3840, "height": 2160, "bitrate": 1_000_000}
    )
    assert plan == "reencode"


def test_non_h264_source_is_reencoded():
    """HEVC and friends do not play reliably across browsers."""
    plan = vc.plan_for(
        {"codec": "hevc", "width": 1920, "height": 1080, "bitrate": 1_000_000}
    )
    assert plan == "reencode"


def test_unknown_probe_is_reencoded():
    """If ffprobe told us nothing, do not blindly copy the stream."""
    assert vc.plan_for({}) == "reencode"


@pytest.mark.parametrize("plan", ["remux", "reencode"])
def test_ffmpeg_command_states_the_container(plan):
    """dest ends in .part, so -f mp4 is required or ffmpeg cannot guess."""
    cmd = vc.ffmpeg_command(plan, "in.mov", "/tmp/out.mp4.part")
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "mp4"
    assert "+faststart" in cmd, "video must start playing before it fully loads"


def test_remux_does_not_reencode():
    cmd = vc.ffmpeg_command("remux", "in.mov", "/tmp/out.mp4.part")
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"
    assert "libx264" not in cmd


def test_reencode_uses_web_settings_not_archival():
    cmd = vc.ffmpeg_command("reencode", "in.mov", "/tmp/out.mp4.part")
    crf = cmd[cmd.index("-crf") + 1]
    preset = cmd[cmd.index("-preset") + 1]
    assert int(crf) >= 20, "crf 18 produced files larger than the source"
    assert preset not in ("slow", "slower", "veryslow"), "too slow for 2 vCPUs"


# --------------------------------------------------------------------------
# The job queue
# --------------------------------------------------------------------------


@pytest.fixture
def queue(tmp_path):
    with patch.object(vc, "JOB_QUEUE", str(tmp_path)):
        yield str(tmp_path)


def test_enqueue_writes_a_complete_job_file(queue):
    job_id = vc.enqueue("/src/clip.mov", "data/2026/9/14/clip-0.mp4")

    path = os.path.join(queue, f"{job_id}.json")
    job = json.load(open(path, encoding="utf-8"))
    assert job["state"] == "queued"
    assert job["source"].endswith("clip.mov")
    assert job["destination"].endswith("data/2026/9/14/clip-0.mp4")
    assert job["attempts"] == 0


def test_enqueue_leaves_no_partial_files(queue):
    """The worker must never observe a half-written job."""
    vc.enqueue("/src/a.mov", "data/a-0.mp4")
    names = os.listdir(queue)
    assert all(not n.startswith(".") and n.endswith(".json") for n in names), names


def test_enqueue_is_unique_per_call(queue):
    a = vc.enqueue("/src/a.mov", "data/a-0.mp4")
    b = vc.enqueue("/src/a.mov", "data/a-0.mp4")
    assert a != b
    assert len(os.listdir(queue)) == 2


def test_enqueue_does_not_transcode(queue):
    """Nothing may run ffmpeg in the request path."""
    with patch("subprocess.run") as run:
        vc.enqueue("/src/clip.mov", "data/clip-0.mp4")
    run.assert_not_called()


# --------------------------------------------------------------------------
# Worker helpers
# --------------------------------------------------------------------------


def _worker():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "video_worker", os.path.join("scripts", "video_worker.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_storage_path_keeps_the_date_layout():
    w = _worker()
    got = w.storage_path_for("/home/deploy/kongaloosh/data/2026/9/14/clip-0.mp4")
    assert got == os.path.join(vc.VIDEO_STORAGE, "2026/9/14/clip-0.mp4")
    assert not got.startswith("/home/deploy/kongaloosh/data"), "must leave the root fs"


def test_encode_timeout_scales_with_duration():
    w = _worker()
    # The old fixed 300s killed a 95s clip; it now gets room to finish.
    assert w.encode_timeout(95) > 300
    assert w.encode_timeout(2) == 300, "short clips still get a floor"
    assert w.encode_timeout(100_000) <= 7200, "but it stays bounded"
    assert w.encode_timeout(None) > 0


def test_link_into_place_replaces_an_existing_link(tmp_path):
    w = _worker()
    first = tmp_path / "one.mp4"
    second = tmp_path / "two.mp4"
    first.write_bytes(b"a")
    second.write_bytes(b"bb")
    dest = tmp_path / "data" / "clip.mp4"

    w.link_into_place(str(first), str(dest))
    assert os.path.realpath(dest) == str(first)

    w.link_into_place(str(second), str(dest))
    assert os.path.realpath(dest) == str(second)
    assert os.path.getsize(dest) == 2


# --------------------------------------------------------------------------
# Templates must not link a video that has not arrived
# --------------------------------------------------------------------------


def _ready_video(directory, name="clip-0.mp4", size=32, meta=None):
    """A video plus the metadata sidecar the worker writes after probing it."""
    import json as _json

    directory.mkdir(parents=True, exist_ok=True)
    video = directory / name
    video.write_bytes(b"\0" * size)
    meta_file = directory / (os.path.splitext(name)[0] + ".meta.json")
    meta_file.write_text(
        _json.dumps(meta or {"width": 1920, "height": 1080, "duration": 12.0})
    )
    return video


def test_video_info_reports_missing_video(tmp_path, monkeypatch):
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    info = kongaloosh.video_info("data/2026/9/14/clip-0.mp4")
    assert info["ready"] is False
    assert info["poster"] is None


def test_video_info_reports_ready_with_dimensions(tmp_path, monkeypatch):
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    d = tmp_path / "data" / "2026" / "9" / "14"
    _ready_video(d)
    (d / "clip-0.poster.jpg").write_bytes(b"\0" * 8)

    info = kongaloosh.video_info("data/2026/9/14/clip-0.mp4")
    assert info["ready"] is True
    assert info["poster"] == "/data/2026/9/14/clip-0.poster.jpg"
    assert info["url"] == "/data/2026/9/14/clip-0.mp4"
    # Dimensions let the browser reserve the box and avoid reflowing the post.
    assert (info["width"], info["height"]) == (1920, 1080)


def test_a_missing_poster_does_not_hide_a_good_video(tmp_path, monkeypatch):
    """Regression: readiness was briefly derived from the poster, so a video
    whose thumbnail failed to render disappeared from the site entirely."""
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    _ready_video(tmp_path / "data")  # no poster written

    info = kongaloosh.video_info("data/clip-0.mp4")
    assert info["ready"] is True, "a thumbnail must never gate the video"
    assert info["poster"] is None


def test_empty_file_is_not_ready(tmp_path, monkeypatch):
    """A zero-byte file is a failed conversion, not a video."""
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    _ready_video(tmp_path / "data", size=0)
    assert kongaloosh.video_info("data/clip-0.mp4")["ready"] is False


@pytest.mark.parametrize("size", [52, 260 * 1024, 5 * 1024 * 1024])
def test_unprobed_video_is_not_ready(tmp_path, monkeypatch, size):
    """Truncated output can be any size; the old pipeline left behind files
    from 52 bytes to 5.1MB, all missing their moov atom. Without a sidecar
    recording a successful probe, nothing may be published."""
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    d = tmp_path / "data"
    d.mkdir()
    (d / "clip-0.mp4").write_bytes(b"\0" * size)  # no meta sidecar
    assert kongaloosh.video_info("data/clip-0.mp4")["ready"] is False


def test_sidecar_paths_sit_beside_the_video():
    assert vc.poster_path_for("data/2026/9/14/clip-0.mp4") == (
        "data/2026/9/14/clip-0.poster.jpg"
    )
    assert vc.meta_path_for("data/2026/9/14/clip-0.mp4") == (
        "data/2026/9/14/clip-0.meta.json"
    )


def test_write_meta_then_read_meta_roundtrips(tmp_path):
    video = tmp_path / "clip-0.mp4"
    video.write_bytes(b"\0" * 16)
    vc.write_meta(str(video), {"width": 1080, "height": 1920, "duration": 3.5})

    meta = vc.read_meta(str(video))
    assert meta == {"width": 1080, "height": 1920, "duration": 3.5}
    assert vc.video_is_ready(str(video)) is True


# --------------------------------------------------------------------------
# Poster frames
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "duration,expected_max",
    [(None, 0.0), (0, 0.0), (0.5, 0.25), (1.0, 0.5), (30.0, 1.0)],
)
def test_poster_seek_stays_inside_the_clip(duration, expected_max):
    """Regression: a flat -ss 1 seeks past the end of a sub-second clip and
    ffmpeg exits 0 having written nothing."""
    offset = float(vc.poster_timestamp(duration))
    assert offset <= expected_max
    if duration:
        assert offset < duration, "seek must land inside the video"


def test_poster_command_uses_the_safe_offset():
    cmd = vc.poster_command("in.mp4", "out.jpg", duration=0.5)
    assert float(cmd[cmd.index("-ss") + 1]) < 0.5


def test_entry_template_omits_player_until_video_is_ready(tmp_path, monkeypatch):
    """Regression guard: posts used to link videos that never arrived."""
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    template = kongaloosh.app.jinja_env.get_template("blog_entries.html")
    source = template.environment.loader.get_source(
        template.environment, "blog_entries.html"
    )[0]
    assert "video_info(video)" in source
    assert 'preload="none"' in source, "several players must not all preload"
    assert "v.ready" in source
    assert "v.width" in source, "intrinsic size prevents layout shift"


def test_player_height_is_capped_in_css():
    """The post page has no column around its content, so without a height cap
    a 1080p video fills ~97% of a desktop viewport and a portrait clip is
    taller than the screen. video.css must constrain video.u-video's height."""
    with open("static/css/video.css", encoding="utf-8") as fh:
        css = fh.read()
    rule = css[css.index("video.u-video {"):]
    rule = rule[: rule.index("}")]
    assert "max-height" in rule and "vh" in rule, "player must be bounded by the viewport"
    assert "max-width: 100%" in rule
