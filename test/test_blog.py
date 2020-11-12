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


#
# def test_empty_db(client):
#     """Start with a blank database."""
#
#     rv = client.get('/')
#     assert b'No entries here so far' in rv.data