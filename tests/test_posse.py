"""Native syndication (POSSE): composing posts, the four targets, and the
entry's syndication list. Network and the AT Protocol client are faked; no
test talks to Bluesky, Bridgy or a fediverse server."""

import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from pysrc import syndication as syn


@pytest.fixture
def cfg(monkeypatch):
    """A fresh ConfigParser the module reads from, per test."""
    import configparser

    c = configparser.ConfigParser()
    monkeypatch.setattr(syn, "config", c)
    return c


def entry_file(tmp_path, **fields):
    data = {"title": None, "content": "Reef Sharks!", "category": ["scuba", "diving"], "video": [], "photo": []}
    data.update(fields)
    f = tmp_path / "e.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return str(f), data


# ---- composition -----------------------------------------------------------


def test_default_targets_are_todays_two_bridgy_webmentions(cfg):
    assert syn.targets() == ["bridgy_fed", "bridgy_bluesky"]


def test_targets_come_from_config(cfg):
    cfg.read_dict({"Syndication": {"targets": "bluesky, fediverse"}})
    assert syn.targets() == ["bluesky", "fediverse"]


def test_plain_text_strips_markdown_and_keeps_title():
    t = syn.plain_text({"title": "Hi", "content": "Some **bold** and a [link](https://x.y) and `code`."})
    assert t == "Hi\n\nSome bold and a link and code."


def test_hashtags_are_sanitised_and_deduped():
    tags = syn.hashtags({"category": ["travel photography", "Travel", "travel", "2024", "a-b", "scuba"]})
    assert tags == ["travelphotography", "Travel", "ab", "scuba"], "spaces/dashes dropped, numbers-only dropped, case-insensitive dedupe"


def test_fit_text_leaves_room_for_the_link_and_tags():
    long = "word " * 100
    out = syn.fit_text(long, reserve=60, limit=290)
    assert len(out) + 60 <= 290 and out.endswith("…")
    assert syn.fit_text("short", reserve=60, limit=290) == "short"


def test_fediverse_text_has_body_link_and_tags():
    t = syn.fediverse_text({"content": "Reef Sharks!", "category": ["scuba"]}, "https://kongaloosh.com/e/2026/07/10/reef-shark")
    assert t == "Reef Sharks!\n\nhttps://kongaloosh.com/e/2026/07/10/reef-shark\n\n#scuba"


# ---- bluesky ---------------------------------------------------------------


class FakeBsky:
    def __init__(self):
        self.calls = []

    def _ok(self, name):
        def f(*a, **k):
            self.calls.append((name, a, k))
            return SimpleNamespace(uri="at://did:plc:abc/app.bsky.feed.post/3kzzrkey", cid="c")
        return f

    def __getattr__(self, name):
        if name in ("send_post", "send_video", "send_images"):
            return self._ok(name)
        raise AttributeError(name)


def test_bluesky_attaches_a_ready_video_with_its_aspect_ratio(cfg, tmp_path, monkeypatch):
    cfg.read_dict({"Bluesky": {"handle": "kongaloosh.com", "app_password": "x"}})
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "clip-0.mp4").write_bytes(b"\0" * 100)
    (tmp_path / "data" / "clip-0.meta.json").write_text(json.dumps({"width": 1920, "height": 1080, "duration": 19}))
    fake = FakeBsky()
    with patch.object(syn, "_bluesky_client", return_value=fake):
        url = syn.bluesky({"content": "Reef Sharks!", "category": ["scuba"], "video": ["data/clip-0.mp4"]},
                          "https://kongaloosh.com/e/2026/07/10/reef-shark")
    assert url == "https://bsky.app/profile/kongaloosh.com/post/3kzzrkey"
    (name, args, kwargs), = fake.calls
    assert name == "send_video" and kwargs["video"] == b"\0" * 100
    assert (kwargs["video_aspect_ratio"].width, kwargs["video_aspect_ratio"].height) == (1920, 1080)
    text = args[0].build_text()
    assert "Reef Sharks!" in text and "kongaloosh.com/e/2026/07/10/reef-shark" in text and "#scuba" in text
    facets = args[0].build_facets()
    kinds = {f.features[0].py_type for f in facets}
    assert kinds == {"app.bsky.richtext.facet#link", "app.bsky.richtext.facet#tag"}


def test_bluesky_falls_back_to_text_when_the_video_is_too_big(cfg, tmp_path, monkeypatch):
    cfg.read_dict({"Bluesky": {"handle": "kongaloosh.com", "app_password": "x", "max_video_bytes": "10"}})
    monkeypatch.chdir(tmp_path); (tmp_path / "data").mkdir()
    (tmp_path / "data" / "big-0.mp4").write_bytes(b"\0" * 100)
    (tmp_path / "data" / "big-0.meta.json").write_text("{}")
    fake = FakeBsky()
    with patch.object(syn, "_bluesky_client", return_value=fake):
        syn.bluesky({"content": "x", "video": ["data/big-0.mp4"]}, "https://kongaloosh.com/e/x")
    assert fake.calls[0][0] == "send_post"


def test_bluesky_attaches_up_to_four_small_photos(cfg, tmp_path, monkeypatch):
    cfg.read_dict({"Bluesky": {"handle": "kongaloosh.com", "app_password": "x"}})
    monkeypatch.chdir(tmp_path); (tmp_path / "data").mkdir()
    photos = []
    for i in range(6):
        p = tmp_path / "data" / f"p{i}.jpg"; p.write_bytes(b"\xff" * (10 if i != 2 else syn.BLUESKY_IMAGE_MAX + 1)); photos.append(f"data/p{i}.jpg")
    fake = FakeBsky()
    with patch.object(syn, "_bluesky_client", return_value=fake):
        syn.bluesky({"content": "pics", "photo": photos}, "https://kongaloosh.com/e/x")
    name, args, kwargs = fake.calls[0]
    assert name == "send_images" and len(kwargs["images"]) == 4, "four max, oversized one skipped"


def test_bluesky_text_only_post(cfg):
    cfg.read_dict({"Bluesky": {"handle": "kongaloosh.com", "app_password": "x"}})
    fake = FakeBsky()
    with patch.object(syn, "_bluesky_client", return_value=fake):
        syn.bluesky({"content": "just words"}, "https://kongaloosh.com/e/x")
    assert fake.calls[0][0] == "send_post"


# ---- fediverse (Mastodon API) ---------------------------------------------


def test_fediverse_uploads_video_polls_then_posts(cfg, tmp_path, monkeypatch):
    cfg.read_dict({"Fediverse": {"instance": "https://social.kongaloosh.com/", "access_token": "tok"}})
    monkeypatch.chdir(tmp_path); (tmp_path / "data").mkdir()
    (tmp_path / "data" / "clip-0.mp4").write_bytes(b"\0" * 10)
    (tmp_path / "data" / "clip-0.meta.json").write_text(json.dumps({"width": 1, "height": 1, "duration": 1}))
    posts, gets = [], []

    def fake_post(url, **kw):
        posts.append((url, kw))
        if url.endswith("/api/v2/media"):
            return Mock(status_code=202, json=lambda: {"id": "m1"}, raise_for_status=lambda: None)
        return Mock(status_code=200, json=lambda: {"url": "https://social.kongaloosh.com/@alex/statuses/01ABC"}, raise_for_status=lambda: None)

    def fake_get(url, **kw):
        gets.append(url)
        return Mock(status_code=200, json=lambda: {"id": "m1", "url": "https://social.kongaloosh.com/fileserver/x.mp4"})

    with patch.object(syn.requests, "post", side_effect=fake_post), patch.object(syn.requests, "get", side_effect=fake_get), \
         patch.object(syn.time, "sleep"):
        url = syn.fediverse({"content": "Reef Sharks!", "category": ["scuba"], "video": ["data/clip-0.mp4"]},
                            "https://kongaloosh.com/e/2026/07/10/reef-shark")

    assert url == "https://social.kongaloosh.com/@alex/statuses/01ABC"
    assert posts[0][0] == "https://social.kongaloosh.com/api/v2/media" and posts[0][1]["headers"] == {"Authorization": "Bearer tok"}
    assert gets == ["https://social.kongaloosh.com/api/v1/media/m1"], "202 means processing: poll once until it has a URL"
    status = posts[1]
    assert status[0] == "https://social.kongaloosh.com/api/v1/statuses"
    assert status[1]["data"]["media_ids[]"] == ["m1"] and status[1]["data"]["visibility"] == "public"
    assert "https://kongaloosh.com/e/2026/07/10/reef-shark" in status[1]["data"]["status"] and "#scuba" in status[1]["data"]["status"]


# ---- the entry point -------------------------------------------------------


def test_syndicate_records_urls_and_isolates_failures(cfg, tmp_path):
    cfg.read_dict({"Syndication": {"targets": "bluesky, fediverse, bridgy_fed"}, "Fediverse": {"instance": "https://social.kongaloosh.com", "access_token": "t"}})
    path, _ = entry_file(tmp_path)
    with patch.dict(syn.TARGETS, {
        "bluesky": lambda e, s: "https://bsky.app/profile/kongaloosh.com/post/r1",
        "fediverse": lambda e, s: (_ for _ in ()).throw(RuntimeError("instance down")),
        "bridgy_fed": lambda e, s: None,
    }):
        out = syn.syndicate(path, "https://kongaloosh.com/e/x")
    assert out["bluesky"] == {"url": "https://bsky.app/profile/kongaloosh.com/post/r1"}
    assert "instance down" in out["fediverse"]["error"]
    assert out["bridgy_fed"] == {"url": None}
    assert json.load(open(path))["syndication"] == ["https://bsky.app/profile/kongaloosh.com/post/r1"]


def test_syndicate_skips_a_network_the_entry_already_links(cfg, tmp_path):
    cfg.read_dict({"Syndication": {"targets": "bluesky"}})
    path, _ = entry_file(tmp_path, syndication=["https://bsky.app/profile/kongaloosh.com/post/old"])
    called = []
    with patch.dict(syn.TARGETS, {"bluesky": lambda e, s: called.append(1) or "x"}):
        out = syn.syndicate(path, "https://kongaloosh.com/e/x")
    assert called == [] and "skipped" in out["bluesky"]


def test_syndicate_never_raises_on_unknown_target_or_missing_entry(cfg, tmp_path):
    cfg.read_dict({"Syndication": {"targets": "nope"}})
    path, _ = entry_file(tmp_path)
    assert syn.syndicate(path, "https://kongaloosh.com/e/x") == {"nope": {"error": "unknown target"}}
    assert "error" in syn.syndicate(str(tmp_path / "missing.json"), "https://k/e/x")["_entry"]


def test_bridgy_bluesky_returns_the_url_bridgy_created(cfg):
    with patch.object(syn.mentioner, "send_bridgy_webmention", return_value=(201, json.dumps({"url": "https://bsky.app/profile/alexkearney.com/post/z"}))):
        assert syn.bridgy_bluesky({}, "https://k/e/x") == "https://bsky.app/profile/alexkearney.com/post/z"
    with patch.object(syn.mentioner, "send_bridgy_webmention", return_value=(404, "<!doctype html>")):
        with pytest.raises(RuntimeError):
            syn.bridgy_fed({}, "https://k/e/x")


def test_labels_by_host(cfg):
    cfg.read_dict({"Fediverse": {"instance": "https://social.kongaloosh.com", "access_token": "t"}})
    assert syn.label_for("https://bsky.app/profile/x/post/y") == "On Bluesky"
    assert syn.label_for("https://twitter.com/kongaloosh/status/1") == "On Twitter"
    assert syn.label_for("https://www.instagram.com/p/abc/") == "On Instagram"
    assert syn.label_for("https://social.kongaloosh.com/@alex/statuses/1") == "On the fediverse"
    assert syn.label_for("https://example.org/p/1") == "On example.org"


def test_entry_template_renders_the_syndication_list():
    src = open("templates/entry.html", encoding="utf-8").read()
    assert "entry.syndication" in src and "syndication_label(url)" in src
    assert 'class="u-syndication"' in src
