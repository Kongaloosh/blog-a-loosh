from io import BytesIO
import os
import tempfile

import pytest
import kongaloosh
import datetime


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
    # test that we can successfully remove a post
    dt = datetime.datetime.today()
    rv = client.get(
        '/delete_entry/e/{year}/{month}/{day}/oh-hey'.format(
            year=dt.year,
            month=dt.month,
            day=dt.day),
        follow_redirects=True
    )

    # test that we cannot add a post if not logged in
    rv = client.post('/add', data=dict(
        title='<Hello>',
        text='<strong>HTML</strong> allowed here'
    ), follow_redirects=True)
    assert 401 == rv.status_code
    assert b'Unauthorized' in rv.data

    # test that we can add a post if logged imn
    login(client, kongaloosh.app.config['USERNAME'], kongaloosh.app.config['PASSWORD'])
    dt = datetime.datetime.today()
    rv = client.get(
        '/delete_entry/e/{year}/{month}/{day}/oh-hey'.format(
            year=dt.year,
            month=dt.month,
            day=dt.day),
        follow_redirects=True
    )
    rv = client.post(
        '/add',
        data={
            "Summary": "summary",
            'Submit': "Submit",
            "h": "",
            "summary":"",
            "published":"",
            "updated":"",
            "category":"",
            "slug":"",
            "location":"",
            "location_name":"",
            "location_id":"",
            "in_reply_to":"",
            "repost_of":"",
            "syndication":"",
            "photo":"",
            "title":'Oh hey',
            "content":'blah blah blah',
            "submit":"Submit",
        },
        content_type="multipart/form-data",
        follow_redirects=True
    )

    assert 'blah blah blah' in rv.data
    assert 200 == rv.status_code

    # test that we cannot add the same post twice
    rv = client.post(
        '/add',
        data={
            "Summary": "summary",
            'Submit': "Submit",
            "h": "",
            "summary":"",
            "published":"",
            "updated":"",
            "category":"",
            "slug":"",
            "location":"",
            "location_name":"",
            "location_id":"",
            "in_reply_to":"",
            "repost_of":"",
            "syndication":"",
            "photo":"",
            "title":'Hello',
            "content":'allowed here',
            "submit":"Submit",
        },
        content_type="multipart/form-data",
        follow_redirects=True
    )
    assert "already exists" in rv.data

    # test that we can successfully remove a post
    dt = datetime.datetime.today()
    rv = client.get(
        '/delete_entry/e/{year}/{month}/{day}/oh-hey'.format(
            year=dt.year,
            month=dt.month,
            day=dt.day),
        follow_redirects=True
    )

    assert 'blah blah blah' not in rv.data
    assert 200 == rv.status_code


def test_img_post(client):

    # test that we can add a post with one picture if logged in
    login(client, kongaloosh.app.config['USERNAME'], kongaloosh.app.config['PASSWORD'])

    dt = datetime.datetime.today()
    rv = client.get(
        '/delete_entry/e/{year}/{month}/{day}/oh-hey'.format(
            year=dt.year,
            month=dt.month,
            day=dt.day),
        follow_redirects=True
    )

    rv = client.post(
        '/add',
        data={
            "Summary": "summary",
            'Submit': "Submit",
            "h": "",
            "summary": "",
            "published": "",
            "updated": "",
            "category": "",
            "slug": "",
            "location": "",
            "location_name": "",
            "location_id": "",
            "in_reply_to": "",
            "repost_of": "",
            "syndication": "",
            "photo_file[]": [(BytesIO(open("test/test_img.jpeg", "rb").read()), "test")],
            "title": 'Oh hey',
            "content": 'blah blah blah',
            "submit": "Submit",
        },
        content_type="multipart/form-data",
        follow_redirects=True
    )

    assert 'blah blah blah' in rv.data
    assert 200 == rv.status_code

    # Check that a delete request also deletes associated images
    dt = datetime.datetime.today()
    rv = client.get(
        '/delete_entry/e/{year}/{month}/{day}/oh-hey'.format(
            year=dt.year,
            month=dt.month,
            day=dt.day),
        follow_redirects=True
    )

    rv = client.post(
        '/add',
        data={
            "Summary": "summary",
            'Submit': "Submit",
            "h": "",
            "summary": "",
            "published": "",
            "updated": "",
            "category": "",
            "slug": "",
            "location": "",
            "location_name": "",
            "location_id": "",
            "in_reply_to": "",
            "repost_of": "",
            "syndication": "",
            "photo_file[]": [
                (BytesIO(open("test/test_img.jpeg", "rb").read()), "test"),
                (BytesIO(open("test/test_img_2.jpg", "rb").read()), "test_2")
            ],
            "title": 'Oh hey',
            "content": 'blah blah blah',
            "submit": "Submit",
        },
        content_type="multipart/form-data",
        follow_redirects=True
    )

    rv = client.get(
        '/delete_entry/e/{year}/{month}/{day}/oh-hey'.format(
            year=dt.year,
            month=dt.month,
            day=dt.day),
        follow_redirects=True
    )