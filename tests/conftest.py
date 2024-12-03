import pytest
import sqlite3
from unittest.mock import patch
from flask import g
from kongaloosh import app as flask_app, init_db


@pytest.fixture
def app():
    """Create a test Flask app"""
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SECRET_KEY"] = "test_key"

    return flask_app


@pytest.fixture
def db():
    """Create an in-memory test database"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create schema
    with flask_app.open_resource("schema.sql", mode="r") as f:
        conn.executescript(f.read())

    return conn


@pytest.fixture
def client(app, db):
    """Create a test client with mocked db"""
    with patch("kongaloosh.connect_db", return_value=db):
        with app.test_client() as client:
            with app.app_context():
                g.db = db
                yield client


@pytest.fixture
def runner(app):
    """Create a test CLI runner"""
    return app.test_cli_runner()
