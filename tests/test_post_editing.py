from pysrc.post import ReplyTo
import pytest
import json
from datetime import datetime
from pathlib import Path
from pydantic import ValidationError
from kongaloosh import get_post_for_editing, BlogPost, DraftPost


@pytest.fixture
def temp_post_file(tmp_path):
    """Create a temporary post file for testing"""

    def _create_post_file(data):
        post_path = tmp_path / "test_post"
        with open(f"{post_path}.json", "w") as f:
            json.dump(data, f)
        return str(post_path)

    return _create_post_file


def test_load_valid_blog_post(temp_post_file):
    """Test loading a valid blog post"""
    post_data = {
        "title": "Test Post",
        "content": "Test Content",
        "published": "2024-03-01T12:00:00",
        "slug": "test-post",
        "url": "/e/2024/03/01/test-post",
        "u_uid": "test-uuid",
    }
    file_path = temp_post_file(post_data)

    result = get_post_for_editing(file_path)

    assert isinstance(result, BlogPost)
    assert result.title == "Test Post"
    assert result.content == "Test Content"
    assert result.published == datetime.fromisoformat("2024-03-01T12:00:00")


def test_load_draft_post(temp_post_file):
    """Test loading a draft post"""
    post_data = {
        "title": "Draft Post",
        "content": "Draft Content",
        "slug": "draft-post",
        "url": "/drafts/2024/03/01/draft-post",
    }
    file_path = temp_post_file(post_data)

    result = get_post_for_editing(file_path)

    assert isinstance(result, DraftPost)
    assert result.title == "Draft Post"
    assert result.content == "Draft Content"


def test_handle_reply_to_list(temp_post_file):
    """Test handling of in_reply_to list"""
    post_data = {
        "title": "Reply Post",
        "content": "Reply Content",
        "slug": "reply-post",
        "url": "/e/2024/03/01/reply-post",
        "in_reply_to": [
            "http://example.com/1",
            "http://example.com/2",
        ],
        "published": "2024-03-01T12:00:00",
        "u_uid": "test-uuid",
    }
    file_path = temp_post_file(post_data)

    result = get_post_for_editing(file_path)

    assert isinstance(result, BlogPost)
    assert result.in_reply_to is not None
    assert len(result.in_reply_to) == 2
    assert isinstance(result.in_reply_to[0], ReplyTo)
    assert isinstance(result.in_reply_to[1], ReplyTo)
    assert str(result.in_reply_to[0].url) == "http://example.com/1"
    assert str(result.in_reply_to[1].url) == "http://example.com/2"


def test_handle_invalid_dates(temp_post_file):
    """Test handling of invalid date formats"""
    post_data = {
        "title": "Date Post",
        "content": "Date Content",
        "slug": "date-post",
        "url": "/e/2024/03/01/date-post",
        "published": "2024-03-01T12:00:00",
        "u_uid": "test-uuid",
        "dt_start": "also-invalid",
    }
    file_path = temp_post_file(post_data)

    result = get_post_for_editing(file_path)

    assert isinstance(result, BlogPost)
    assert result.dt_start is None


def test_file_not_found():
    """Test handling of non-existent file"""
    with pytest.raises(FileNotFoundError) as exc_info:
        get_post_for_editing("nonexistent/path")
    assert "Post not found" in str(exc_info.value)


def test_invalid_json(tmp_path):
    """Test handling of invalid JSON file"""
    post_path = tmp_path / "invalid_post"
    with open(f"{post_path}.json", "w") as f:
        f.write("invalid json content")

    with pytest.raises(json.JSONDecodeError):
        get_post_for_editing(str(post_path))


def test_invalid_post_data(temp_post_file):
    """Test handling of invalid post data"""
    post_data = {
        # Missing required fields
        "title": "Invalid Post"
    }
    file_path = temp_post_file(post_data)

    with pytest.raises(ValueError) as exc_info:
        get_post_for_editing(file_path)
    assert "Invalid blog post data" in str(exc_info.value)
