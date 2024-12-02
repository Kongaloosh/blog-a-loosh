import pytest
from datetime import datetime
from pysrc.post import BlogPost, DraftPost
from pysrc.file_management.file_parser import create_json_entry, update_json_entry


def test_create_draft_post():
    """Test creating a draft post"""
    draft = DraftPost(
        content="Test content",
        slug="test-draft",
        url="/drafts/test-draft",
        title="Test Draft",
    )
    assert draft.content == "Test content"
    assert draft.slug == "test-draft"
    assert draft.title == "Test Draft"


def test_convert_draft_to_blog_post():
    """Test converting a draft to a blog post"""
    draft = DraftPost(
        content="Test content",
        slug="test-draft",
        url="/drafts/test-draft",
        title="Test Draft",
    )

    blog_post = BlogPost(
        **draft.model_dump(), published=datetime.now(), u_uid="test-uuid"
    )

    assert blog_post.content == draft.content
    assert blog_post.title == draft.title
    assert blog_post.u_uid == "test-uuid"
    assert blog_post.published is not None


def test_blog_post_validation():
    """Test blog post validation"""
    with pytest.raises(ValueError):
        # Should fail without required fields
        BlogPost(content="Test content", slug="test-post")
