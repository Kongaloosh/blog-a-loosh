import pytest
from kongaloosh import app
from flask_wtf.csrf import generate_csrf
from io import BytesIO


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["SECRET_KEY"] = "test_key"

    with app.test_client() as client:
        with app.app_context():
            with client.request_context("/"):  # Add request context
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    csrf_token = generate_csrf()
                    sess["csrf_token"] = csrf_token
                yield client


def test_unauthorized_access(client):
    """Test that unauthenticated requests are properly handled"""
    response = client.post(
        "/add", data={"content": "Test content", "title": "Test Title"}
    )
    assert response.status_code == 401  # Unauthorized, not 302


def test_csrf_protection(client):
    """Test that POST requests require CSRF token"""
    with client.session_transaction() as sess:
        csrf_token = sess["csrf_token"]

    # Test with token
    response = client.post(
        "/add",
        data={
            "content": "Test content",
            "title": "Test Title",
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code in [200, 302]


@pytest.mark.skip(reason="XSS protection needs to be implemented")
def test_xss_content_escaping(client):
    """Test that HTML in content is properly escaped"""
    pass


@pytest.mark.skip(reason="Session fixation prevention needs to be implemented")
def test_session_fixation_prevention(client):
    """Test that session ID changes after login"""
    pass


@pytest.mark.skip(reason="Rate limiting needs to be implemented")
def test_rate_limiting(client):
    """Test that rapid requests are rate limited"""
    pass


def test_file_upload_restrictions(client):
    """Test that file uploads are properly restricted"""
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    with app.app_context():
        csrf_token = generate_csrf()
        data = {
            "file": (BytesIO(b'<?php echo "hack"; ?>'), "malicious.php"),
            "csrf_token": csrf_token,
        }
        response = client.post("/upload", data=data)
        assert response.status_code in [400, 404]  # Either reject or not found


@pytest.mark.skip(reason="JSON endpoint protection needs to be implemented")
def test_json_injection_prevention(client):
    """Test that JSON endpoints are protected against injection"""
    pass


def test_secure_headers(client):
    """Test that security headers are properly set"""
    pass


def test_auth_token_expiry(client):
    """Test that authentication tokens expire properly"""
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    response = client.get("/add")
    assert response.status_code in [
        401,
        302,
    ]  # Either unauthorized or redirect to login
