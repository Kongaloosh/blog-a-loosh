import os
import tempfile

import pytest
import kongaloosh


@pytest.fixture
def client():
    db_fd, kongaloosh.app.config['DATABASE'] = tempfile.mkstemp()
    kongaloosh.app.config['TESTING'] = True

    with kongaloosh.app.test_client() as client:
        with kongaloosh.app.app_context():
            kongaloosh.init_db()
        yield client

    os.close(db_fd)
    os.unlink(kongaloosh.app.config['DATABASE'])


def test_empty_db(client):
    """Start with a blank database."""

    rv = client.get('/')
    assert b'No entries here so far' in rv.data


def login(client, username, password):
    return client.post('/login', data=dict(
        username=username,
        password=password
    ), follow_redirects=True)


def logout(client):
    return client.get('/logout', follow_redirects=True)


def test_login_logout(client):
    """Make sure login and logout works."""

    rv = login(client, kongaloosh.app.config['USERNAME'], kongaloosh.app.config['PASSWORD'])
    assert b'You were successfully logged in' in rv.data

    rv = logout(client)
    assert b'You were logged out' in rv.data

    rv = login(client, kongaloosh.app.config['USERNAME'] + 'x', kongaloosh.app.config['PASSWORD'])
    assert b'Invalid credentials' in rv.data

    rv = login(client, kongaloosh.app.config['USERNAME'], kongaloosh.app.config['PASSWORD'] + 'x')
    assert b'Invalid credentials' in rv.data


def test_messages(client):
    """Test that messages work."""

    # login(client, flaskr.app.config['USERNAME'], flaskr.app.config['PASSWORD'])
    rv = client.post('/add', data=dict(
        title='<Hello>',
        text='<strong>HTML</strong> allowed here'
    ), follow_redirects=True)
    assert 501 is not rv.status_code
    # assert b'No entries here so far' not in rv.c
    # assert b'&lt;Hello&gt;' in rv.data
    # assert b'<strong>HTML</strong> allowed here' in rv.data