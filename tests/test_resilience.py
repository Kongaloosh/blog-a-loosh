"""Tests for outbound-call resilience, upload streaming, and key handling.

These cover the failure modes behind the September 2026 outage: outbound HTTP
calls with no timeout wedged every worker thread until the process ran out of
file descriptors and stopped accepting connections.
"""

import io
import json
import os
from unittest.mock import Mock, patch

import pytest
import requests
from werkzeug.datastructures import FileStorage
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

import kongaloosh
from kongaloosh import (
    HTTP_TIMEOUT,
    Travel,
    announce_post,
    app,
    handle_travel_data,
    handle_uploaded_files,
)
from pysrc.post import Travel as TravelModel


def make_request(form_data):
    return Request(EnvironBuilder(method="POST", data=form_data).get_environ())


TRIP_FORM = {
    "geo[]": ["geo:45.5231,-122.6765"],
    "location[]": ["Portland, OR"],
    "date[]": ["2024-03-01"],
}


# --------------------------------------------------------------------------
# Every outbound call must carry a timeout.
# --------------------------------------------------------------------------


def test_every_requests_call_sets_a_timeout():
    """A call without timeout= blocks forever and pins a worker thread."""
    import ast

    offenders = []
    for path in (
        "kongaloosh.py",
        "pysrc/python_webmention/mentioner.py",
        "pysrc/authentication/indieauth.py",
    ):
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("get", "post", "head", "put", "delete")
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "requests"
                and not any(k.arg == "timeout" for k in node.keywords)
            ):
                offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], f"requests call(s) without a timeout: {offenders}"


def test_travel_map_fetch_passes_timeout():
    with app.test_request_context():
        with patch("requests.get") as mock_get:
            mock_get.return_value.content = b"map"
            handle_travel_data(make_request(TRIP_FORM))
        assert mock_get.call_args.kwargs.get("timeout") == HTTP_TIMEOUT


# --------------------------------------------------------------------------
# A slow or failing remote must degrade, not 500.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        requests.exceptions.Timeout("timed out"),
        requests.exceptions.ConnectionError("refused"),
    ],
)
def test_travel_page_survives_map_failure(failure):
    """The travel page renders without a map rather than raising."""
    with app.test_request_context():
        with patch("requests.get", side_effect=failure):
            result = handle_travel_data(make_request(TRIP_FORM))

    assert isinstance(result, Travel)
    assert result.map_data is None
    assert len(result.trips) == 1  # trip data survives the failed fetch


def test_announce_post_swallows_network_errors():
    """Syndication runs after the entry is saved, so it must never raise."""
    with app.test_request_context():
        with patch("requests.post", side_effect=requests.exceptions.Timeout()):
            result = announce_post("https://example.com/e/x")
    assert set(result) == {"fediverse", "bluesky"}
    assert all(status is None for status, _ in result.values())


def test_announce_post_swallows_error_status():
    with app.test_request_context():
        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=503, text="unavailable")
            result = announce_post("https://example.com/e/x")
        assert mock_post.call_args.kwargs.get("timeout") == HTTP_TIMEOUT
    assert result["fediverse"][0] == 503


def test_syndicate_continues_after_one_bad_target():
    """One unreachable reply target must not stop the remaining ones."""
    post = Mock(url="/e/2026/1/1/x", in_reply_to=["https://a.example", "https://b.example"])
    calls = []

    def flaky(url, **kwargs):
        calls.append(kwargs["data"]["target"])
        if kwargs["data"]["target"] == "https://a.example":
            raise requests.exceptions.ConnectionError("down")
        return Mock(status_code=200, text="ok")

    with app.test_request_context():
        with patch("requests.post", side_effect=flaky):
            kongaloosh.syndicate_from_form(None, post)

    assert calls == ["https://a.example", "https://b.example"]


# --------------------------------------------------------------------------
# The Google Maps key must not be serialised into stored post data.
# --------------------------------------------------------------------------


def test_map_url_is_not_serialised():
    travel = TravelModel(map_data=b"x", map_url="https://maps.googleapis.com/s?key=SEKRIT")

    assert travel.map_url is not None, "still available in memory"
    for dumped in (travel.model_dump(), travel.model_dump(mode="json")):
        assert "map_url" not in dumped
        assert "SEKRIT" not in json.dumps(dumped, default=str)


def test_stored_post_data_contains_no_api_key():
    """Regression guard: the live key was previously written into post JSON."""
    key = kongaloosh.GOOGLE_MAPS_KEY
    if not key:
        pytest.skip("no Google Maps key configured")

    leaked = []
    for root, _dirs, files in os.walk("data"):
        for name in files:
            if not name.endswith(".json"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8", errors="ignore") as fh:
                if key in fh.read():
                    leaked.append(path)
    assert leaked == [], f"API key present in stored post data: {leaked}"


# --------------------------------------------------------------------------
# Large uploads must stream to disk, not buffer in RAM.
# --------------------------------------------------------------------------


class _CountingStream(io.BytesIO):
    """BytesIO that records the largest single read it served."""

    def __init__(self, data):
        super().__init__(data)
        self.largest_read = 0

    def read(self, size=-1):
        chunk = super().read(size)
        self.largest_read = max(self.largest_read, len(chunk))
        return chunk


def _upload_request(filename, payload):
    stream = _CountingStream(payload)
    storage = FileStorage(
        stream=stream, filename=filename, content_type="video/quicktime"
    )
    builder = EnvironBuilder(method="POST", data={"media_file[]": storage})
    return Request(builder.get_environ()), stream


def test_video_upload_streams_in_chunks(tmp_path):
    """A 12MB upload must never be read into memory in one go.

    The old code did len(file.read()) and then content = file.read(), i.e. two
    full-size allocations; a 181MB video would not fit in this host's RAM.
    """
    payload = b"\0" * (12 * 1024 * 1024)
    request, _ = _upload_request("clip.mov", payload)

    with patch.object(kongaloosh, "BULK_UPLOAD_DIR", str(tmp_path)):
        with app.test_request_context():
            photos, videos = handle_uploaded_files(request)

    assert photos == []
    assert len(videos) == 1
    written = os.path.join(str(tmp_path), "clip.mov")
    assert os.path.getsize(written) == len(payload), "file written in full"


def test_video_upload_read_size_is_bounded(tmp_path):
    payload = b"\0" * (5 * 1024 * 1024)
    request, _ = _upload_request("clip.mov", payload)

    with patch.object(kongaloosh, "BULK_UPLOAD_DIR", str(tmp_path)):
        with app.test_request_context():
            # Werkzeug wraps the stream, so assert on the chunk size the
            # implementation asks for rather than on the raw stream.
            with patch("shutil.copyfileobj", wraps=kongaloosh.shutil.copyfileobj) as cp:
                handle_uploaded_files(request)

    assert cp.called, "upload must go through a streaming copy"
    chunk = cp.call_args.args[2] if len(cp.call_args.args) > 2 else None
    assert chunk == kongaloosh.VIDEO_COPY_CHUNK
    assert chunk <= 4 * 1024 * 1024, "chunk must stay small regardless of file size"


def test_mov_is_an_accepted_video_extension(tmp_path):
    request, _ = _upload_request("Holiday.MOV", b"\0" * 2048)

    with patch.object(kongaloosh, "BULK_UPLOAD_DIR", str(tmp_path)):
        with app.test_request_context():
            photos, videos = handle_uploaded_files(request)

    assert photos == [], ".mov must not be routed through image handling"
    assert len(videos) == 1
