import pytest
from datetime import datetime
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
from kongaloosh import process_form_data, PostFormData
from dateutil.parser import parse


@pytest.fixture
def make_request():
    """Helper fixture to create test requests"""

    def _make_request(form_data):
        builder = EnvironBuilder(method="POST", data=form_data)
        env = builder.get_environ()
        return Request(env)

    return _make_request


def test_process_basic_fields(make_request):
    """Test processing of basic text fields"""
    request = make_request(
        {"title": "Test Title", "content": "Test Content", "summary": "Test Summary"}
    )

    result = process_form_data(request)

    assert isinstance(result, PostFormData)
    assert result.title == "Test Title"
    assert result.content == "Test Content"
    assert result.summary == "Test Summary"


def test_process_categories(make_request):
    """Test processing of categories/tags"""
    request = make_request({"category": "python, flask, testing"})

    result = process_form_data(request)

    assert result.category == ["python", "flask", "testing"]


def test_process_published_date(make_request):
    """Test processing of published date"""
    test_date = "2024-03-01T12:00:00"
    request = make_request({"published": test_date})

    result = process_form_data(request)

    assert result.published == parse(test_date)


def test_process_published_date_default(make_request):
    """Test default published date when none provided"""
    request = make_request({})

    before = datetime.now()
    result = process_form_data(request)
    after = datetime.now()

    assert before <= result.published <= after


def test_process_reply_to(make_request):
    """Test processing of in-reply-to field"""
    request = make_request(
        {"in_reply_to": "http://example.com/1, http://example.com/2"}
    )

    result = process_form_data(request)

    assert result.in_reply_to == ["http://example.com/1", "http://example.com/2"]


def test_process_photos(make_request):
    """Test processing of existing photos"""
    request = make_request({"photo": "photo1.jpg, photo2.jpg, photo3.jpg"})

    result = process_form_data(request)

    assert result.photo == ["photo1.jpg", "photo2.jpg", "photo3.jpg"]


def test_process_empty_form(make_request):
    """Test processing of empty form"""
    request = make_request({})

    result = process_form_data(request)

    assert isinstance(result, PostFormData)
    assert result.title is None
    assert result.content is None
    assert result.summary is None
    assert result.category is None
    assert result.in_reply_to is None
    assert result.photo is None
    assert isinstance(result.published, datetime)


def test_process_whitespace_handling(make_request):
    """Test handling of whitespace in list fields"""
    request = make_request(
        {
            "category": " python ,  flask  , testing ",
            "in_reply_to": " http://example.com/1 , http://example.com/2 ",
            "photo": " photo1.jpg ,  photo2.jpg  ",
        }
    )

    result = process_form_data(request)

    assert result.category == ["python", "flask", "testing"]
    assert result.in_reply_to == ["http://example.com/1", "http://example.com/2"]
    assert result.photo == ["photo1.jpg", "photo2.jpg"]
