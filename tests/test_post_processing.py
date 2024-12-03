import pytest
from datetime import datetime
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
from werkzeug.datastructures import FileStorage
from kongaloosh import post_from_request, BlogPost, DraftPost, Travel, app
from io import BytesIO
from PIL import Image


@pytest.fixture
def make_request():
    """Helper fixture to create test requests"""

    def _make_request(form_data=None, files=None):
        builder = EnvironBuilder(method="POST", data=form_data)
        if files:
            for key, file_list in files.items():
                if isinstance(file_list, list):
                    for file in file_list:
                        builder.files.add_file(key, file[0], file[1])
                else:
                    builder.files.add_file(key, file_list[0], file_list[1])
        env = builder.get_environ()
        return Request(env)

    return _make_request


@pytest.fixture
def create_test_image():
    """Create a test image in memory"""

    def _create_image():
        img = Image.new("RGB", (100, 100), color="red")
        img_io = BytesIO()
        img.save(img_io, "JPEG")
        img_io.seek(0)
        return img_io

    return _create_image


def test_create_new_blog_post(make_request):
    """Test creating a new blog post"""
    with app.test_request_context():
        request = make_request(
            {
                "title": "Test Post",
                "content": "Test Content",
                "category": "test, blog",
                "summary": "Test Summary",
            }
        )

        result = post_from_request(request)

        assert isinstance(result, BlogPost)
        assert result.title == "Test Post"
        assert result.content == "Test Content"
        assert result.category == ["test", "blog"]
        assert result.summary == "Test Summary"
        assert result.u_uid is not None
        assert result.published is not None


def test_create_draft_post(make_request):
    """Test creating a draft post"""
    with app.test_request_context():
        request = make_request(
            {
                "title": "Draft Post",
                "content": "Draft Content",
                "Save": "true",  # Indicates draft save
            }
        )

        result = post_from_request(request)

        assert isinstance(result, DraftPost)
        assert result.title == "Draft Post"
        assert result.content == "Draft Content"
        assert result.url.startswith("/drafts/")
        assert "draft-" in result.slug or result.slug == "draft-post"


def test_update_existing_post(make_request):
    """Test updating an existing post"""
    with app.test_request_context():
        existing_post = BlogPost(
            title="Original Title",
            content="Original Content",
            slug="original-slug",
            url="/e/2024/03/01/original-slug",
            published=datetime.now(),
            u_uid="test-uuid",
        )

        request = make_request({"title": "Updated Title", "content": "Updated Content"})

        result = post_from_request(request, existing_post)

        assert isinstance(result, BlogPost)
        assert result.title == "Updated Title"
        assert result.content == "Updated Content"
        assert result.slug == "original-slug"  # Should preserve original slug
        assert result.url == "/e/2024/03/01/original-slug"  # Should preserve URL
        assert result.u_uid == "test-uuid"  # Should preserve UUID


def test_post_with_photos(make_request, create_test_image, tmp_path):
    """Test creating a post with photos"""
    with app.test_request_context():
        test_image = create_test_image()
        request = make_request(
            form_data={
                "title": "Photo Post",
                "content": "Post with Photos",
                "photo": "existing1.jpg, existing2.jpg",
            },
            files={"photo_file[]": [(test_image, "new_photo.jpg")]},
        )

        with pytest.MonkeyPatch.context() as m:
            m.setattr("os.getcwd", lambda: str(tmp_path))
            result = post_from_request(request)

        assert isinstance(result, BlogPost)
        assert "existing1.jpg" in result.photo
        assert "existing2.jpg" in result.photo
        assert any("new_photo.jpg" in photo for photo in result.photo)


def test_post_with_travel_data(make_request):
    """Test creating a post with travel data"""
    with app.test_request_context():
        request = make_request(
            {
                "title": "Travel Post",
                "content": "Travel Content",
                "geo[]": ["geo:45.5231,-122.6765"],
                "location[]": ["Portland, OR"],
                "date[]": ["2024-03-01"],
            }
        )

        result = post_from_request(request)

        assert isinstance(result, BlogPost)
        assert isinstance(result.travel, Travel)
        assert len(result.travel.trips) == 1
        assert result.travel.trips[0].location == "geo:45.5231,-122.6765"
        assert result.travel.trips[0].location_name == "Portland, OR"


def test_invalid_post_data(make_request):
    """Test handling of invalid post data"""
    with app.test_request_context():
        request = make_request(
            {"title": "Invalid Post", "published": "not-a-date"}  # Invalid date format
        )

        with pytest.raises(ValueError) as exc_info:
            post_from_request(request)
        assert "Invalid blog post data" in str(exc_info.value)
