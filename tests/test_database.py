import pytest
import sqlite3
from datetime import datetime
from pysrc.database.queries import EntryQueries, CategoryQueries
from pysrc.post import BlogPost, DraftPost, Travel


@pytest.fixture
def db():
    """Create a temporary test database"""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    # Create tables
    cur.executescript(
        """
        CREATE TABLE entries (
            slug TEXT,
            published DATETIME,
            location TEXT,
            PRIMARY KEY (slug, published)
        );
        
        CREATE TABLE categories (
            slug TEXT,
            published DATETIME,
            category TEXT,
            PRIMARY KEY (slug, published, category)
        );
    """
    )

    return conn


def test_insert_entry(db):
    """Test inserting a blog entry"""
    cur = db.cursor()
    test_data = ["test-slug", datetime.now(), "test/path"]

    cur.execute(EntryQueries.INSERT, test_data)
    db.commit()

    # Verify insertion
    cur.execute("SELECT * FROM entries")
    result = cur.fetchone()
    assert result[0] == "test-slug"
    assert result[2] == "test/path"


def test_popular_categories(db):
    """Test getting popular categories"""
    cur = db.cursor()
    # Insert test categories
    test_data = [
        ("slug1", datetime.now(), "python"),
        ("slug2", datetime.now(), "python"),
        ("slug3", datetime.now(), "flask"),
    ]

    for entry in test_data:
        cur.execute(CategoryQueries.INSERT_OR_REPLACE, entry)
    db.commit()

    # Test popular categories query
    cur.execute(CategoryQueries.SELECT_POPULAR)
    results = cur.fetchall()
    assert len(results) == 2
    assert results[0][0] == "python"  # Most popular category
    assert results[0][1] == 2  # Count of python entries
