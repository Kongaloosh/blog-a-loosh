import pytest
from datetime import datetime
import os
import json
from unittest.mock import patch, mock_open, MagicMock
from pysrc.post import BlogPost


@pytest.fixture
def mock_db_entries():
    """Mock database entries with required fields"""
    current_time = datetime.now()
    return [
        ("entry1", current_time, "data/2024/03/01/entry1"),
        ("entry2", current_time, "data/2024/03/02/entry2"),
        ("entry3", current_time, "data/2024/02/28/entry3"),
    ]


@pytest.fixture
def mock_json_files():
    """Mock JSON file contents"""
    return {
        "data/2024/03/01/entry1.json": {
            "title": "Entry 1",
            "content": "Content 1",
            "published": "2024-03-01T12:00:00",
            "slug": "entry1",
            "url": "/e/2024/03/01/entry1",
            "u_uid": "uuid1",
        },
        "data/2024/03/02/entry2.json": {
            "title": "Entry 2",
            "content": "Content 2",
            "published": "2024-03-02T12:00:00",
            "slug": "entry2",
            "url": "/e/2024/03/02/entry2",
            "u_uid": "uuid2",
        },
        "data/2024/02/28/entry3.json": {
            "title": "Entry 3",
            "content": "Content 3",
            "published": "2024-02-28T12:00:00",
            "slug": "entry3",
            "url": "/e/2024/02/28/entry3",
            "u_uid": "uuid3",
        },
    }


def test_get_entries_by_date(client, db, mock_db_entries, mock_json_files):
    """Test getting entries ordered by date"""
    # Setup test data in db
    for slug, published, location in mock_db_entries:
        db.execute(
            "INSERT INTO entries (slug, published, location) VALUES (?, ?, ?)",
            (slug, published, location),
        )
    db.commit()

    # Mock file operations
    with patch("os.path.exists", return_value=True):

        def mock_json_open(filename, *args, **kwargs):
            filename = filename.replace("\\", "/")  # Normalize path separators
            content = mock_json_files[filename]
            return mock_open(read_data=json.dumps(content)).return_value

        with patch("builtins.open", side_effect=mock_json_open):
            from kongaloosh import get_entries_by_date

            entries = get_entries_by_date()

            # Verify we got all entries
            assert len(entries) == 3
            assert all(isinstance(entry, BlogPost) for entry in entries)
            assert entries[0].title == "Entry 1"
            assert entries[1].title == "Entry 2"
            assert entries[2].title == "Entry 3"


def test_get_entries_missing_files(client, db, mock_db_entries):
    """Test handling of missing JSON files"""
    # Setup test data in db
    for slug, published, location in mock_db_entries:
        db.execute(
            "INSERT INTO entries (slug, published, location) VALUES (?, ?, ?)",
            (slug, published, location),
        )
    db.commit()

    with patch("os.path.exists", return_value=False):
        from kongaloosh import get_entries_by_date

        entries = get_entries_by_date()
        assert entries == []


def test_get_entries_invalid_json(client, db, mock_db_entries):
    """Test handling of invalid JSON files"""
    # Setup test data in db
    for slug, published, location in mock_db_entries:
        db.execute(
            "INSERT INTO entries (slug, published, location) VALUES (?, ?, ?)",
            (slug, published, location),
        )
    db.commit()

    with patch("os.path.exists", return_value=True):
        mock_file = mock_open(read_data="invalid json content")
        with patch("builtins.open", mock_file):
            from kongaloosh import get_entries_by_date

            entries = get_entries_by_date()
            assert entries == []


def test_get_entries_db_error(client):
    """Test handling of database errors"""
    # Create a mock db with an execute method that raises an exception
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("DB Error")

    with patch("flask.g.db", mock_db):
        from kongaloosh import get_entries_by_date

        with pytest.raises(Exception) as exc_info:
            entries = get_entries_by_date()
        assert str(exc_info.value) == "DB Error"
