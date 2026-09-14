"""Syndication through Bridgy: the endpoints, and *when* the webmentions go out.

Bridgy fetches a post the moment it receives the webmention. On 2026-09-14 a
post with a video was announced at publish time, ~60s before the worker had
converted the video, and Bridgy syndicated the page without the clip - with
the "still being processed" placeholder as the Bluesky post's text. The
webmentions are now sent by whoever finishes the post: the request handler
when there is no video, the conversion worker when the last video lands.

The fediverse leg had also been posting to /publish/webmention, which returns
404; Bridgy Fed advertises /webmention.
"""

import json
import os
from unittest.mock import Mock, patch

import pytest
import requests

import kongaloosh
from pysrc import video_converter as vc
from pysrc.python_webmention import mentioner


# --------------------------------------------------------------------------
# Talking to Bridgy
# --------------------------------------------------------------------------


def test_announce_hits_both_bridgy_endpoints_with_the_right_targets():
    calls = []

    def fake_post(url, data=None, timeout=None, **_):
        calls.append((url, data, timeout))
        return Mock(status_code=201 if "brid.gy/publish" in url else 202, text="ok")

    with patch.object(mentioner.requests, "post", side_effect=fake_post):
        result = mentioner.announce_to_bridgy("https://kongaloosh.com/e/2026/09/14/x")

    urls = [c[0] for c in calls]
    assert "https://fed.brid.gy/webmention" in urls, "Bridgy Fed's advertised endpoint"
    assert "https://fed.brid.gy/publish/webmention" not in urls, "this path 404s"
    assert "https://brid.gy/publish/webmention" in urls
    by_url = {c[0]: c for c in calls}
    assert by_url["https://fed.brid.gy/webmention"][1] == {
        "source": "https://kongaloosh.com/e/2026/09/14/x", "target": "https://fed.brid.gy/"}
    assert by_url["https://brid.gy/publish/webmention"][1]["target"] == "https://brid.gy/publish/bluesky"
    assert all(c[2] == mentioner.HTTP_TIMEOUT for c in calls), "never without a timeout"
    assert result["fediverse"][0] == 202 and result["bluesky"][0] == 201


def test_announce_never_raises_and_keeps_going_after_one_failure():
    def flaky(url, **_):
        if "fed.brid.gy" in url:
            raise requests.exceptions.ConnectionError("fediverse down")
        return Mock(status_code=201, text="created")

    with patch.object(mentioner.requests, "post", side_effect=flaky):
        result = mentioner.announce_to_bridgy("https://kongaloosh.com/e/x")

    assert result["fediverse"][0] is None and "fediverse down" in result["fediverse"][1]
    assert result["bluesky"][0] == 201, "one dead destination must not stop the other"


def test_a_201_from_bridgy_is_success_not_an_error(caplog):
    """Bridgy answers 201 on a new Bluesky post; the old code logged != 200 as an error."""
    with patch.object(mentioner.requests, "post", return_value=Mock(status_code=201, text="{}")):
        with caplog.at_level("WARNING"):
            status, _ = mentioner.send_bridgy_webmention("s", "https://brid.gy/publish/webmention", "t")
    assert status == 201
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


# --------------------------------------------------------------------------
# Jobs carry the post; the worker announces once the post is complete
# --------------------------------------------------------------------------


@pytest.fixture
def queue(tmp_path):
    with patch.object(vc, "JOB_QUEUE", str(tmp_path)):
        yield str(tmp_path)


def test_enqueue_records_the_post_it_belongs_to(queue):
    job_id = vc.enqueue("/src/a.mov", "data/2026/9/14/a-0.mp4",
                        post_url="/e/2026/09/14/a", post_file="data/2026/09/14/a.json")
    job = json.load(open(os.path.join(queue, f"{job_id}.json")))
    assert job["post_url"] == "/e/2026/09/14/a"
    assert job["post_file"].endswith("data/2026/09/14/a.json")


def test_enqueue_without_a_post_stays_anonymous(queue):
    """Drafts and backfills convert without syndicating anything."""
    job_id = vc.enqueue("/src/a.mov", "data/a-0.mp4")
    job = json.load(open(os.path.join(queue, f"{job_id}.json")))
    assert job["post_url"] is None and job["post_file"] is None


def _entry(tmp_path, videos):
    f = tmp_path / "entry.json"
    f.write_text(json.dumps({"video": videos, "content": "x"}))
    return str(f)


def test_maybe_announce_ignores_jobs_with_no_post():
    with patch("pysrc.python_webmention.mentioner.announce_to_bridgy") as ann:
        assert vc.maybe_announce({"id": "j", "post_url": None, "post_file": None}) is None
    ann.assert_not_called()


def test_maybe_announce_waits_while_another_video_is_still_converting(tmp_path):
    entry = _entry(tmp_path, ["data/x-0.mp4", "data/x-1.mp4"])
    ready = {"data/x-0.mp4": True, "data/x-1.mp4": False}
    with patch.object(vc, "video_is_ready", side_effect=lambda p: ready[p]), \
         patch("pysrc.python_webmention.mentioner.announce_to_bridgy") as ann:
        out = vc.maybe_announce({"id": "j", "post_url": "/e/2026/09/14/x", "post_file": entry})
    assert "skipped" in out and "1 video" in out["skipped"]
    ann.assert_not_called()


def test_maybe_announce_fires_once_the_last_video_lands(tmp_path):
    entry = _entry(tmp_path, ["data/x-0.mp4", "data/x-1.mp4"])
    with patch.object(vc, "video_is_ready", return_value=True), \
         patch.object(vc, "DOMAIN_NAME", "kongaloosh.com"), \
         patch("pysrc.python_webmention.mentioner.announce_to_bridgy",
               return_value={"fediverse": (202, ""), "bluesky": (201, "")}) as ann:
        out = vc.maybe_announce({"id": "j", "post_url": "/e/2026/09/14/x", "post_file": entry})
    ann.assert_called_once_with("https://kongaloosh.com/e/2026/09/14/x")
    assert out["bluesky"][0] == 201


def test_pending_videos_lists_only_the_unready_ones(tmp_path):
    entry = _entry(tmp_path, ["data/a.mp4", "data/b.mp4"])
    with patch.object(vc, "video_is_ready", side_effect=lambda p: p == "data/a.mp4"):
        assert vc.pending_videos(entry) == ["data/b.mp4"]
    assert vc.pending_videos(str(tmp_path / "nope.json")) == []


# --------------------------------------------------------------------------
# The request handler defers when a video is pending
# --------------------------------------------------------------------------


def test_publish_defers_syndication_while_a_video_converts(tmp_path, monkeypatch):
    storage = tmp_path / "data"; (storage / "2026" / "09" / "14").mkdir(parents=True)
    (storage / "2026" / "09" / "14" / "clip.json").write_text(json.dumps({"video": ["data/2026/09/14/clip-0.mp4"]}))
    monkeypatch.setattr(kongaloosh, "BLOG_STORAGE", str(storage))
    with kongaloosh.app.app_context(), \
         patch.object(kongaloosh.video_converter, "video_is_ready", return_value=False), \
         patch.object(kongaloosh, "announce_post") as ann:
        kongaloosh.announce_or_defer("/e/2026/09/14/clip")
    ann.assert_not_called()


def test_publish_syndicates_immediately_without_pending_video(tmp_path, monkeypatch):
    storage = tmp_path / "data"; (storage / "2026" / "09" / "14").mkdir(parents=True)
    (storage / "2026" / "09" / "14" / "text.json").write_text(json.dumps({"video": []}))
    monkeypatch.setattr(kongaloosh, "BLOG_STORAGE", str(storage))
    monkeypatch.setattr(kongaloosh, "DOMAIN_NAME", "kongaloosh.com")
    with kongaloosh.app.app_context(), patch.object(kongaloosh, "announce_post") as ann:
        kongaloosh.announce_or_defer("/e/2026/09/14/text")
    ann.assert_called_once_with("https://kongaloosh.com/e/2026/09/14/text")


def test_already_made_is_not_announced():
    with kongaloosh.app.app_context(), patch.object(kongaloosh, "announce_post") as ann:
        kongaloosh.announce_or_defer("/already_made")
    ann.assert_not_called()


# --------------------------------------------------------------------------
# What Bridgy sees in the HTML
# --------------------------------------------------------------------------


@pytest.mark.parametrize("template", ["entry.html", "blog_entries.html"])
def test_video_element_carries_the_u_video_property(template):
    src = open(f"templates/{template}", encoding="utf-8").read()
    assert 'class="u-video' in src, "Bridgy attaches the video only via u-video on the <video>"
    assert "u-videos" not in src, "the mistyped property that hid every video from Bridgy"


@pytest.mark.parametrize("template", ["entry.html", "blog_entries.html"])
def test_processing_placeholder_has_no_text_for_parsers(template):
    src = open(f"templates/{template}", encoding="utf-8").read()
    assert 'class="video-processing"' in src
    assert "This video is still being processed." not in src.replace("{#", "\x00").split("\x00")[0] or \
        all("still being processed" not in seg.split("#}")[-1] for seg in src.split("{#")[1:]), \
        "the hint must live in CSS (::after), not in the DOM text Bridgy reads"
