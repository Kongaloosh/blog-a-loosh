import pytest
from PIL import Image
import io
import os
from kongaloosh import BULK_UPLOAD_DIR


@pytest.fixture
def create_test_image():
    """Create a test image in memory"""

    def _create_image(format="JPEG"):
        # Create a small test image
        image = Image.new("RGB", (100, 100), color="red")
        img_io = io.BytesIO()
        image.save(img_io, format=format)
        img_io.seek(0)
        return img_io

    return _create_image


def test_handle_single_file_upload(client, create_test_image, tmp_path):
    """Test uploading a single file"""
    # Setup
    test_image = create_test_image()
    data = {"photo_file[]": (test_image, "test.jpg", "image/jpeg")}

    # Test
    with pytest.MonkeyPatch.context() as m:
        m.setattr("os.getcwd", lambda: str(tmp_path))
        response = client.post("/upload", data=data, content_type="multipart/form-data")

    # Verify
    assert response.status_code == 200
    assert os.path.exists(os.path.join(tmp_path, BULK_UPLOAD_DIR, "test.jpg"))


def test_handle_multiple_file_uploads(client, create_test_image, tmp_path):
    """Test uploading multiple files"""
    # Setup
    data = {
        "photo_file[]": [
            (create_test_image(), "test1.jpg", "image/jpeg"),
            (create_test_image(), "test2.jpg", "image/jpeg"),
            (create_test_image(), "test3.jpg", "image/jpeg"),
        ]
    }

    # Test
    with pytest.MonkeyPatch.context() as m:
        m.setattr("os.getcwd", lambda: str(tmp_path))
        response = client.post("/upload", data=data, content_type="multipart/form-data")

    # Verify
    assert response.status_code == 200
    for i in range(1, 4):
        assert os.path.exists(os.path.join(tmp_path, BULK_UPLOAD_DIR, f"test{i}.jpg"))


def test_handle_no_files(client, tmp_path):
    """Test when no files are uploaded"""
    with pytest.MonkeyPatch.context() as m:
        m.setattr("os.getcwd", lambda: str(tmp_path))
        response = client.post("/upload", data={}, content_type="multipart/form-data")

    assert response.status_code == 200
    assert not os.listdir(os.path.join(tmp_path, BULK_UPLOAD_DIR))


def test_handle_empty_filename(client, create_test_image, tmp_path):
    """Test handling of files with empty filenames"""
    data = {"photo_file[]": (create_test_image(), "", "image/jpeg")}

    with pytest.MonkeyPatch.context() as m:
        m.setattr("os.getcwd", lambda: str(tmp_path))
        response = client.post("/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 200
    assert not os.listdir(os.path.join(tmp_path, BULK_UPLOAD_DIR))


def test_secure_filename_handling(client, create_test_image, tmp_path):
    """Test that filenames are properly secured"""
    data = {
        "photo_file[]": (
            create_test_image(),
            "../malicious../../file.jpg",
            "image/jpeg",
        )
    }

    with pytest.MonkeyPatch.context() as m:
        m.setattr("os.getcwd", lambda: str(tmp_path))
        response = client.post("/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 200
    assert os.path.exists(os.path.join(tmp_path, BULK_UPLOAD_DIR, "file.jpg"))
    assert not any(
        name
        for name in os.listdir(os.path.join(tmp_path, BULK_UPLOAD_DIR))
        if ".." in name
    )
