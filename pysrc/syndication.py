"""POSSE: publish a finished entry to the networks it should appear on.

Targets are chosen in config.ini. With no [Syndication] section this does
exactly what the site did before: two webmentions to Bridgy.

    [Syndication]
    targets = bridgy_fed, bridgy_bluesky

    [Bluesky]                 # target "bluesky": post directly to your own account
    handle = kongaloosh.com
    app_password = ...
    max_video_bytes = 52428800

    [Fediverse]               # target "fediverse": your GoToSocial/Mastodon account
    instance = https://social.kongaloosh.com
    access_token = ...

Each target receives the entry as stored and its canonical URL, does its
work, and returns the URL of the post it made (or None). Nothing here raises:
the entry is already saved and indexed, and a network being down must not
make a successful publish look failed. URLs come back into the entry's
`syndication` list, which the templates render as u-syndication links - the
IndieWeb marker that also lets Bridgy's backfeed match responses to posts.
"""

import configparser
import html
import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import requests

from pysrc import video_converter
from pysrc.python_webmention import mentioner

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read("config.ini")

DEFAULT_TARGETS = "bridgy_fed, bridgy_bluesky"
BLUESKY_TEXT_LIMIT = 290      # 300 graphemes, with a margin for emoji
BLUESKY_IMAGE_MAX = 950_000   # bytes; Bluesky refuses larger images
FEDIVERSE_TEXT_LIMIT = 4500   # GoToSocial's default cap is 5000
MEDIA_POLL_SECONDS = 60       # how long to wait for the instance to process a video


def targets() -> List[str]:
    raw = config.get("Syndication", "targets", fallback=DEFAULT_TARGETS)
    return [t.strip() for t in raw.split(",") if t.strip()]


# --------------------------------------------------------------------------
# Turning an entry into post material
# --------------------------------------------------------------------------


def plain_text(entry: Dict[str, Any]) -> str:
    """The entry as readable text: title, then content with markup removed."""
    parts = []
    if entry.get("title"):
        parts.append(str(entry["title"]).strip())
    content = entry.get("content") or ""
    try:
        import markdown

        rendered = markdown.markdown(content)
    except Exception:  # markdown is not worth failing over
        rendered = content
    text = re.sub(r"<[^>]+>", " ", rendered)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([.,;:!?])", r"\1", text)  # "a link ." from a stripped tag
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    if text:
        parts.append(text)
    return "\n\n".join(parts)


def hashtags(entry: Dict[str, Any], limit: int = 6) -> List[str]:
    """Categories as hashtag words: letters, digits, underscores only."""
    out: List[str] = []
    for c in entry.get("category") or []:
        tag = re.sub(r"[^\w]", "", str(c).replace("-", "").replace(" ", ""))
        if tag and not tag.isdigit() and tag.lower() not in {t.lower() for t in out}:
            out.append(tag)
    return out[:limit]


def link_label(url: str) -> str:
    """kongaloosh.com/e/2026/07/10/reef-shark - what the link shows as."""
    u = urlsplit(url)
    return (u.netloc + u.path).rstrip("/")


def fit_text(text: str, reserve: int, limit: int) -> str:
    """Cut text so that it plus `reserve` more characters fits in `limit`."""
    room = limit - reserve
    if room <= 0:
        return ""
    if len(text) <= room:
        return text
    cut = text[: room - 1]
    if " " in cut[room // 2:]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip() + "…"


def first_ready_video(entry: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    for v in entry.get("video") or []:
        path = str(v).lstrip("/")
        if video_converter.video_is_ready(path):
            return path, (video_converter.read_meta(path) or {})
    return None


def ready_photos(entry: Dict[str, Any], limit: int = 4, max_bytes: Optional[int] = None) -> List[str]:
    out = []
    for p in entry.get("photo") or []:
        path = str(p).lstrip("/")
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if max_bytes and size > max_bytes:
            continue
        out.append(path)
        if len(out) == limit:
            break
    return out


def alt_text(entry: Dict[str, Any]) -> str:
    return plain_text(entry)[:1000] or "Video"


# --------------------------------------------------------------------------
# Targets
# --------------------------------------------------------------------------


def bridgy_fed(entry: Dict[str, Any], source: str) -> Optional[str]:
    """Bridgy Fed learns about the post by webmention; it publishes no URL back."""
    status, body = mentioner.send_bridgy_webmention(
        source, mentioner.BRIDGY_FED_ENDPOINT, mentioner.BRIDGY_FED_TARGET
    )
    if status is None or status >= 300:
        raise RuntimeError(f"Bridgy Fed answered {status}: {body}")
    return None


def bridgy_bluesky(entry: Dict[str, Any], source: str) -> Optional[str]:
    """Bridgy (classic) publishes to Bluesky and answers 201 with the post URL."""
    status, body = mentioner.send_bridgy_webmention(
        source, mentioner.BRIDGY_BLUESKY_ENDPOINT, mentioner.BRIDGY_BLUESKY_TARGET
    )
    if status is None or status >= 300:
        raise RuntimeError(f"Bridgy answered {status}: {body}")
    try:
        return json.loads(body).get("url")
    except (ValueError, AttributeError):
        return None


def _bluesky_client():
    """Factory, so tests can substitute a fake without importing atproto."""
    from atproto import Client

    client = Client()
    client.login(config.get("Bluesky", "handle"), config.get("Bluesky", "app_password"))
    return client


def bluesky_text(entry: Dict[str, Any], source: str):
    """A TextBuilder: text, a link back to the entry, then hashtags as facets."""
    from atproto import client_utils

    tags = hashtags(entry)
    label = link_label(source)
    reserve = 1 + len(label) + sum(2 + len(t) for t in tags)
    body = fit_text(plain_text(entry), reserve, BLUESKY_TEXT_LIMIT)
    tb = client_utils.TextBuilder()
    if body:
        tb.text(body + "\n")
    tb.link(label, source)
    for t in tags:
        tb.text(" ").tag("#" + t, t)
    return tb


def bluesky(entry: Dict[str, Any], source: str) -> Optional[str]:
    """Post natively to the account in [Bluesky], with the video or photos attached."""
    from atproto import models

    client = _bluesky_client()
    text = bluesky_text(entry, source)
    alt = alt_text(entry)
    max_video = config.getint("Bluesky", "max_video_bytes", fallback=50 * 1024 * 1024)

    video = first_ready_video(entry)
    if video:
        path, meta = video
        with open(path, "rb") as fh:
            data = fh.read()
        if len(data) <= max_video:
            ratio = None
            if meta.get("width") and meta.get("height"):
                ratio = models.AppBskyEmbedDefs.AspectRatio(width=int(meta["width"]), height=int(meta["height"]))
            resp = client.send_video(text, video=data, video_alt=alt, video_aspect_ratio=ratio)
        else:
            logger.warning("video %s is %d bytes, over the Bluesky cap; posting text and link", path, len(data))
            resp = client.send_post(text)
    else:
        photos = ready_photos(entry, max_bytes=BLUESKY_IMAGE_MAX)
        if photos:
            images = [open(p, "rb").read() for p in photos]
            resp = client.send_images(text, images=images, image_alts=[alt] * len(images))
        else:
            resp = client.send_post(text)

    rkey = str(resp.uri).rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{config.get('Bluesky', 'handle')}/post/{rkey}"


def fediverse_text(entry: Dict[str, Any], source: str) -> str:
    tags = hashtags(entry)
    tail = "\n\n" + source + ("\n\n" + " ".join("#" + t for t in tags) if tags else "")
    body = fit_text(plain_text(entry), len(tail), FEDIVERSE_TEXT_LIMIT)
    return (body + tail).strip()


def _upload_media(base: str, headers: Dict[str, str], path: str, mime: str, alt: str) -> str:
    """Upload one file via the Mastodon API and wait until it is processed."""
    with open(path, "rb") as fh:
        r = requests.post(
            f"{base}/api/v2/media", headers=headers, data={"description": alt},
            files={"file": (os.path.basename(path), fh, mime)}, timeout=(5, 300),
        )
    r.raise_for_status()
    media_id = r.json()["id"]
    if r.status_code == 202:  # still processing (video); poll until it has a URL
        deadline = time.time() + MEDIA_POLL_SECONDS
        while time.time() < deadline:
            g = requests.get(f"{base}/api/v1/media/{media_id}", headers=headers, timeout=(5, 30))
            if g.status_code == 200 and g.json().get("url"):
                break
            time.sleep(2)
    return media_id


def fediverse(entry: Dict[str, Any], source: str) -> Optional[str]:
    """Post to the account in [Fediverse] over the Mastodon API (GoToSocial, Mastodon...)."""
    base = config.get("Fediverse", "instance").rstrip("/")
    headers = {"Authorization": "Bearer " + config.get("Fediverse", "access_token")}
    alt = alt_text(entry)

    media_ids = []
    video = first_ready_video(entry)
    if video:
        media_ids.append(_upload_media(base, headers, video[0], "video/mp4", alt))
    else:
        for p in ready_photos(entry):
            media_ids.append(_upload_media(base, headers, p, "image/jpeg", alt))

    data: Dict[str, Any] = {"status": fediverse_text(entry, source), "visibility": "public", "language": "en"}
    if media_ids:
        data["media_ids[]"] = media_ids
    r = requests.post(f"{base}/api/v1/statuses", headers=headers, data=data, timeout=(5, 60))
    r.raise_for_status()
    return r.json().get("url")


TARGETS: Dict[str, Callable[[Dict[str, Any], str], Optional[str]]] = {
    "bridgy_fed": bridgy_fed,
    "bridgy_bluesky": bridgy_bluesky,
    "bluesky": bluesky,
    "fediverse": fediverse,
}

# A target is skipped when the entry already links a post on its network.
TARGET_HOSTS = {
    "bluesky": lambda: "bsky.app",
    "bridgy_bluesky": lambda: "bsky.app",
    "fediverse": lambda: urlsplit(config.get("Fediverse", "instance", fallback="")).netloc,
}


# --------------------------------------------------------------------------
# The entry point
# --------------------------------------------------------------------------


def syndicate(entry_path: str, source: str) -> Dict[str, Dict[str, Any]]:
    """Publish the entry at entry_path to every configured target.

    Returns {target: {"url": ...} | {"error": ...} | {"skipped": ...}} and
    records new URLs in the entry file's `syndication` list. Never raises.
    """
    try:
        with open(entry_path, encoding="utf-8") as fh:
            entry = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("syndicate: cannot read %s: %s", entry_path, e)
        return {"_entry": {"error": str(e)}}

    existing = [str(u) for u in (entry.get("syndication") or [])]
    results: Dict[str, Dict[str, Any]] = {}
    new_urls: List[str] = []
    for name in targets():
        fn = TARGETS.get(name)
        if fn is None:
            results[name] = {"error": "unknown target"}
            logger.warning("syndicate: unknown target %r in config", name)
            continue
        host = TARGET_HOSTS.get(name, lambda: None)()
        if host and any(host in u for u in existing + new_urls):
            results[name] = {"skipped": f"already syndicated to {host}"}
            continue
        try:
            url = fn(entry, source)
        except Exception as e:  # one network must not stop the others
            logger.warning("syndicate: %s failed for %s: %s", name, source, e)
            results[name] = {"error": str(e)[:300]}
            continue
        results[name] = {"url": url}
        if url and url not in existing and url not in new_urls:
            new_urls.append(url)
        logger.info("syndicate: %s -> %s", name, url or "ok")

    if new_urls:
        entry["syndication"] = existing + new_urls
        tmp = entry_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, entry_path)
    return results


def label_for(url: str) -> str:
    """Human label for a syndication link, by host."""
    host = urlsplit(str(url)).netloc.lower().removeprefix("www.")
    if host == "bsky.app":
        return "On Bluesky"
    if host in ("twitter.com", "x.com"):
        return "On Twitter"
    if host == "instagram.com":
        return "On Instagram"
    if host == "facebook.com":
        return "On Facebook"
    fedi = urlsplit(config.get("Fediverse", "instance", fallback="")).netloc.lower()
    if fedi and host == fedi:
        return "On the fediverse"
    return "On " + host
