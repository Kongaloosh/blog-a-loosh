from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime
from kongaloosh import get_most_popular_tags


@pytest.fixture
def tag_test_data():
    """Test data for tags"""
    current_time = datetime.now()
    return [
        ("post1", current_time, "python"),
        ("post1", current_time, "flask"),
        ("post2", current_time, "python"),
        ("post3", current_time, "javascript"),
        ("post4", current_time, "python"),
        ("post5", current_time, "note"),  # should be excluded
        ("post6", current_time, "image"),  # should be excluded
    ]


def test_get_most_popular_tags(client, db, tag_test_data):
    """Test getting popular tags"""
    # Setup test data
    for slug, published, category in tag_test_data:
        db.execute(
            "INSERT INTO categories (slug, published, category) VALUES (?, ?, ?)",
            (slug, published, category),
        )
    db.commit()

    # Get tags
    tags = get_most_popular_tags()

    # Verify results
    assert len(tags) == 3  # All non-excluded tags
    assert tags[0] == "python"  # Most used tag (3 occurrences)
    assert tags[1] in ["flask", "javascript"]  # These have equal count (1 each)
    assert tags[2] in ["flask", "javascript"]  # These have equal count (1 each)
    assert tags[1] != tags[2]  # Should be different tags


def test_get_most_popular_tags_empty(client, db):
    """Test getting tags when none exist"""
    tags = get_most_popular_tags()
    assert tags == []


def test_get_most_popular_tags_only_excluded(client, db):
    """Test when only excluded tags exist"""
    current_time = datetime.now()
    excluded_tags = [
        ("post1", current_time, "note"),
        ("post2", current_time, "image"),
        ("post3", current_time, "album"),
        ("post4", current_time, "bookmark"),
    ]

    for slug, published, category in excluded_tags:
        db.execute(
            "INSERT INTO categories (slug, published, category) VALUES (?, ?, ?)",
            (slug, published, category),
        )
    db.commit()

    tags = get_most_popular_tags()
    assert tags == []


def test_get_most_popular_tags_db_error(client):
    """Test handling of database errors"""
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("DB Error")

    with patch("flask.g.db", mock_db):
        with pytest.raises(Exception) as exc_info:
            tags = get_most_popular_tags()
            del tags
        assert str(exc_info.value) == "DB Error"
