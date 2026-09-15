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


def test_finish_post_ignores_jobs_with_no_post():
    with patch("pysrc.syndication.syndicate") as ann:
        assert vc.finish_post({"id": "j", "post_url": None, "post_file": None}) is None
    ann.assert_not_called()


def test_finish_post_waits_while_another_video_is_still_converting(tmp_path):
    entry = _entry(tmp_path, ["data/x-0.mp4", "data/x-1.mp4"])
    ready = {"data/x-0.mp4": True, "data/x-1.mp4": False}
    with patch.object(vc, "video_is_ready", side_effect=lambda p: ready[p]), \
         patch("pysrc.syndication.syndicate") as ann:
        out = vc.finish_post({"id": "j", "post_url": "/e/2026/09/14/x", "post_file": entry})
    assert "skipped" in out and "1 video" in out["skipped"]
    ann.assert_not_called()


@pytest.fixture
def index_db(tmp_path):
    """An empty entries/categories database, as schema.sql defines it."""
    import sqlite3

    path = tmp_path / "index.db"
    db = sqlite3.connect(path)
    with open("schema.sql", encoding="utf-8") as fh:
        db.executescript(fh.read())
    db.close()
    with patch.object(vc, "DATABASE", str(path)):
        yield str(path)


def test_finish_post_publishes_indexes_then_announces_exactly_once(tmp_path, index_db, monkeypatch):
    """The order matters: the flag clears and the rows exist before Bridgy is
    told, because Bridgy fetches the page immediately."""
    import sqlite3

    monkeypatch.chdir(tmp_path)
    d = tmp_path / "data" / "2026" / "09" / "14"; d.mkdir(parents=True)
    entry = d / "clip.json"
    entry.write_text(json.dumps({"slug": "clip", "url": "/e/2026/09/14/clip", "published": "2026-09-14T12:00:00",
                                 "video": ["data/2026/09/14/clip-0.mp4"], "category": ["a", "b"], "pending_media": True}))
    job = {"id": "j", "post_url": "/e/2026/09/14/clip", "post_file": str(entry)}
    calls = []

    def announce(post_file, source):
        # By the time Bridgy is told, the page must already be public.
        calls.append(source)
        assert json.load(open(entry))["pending_media"] is False
        assert sqlite3.connect(index_db).execute("SELECT count(*) FROM entries").fetchone()[0] == 1
        return {"fediverse": (202, ""), "bluesky": (201, "")}

    with patch.object(vc, "video_is_ready", return_value=True), patch.object(vc, "DOMAIN_NAME", "kongaloosh.com"), \
         patch("pysrc.syndication.syndicate", side_effect=announce):
        first = vc.finish_post(job)
        second = vc.finish_post(job)

    assert first["published"] and first["indexed"] and first["announced"]["bluesky"][0] == 201
    assert calls == ["https://kongaloosh.com/e/2026/09/14/clip"], "announced exactly once"
    assert second == {"skipped": "already public"}
    db = sqlite3.connect(index_db)
    assert db.execute("SELECT slug, published, location FROM entries").fetchall() == [
        ("clip", "2026-09-14 12:00:00", "data/2026/09/14/clip")]
    assert sorted(r[0] for r in db.execute("SELECT category FROM categories")) == ["a", "b"]


def test_finish_post_leaves_an_already_public_post_alone(tmp_path, index_db, monkeypatch):
    import sqlite3

    monkeypatch.chdir(tmp_path)
    d = tmp_path / "data" / "2026" / "09" / "14"; d.mkdir(parents=True)
    entry = d / "old.json"
    entry.write_text(json.dumps({"slug": "old", "url": "/e/2026/09/14/old", "published": "2026-09-14T12:00:00",
                                 "video": ["data/2026/09/14/old-0.mp4"], "pending_media": False}))
    db = sqlite3.connect(index_db); db.execute("INSERT INTO entries (slug, published, location) VALUES (?,?,?)",
                                                ("old", "2026-09-14 12:00:00", "data/2026/09/14/old")); db.commit(); db.close()
    with patch.object(vc, "video_is_ready", return_value=True), \
         patch("pysrc.syndication.syndicate") as ann:
        out = vc.finish_post({"id": "j", "post_url": "/e/2026/09/14/old", "post_file": str(entry)})
    assert out == {"skipped": "already public"}
    ann.assert_not_called()


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
    (storage / "2026" / "09" / "14" / "clip.json").write_text(json.dumps({"video": ["data/2026/09/14/clip-0.mp4"], "pending_media": True}))
    monkeypatch.setattr(kongaloosh, "BLOG_STORAGE", str(storage))
    with kongaloosh.app.app_context(), patch.object(kongaloosh, "announce_post") as ann:
        kongaloosh.announce_or_defer("/e/2026/09/14/clip")
    ann.assert_not_called()


def test_publish_syndicates_immediately_without_pending_video(tmp_path, monkeypatch):
    storage = tmp_path / "data"; (storage / "2026" / "09" / "14").mkdir(parents=True)
    (storage / "2026" / "09" / "14" / "text.json").write_text(json.dumps({"video": [], "pending_media": False}))
    monkeypatch.setattr(kongaloosh, "BLOG_STORAGE", str(storage))
    monkeypatch.setattr(kongaloosh, "DOMAIN_NAME", "kongaloosh.com")
    with kongaloosh.app.app_context(), patch.object(kongaloosh, "announce_post") as ann:
        kongaloosh.announce_or_defer("/e/2026/09/14/text")
    ann.assert_called_once()
    assert ann.call_args.args[0] == "https://kongaloosh.com/e/2026/09/14/text"


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


# --------------------------------------------------------------------------
# A post is not public until its media is ready
# --------------------------------------------------------------------------


def _bulk_video_post(tmp_path, with_video):
    from datetime import datetime
    from pysrc.post import BlogPost

    bulk = str(tmp_path / "bulk") + os.sep; os.makedirs(bulk)
    media = {}
    if with_video:
        open(bulk + "clip.mp4", "wb").write(b"\0" * 16); media["video"] = [bulk + "clip.mp4"]
    return bulk, BlogPost(content="body", slug="clip", url="/e/x", title="t",
                          published=datetime(2026, 9, 14, 12, 0), u_uid="u", **media)


@pytest.mark.parametrize("with_video, expect_pending, expect_indexed", [(True, True, False), (False, False, True)])
def test_publish_indexes_only_when_no_video_is_converting(tmp_path, with_video, expect_pending, expect_indexed):
    from pysrc.file_management import file_parser as fp

    bulk, post = _bulk_video_post(tmp_path, with_video)
    storage = str(tmp_path / "data"); os.makedirs(storage)
    g = Mock()
    with kongaloosh.app.app_context(), patch.object(fp, "BLOG_STORAGE", storage), patch.object(fp, "BULK_UPLOAD_DIR", bulk), \
         patch.object(fp, "enqueue_video") as enq, patch.object(fp, "run", side_effect=lambda c, **k: c):
        location = fp.create_json_entry(post, g=g, draft=False)

    written = json.load(open(os.path.join(storage, "2026/09/14/clip.json")))
    assert written["pending_media"] is expect_pending
    assert g.execute.called is expect_indexed, "the index is what makes a post public"
    if with_video:
        assert enq.call_args.kwargs["post_url"] == location
        assert enq.call_args.kwargs["post_file"].endswith("2026/09/14/clip.json")


def test_pending_entry_is_404_for_the_public_and_visible_to_the_author(client, tmp_path, monkeypatch):
    storage = tmp_path / "data"; d = storage / "2026" / "09" / "14"; d.mkdir(parents=True)
    (d / "pend.json").write_text(json.dumps({
        "title": "Pending", "content": "Reef sharks", "published": "2026-09-14T12:00:00", "updated": "2026-09-14T12:00:00",
        "slug": "pend", "url": "/e/2026/09/14/pend", "u_uid": "u-pend", "video": ["data/2026/09/14/pend-0.mp4"], "pending_media": True}))
    monkeypatch.setattr(kongaloosh, "BLOG_STORAGE", str(storage))
    monkeypatch.chdir(tmp_path)

    assert client.get("/e/2026/09/14/pend").status_code == 404, "never public while converting"
    assert client.get("/e/2026/09/14/pend", headers={"Accept": "application/json"}).status_code == 404

    with client.session_transaction() as sess:
        sess["logged_in"] = True
    response = client.get("/e/2026/09/14/pend")
    assert response.status_code == 200
    assert b"Not public yet" in response.data


@pytest.mark.parametrize("template", ["entry.html", "blog_entries.html"])
def test_processing_hint_is_author_only(template):
    src = open(f"templates/{template}", encoding="utf-8").read()
    i = src.index('class="video-processing"')
    assert "{% if session.logged_in %}" in src[max(0, i - 200):i], "the public never sees a stub"
