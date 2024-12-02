from typing import NamedTuple


class EntryQueries:
    INSERT = """
        INSERT INTO entries 
        (slug, published, location) 
        VALUES (?, ?, ?)
    """

    SELECT_ALL = """
        SELECT entries.location 
        FROM entries
        ORDER BY entries.published DESC
    """

    SELECT_BY_DATE = """
        SELECT entries.location 
        FROM entries
        WHERE CAST(strftime('%Y',entries.published)AS INT) = ?
        AND CAST(strftime('%m',entries.published)AS INT) = ?
        AND CAST(strftime('%d',entries.published)AS INT) = ?
        ORDER BY entries.published DESC
    """


class CategoryQueries:
    INSERT_OR_REPLACE = """
        INSERT OR REPLACE INTO categories 
        (slug, published, category) 
        VALUES (?, ?, ?)
    """

    DELETE = """
        DELETE FROM categories 
        WHERE slug = ? AND category = ?
    """

    SELECT_POPULAR = """
        SELECT category, COUNT(*) as count
        FROM categories
        WHERE category NOT IN ('None', 'image', 'album', 'bookmark', 'note')
        GROUP BY category
        ORDER BY count DESC
    """

    SELECT_BY_CATEGORY = """
        SELECT entries.location 
        FROM categories
        INNER JOIN entries ON 
            entries.slug = categories.slug AND 
            entries.published = categories.published
        WHERE categories.category = ?
        ORDER BY entries.published DESC
    """
