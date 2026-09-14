"""Tests for upload handling.

These previously posted to a /upload route that does not exist, so every one
of them asserted 200 against a 404. They now exercise the functions the app
actually uses: handle_photo_files, which pulls photo_file[] off the request,
and handle_uploaded_files, which writes media to disk.
"""

import io
import os

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

import kongaloosh
from kongaloosh import app, handle_photo_files, handle_uploaded_files


@pytest.fixture
def create_test_image():
    """Create a test image in memory"""

    def _create_image(format="JPEG"):
        image = Image.new("RGB", (100, 100), color="red")
        img_io = io.BytesIO()
        image.save(img_io, format=format)
        img_io.seek(0)
        return img_io

    return _create_image


def _request(files):
    """Build a multipart request from {field: [(stream, filename), ...]}."""
    data = {}
    for field, items in files.items():
        data[field] = [
            FileStorage(stream=stream, filename=name, content_type="image/jpeg")
            for stream, name in items
        ]
    builder = EnvironBuilder(method="POST", data=data)
    return Request(builder.get_environ())


def test_handle_single_file_upload(create_test_image):
    request = _request({"photo_file[]": [(create_test_image(), "test.jpg")]})

    files = handle_photo_files(request)

    assert len(files) == 1
    assert files[0].filename == "test.jpg"


def test_handle_multiple_file_uploads(create_test_image):
    request = _request(
        {
            "photo_file[]": [
                (create_test_image(), "test1.jpg"),
                (create_test_image(), "test2.jpg"),
                (create_test_image(), "test3.jpg"),
            ]
        }
    )

    files = handle_photo_files(request)

    assert [f.filename for f in files] == ["test1.jpg", "test2.jpg", "test3.jpg"]


def test_handle_no_files():
    """No photo fields at all is an error the caller has to handle."""
    request = Request(EnvironBuilder(method="POST", data={}).get_environ())

    with pytest.raises(ValueError):
        handle_photo_files(request)


def test_handle_empty_filename(create_test_image, tmp_path):
    """A part with no filename must not be written to disk."""
    request = _request({"media_file[]": [(create_test_image(), "")]})

    with patch_upload_dir(tmp_path):
        photos, videos = handle_uploaded_files(request)

    assert photos == []
    assert videos == []
    assert os.listdir(tmp_path) == []


def test_secure_filename_handling(create_test_image, tmp_path):
    """A traversing filename must not escape the upload directory."""
    request = _request(
        {"media_file[]": [(create_test_image(), "../malicious../../file.jpg")]}
    )

    with patch_upload_dir(tmp_path):
        photos, _videos = handle_uploaded_files(request)

    assert len(photos) == 1
    # secure_filename flattens the separators; the result stays one component.
    assert os.listdir(tmp_path) == ["malicious.._.._file.jpg"]
    # Nothing may appear outside the upload directory.
    assert not os.path.exists(os.path.join(os.path.dirname(str(tmp_path)), "file.jpg"))


class patch_upload_dir:
    """Point BULK_UPLOAD_DIR at a temporary directory for one test."""

    def __init__(self, path):
        self.path = str(path)

    def __enter__(self):
        self._old = kongaloosh.BULK_UPLOAD_DIR
        kongaloosh.BULK_UPLOAD_DIR = self.path
        self._ctx = app.test_request_context()
        self._ctx.__enter__()
        return self

    def __exit__(self, *exc):
        self._ctx.__exit__(*exc)
        kongaloosh.BULK_UPLOAD_DIR = self._old
        return False
