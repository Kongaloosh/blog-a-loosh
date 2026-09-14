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


def test_video_info_reports_missing_video(tmp_path, monkeypatch):
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    info = kongaloosh.video_info("data/2026/9/14/clip-0.mp4")
    assert info["ready"] is False
    assert info["poster"] is None


def test_video_info_finds_poster_when_ready(tmp_path, monkeypatch):
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    d = tmp_path / "data" / "2026" / "9" / "14"
    d.mkdir(parents=True)
    (d / "clip-0.mp4").write_bytes(b"\0" * 32)
    (d / "clip-0.poster.jpg").write_bytes(b"\0" * 8)

    info = kongaloosh.video_info("data/2026/9/14/clip-0.mp4")
    assert info["ready"] is True
    assert info["poster"] == "/data/2026/9/14/clip-0.poster.jpg"
    assert info["url"] == "/data/2026/9/14/clip-0.mp4"


def test_empty_file_is_not_ready(tmp_path, monkeypatch):
    """A zero-byte file is a failed conversion, not a video."""
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    d = tmp_path / "data"
    d.mkdir()
    (d / "clip-0.mp4").write_bytes(b"")
    (d / "clip-0.poster.jpg").write_bytes(b"\0" * 8)
    assert kongaloosh.video_info("data/clip-0.mp4")["ready"] is False


@pytest.mark.parametrize("size", [52, 260 * 1024, 5 * 1024 * 1024])
def test_truncated_encode_without_poster_is_not_ready(tmp_path, monkeypatch, size):
    """Truncated output can be any size; the old pipeline left behind files
    of 52 bytes and of 5MB, both missing their moov atom. Only the poster
    distinguishes them, because it requires a decodable frame."""
    import kongaloosh

    monkeypatch.chdir(tmp_path)
    d = tmp_path / "data"
    d.mkdir()
    (d / "clip-0.mp4").write_bytes(b"\0" * size)  # no poster alongside it
    assert kongaloosh.video_info("data/clip-0.mp4")["ready"] is False


def test_poster_path_sits_beside_the_video():
    assert vc.poster_path_for("data/2026/9/14/clip-0.mp4") == (
        "data/2026/9/14/clip-0.poster.jpg"
    )


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
