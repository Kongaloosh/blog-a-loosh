import pytest
from unittest.mock import patch, mock_open
from kongaloosh import app
import sqlite3
from datetime import datetime
import json
import tempfile
import os


@pytest.fixture
def test_json_file():
    """Create a temporary test JSON file"""
    test_data = {
        "title": "Test Entry",
        "content": "Test Content",
        "published": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "slug": "test-entry",
        "url": "https://kongaloosh.com/e/test-entry",
        "u_uid": "tag:kongaloosh.com,2024:test-entry",
        "type": "article",
    }

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(test_data, f)
        temp_path = f.name

    yield temp_path

    # Cleanup after test
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_db(test_json_file):
    """Create a mock database connection"""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row

    # Use the actual schema.sql file
    with app.open_resource("schema.sql", mode="r") as f:
        db.executescript(f.read())

    # Add test data pointing to our temp file
    current_time = datetime.now()
    db.execute(
        """INSERT INTO entries (slug, published, location) 
                 VALUES (?, ?, ?)""",
        ("test-entry", current_time, test_json_file[:-5]),
    )  # Remove .json as it's added by parser

    db.commit()
    return db


@pytest.fixture
def client(mock_db):
    """Create a test client with mocked db.

    The application context wraps the client: leaving the client runs
    teardown_request, which needs the context to still be alive.
    """
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "test_key"

    with patch("kongaloosh.connect_db", return_value=mock_db):
        with app.app_context():
            with app.test_client() as client:
                yield client


def test_homepage_returns_200(client):
    """Test that homepage loads successfully"""
    response = client.get("/")
    assert response.status_code == 200


def test_nonexistent_page_returns_404(client):
    """Test that non-existent pages return 404"""
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404


def test_unauthorized_post_returns_401(client):
    """Test that posting without login returns 401"""
    response = client.post(
        "/add", data={"content": "Test content", "title": "Test Title"}
    )
    assert response.status_code == 401


def test_draft_save_redirects_correctly(client, tmp_path, monkeypatch):
    """Saving from /add writes a draft file and lands on its edit page.

    Drafts are files, not database rows - create_json_entry only inserts
    into entries for published posts - so the old database assertion could
    never hold. Storage is redirected to a temp dir so the test never
    writes into the real drafts folder. The draft path doubles as the
    redirect URL, so it has to stay relative: hence chdir rather than an
    absolute path.
    """
    import kongaloosh
    from pysrc.file_management import file_parser

    monkeypatch.chdir(tmp_path)
    (tmp_path / "drafts").mkdir()
    monkeypatch.setattr(kongaloosh, "DRAFT_STORAGE", "drafts")
    monkeypatch.setattr(file_parser, "DRAFTS_STORAGE", "drafts")

    with client.session_transaction() as sess:
        sess["logged_in"] = True

    response = client.post(
        "/add",
        data={
            "content": "Test draft content",
            "title": "Test Draft",
            "Save": "true",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Test Draft" in response.data or b"Test draft content" in response.data

    saved = list((tmp_path / "drafts").glob("*.json"))
    assert len(saved) == 1, saved
    assert "test-draft" in saved[0].name


def test_atom_feed_content_type(client):
    """Test that atom feed returns correct content type"""
    response = client.get("/", headers={"Accept": "application/atom+xml"})
    assert "application/atom+xml" in response.headers["Content-Type"]


def test_activitypub_content_type(client):
    """Test that ActivityPub request returns correct content type"""
    response = client.get("/", headers={"Accept": "application/as+json"})
    assert response.headers["Content-Type"] == "application/json"
