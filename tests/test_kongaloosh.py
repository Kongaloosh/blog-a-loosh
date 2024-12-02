import unittest
from unittest.mock import patch, MagicMock
import kongaloosh
from pysrc import post

# Create a minimal mock configuration
mock_config = MagicMock()
mock_config.get.side_effect = lambda section, key: {
    ("PhotoLocations", "BulkUploadLocation"): "/test/bulk/upload",
    ("PhotoLocations", "BlogStorage"): "/test/blog/storage",
    ("PhotoLocations", "PermStorage"): "/test/perm/storage",
    ("Global", "Database"): "test_database.db",
    ("Global", "Debug"): "True",
    ("Global", "DomainName"): "test.com",
    ("Global", "DevKey"): "test_key",
    ("SiteAuthentication", "Username"): "test_user",
    ("SiteAuthentication", "Password"): "test_pass",
    ("GeoNamesUsername", "Username"): "test_geo",
    ("PersonalInfo", "FullName"): "Test User",
    ("GoogleMaps", "key"): "test_google_key",
    ("PhotoLocations", "URLPhotos"): "/test/url/photos",
}.get((section, key))

# Apply the mocks
patch("configparser.ConfigParser", return_value=mock_config).start()
patch("pysrc.file_management.markdown_album_pre_process.config", mock_config).start()
patch("pysrc.file_management.file_parser.config", mock_config).start()


# Create a mock ConfigParser
mock_configparser = MagicMock()
mock_configparser.ConfigParser.return_value = mock_config

# Apply the mocks
patch("configparser.ConfigParser", mock_configparser.ConfigParser).start()
patch("pysrc.file_management.markdown_album_pre_process.config", mock_config).start()
patch("pysrc.file_management.file_parser.config", mock_config).start()

# Now import the modules
from kongaloosh import app, connect_db
from pysrc.file_management import markdown_album_pre_process, file_parser
from flask_testing import TestCase


class KongalooshTestCase(TestCase):

    def create_app(self):
        app.config["TESTING"] = True
        app.config["DATABASE"] = "test_database.db"
        app.config["SECRET_KEY"] = "test_secret_key"
        return app

    def test_config_values(self):
        self.assertEqual(
            markdown_album_pre_process.ORIGINAL_PHOTOS_DIR, "/test/bulk/upload"
        )
        self.assertEqual(markdown_album_pre_process.BLOG_STORAGE, "/test/blog/storage")
        self.assertEqual(
            markdown_album_pre_process.PERMANENT_PHOTOS_DIR, "/test/perm/storage"
        )
        self.assertEqual(file_parser.DATABASE, "test_database.db")

    @patch("kongaloosh.g")
    @patch("kongaloosh.file_parser_json")
    @patch("os.path.exists")
    def test_get_entries_by_date_empty(self, mock_exists, mock_file_parser, mock_g):
        # Setup
        mock_g.db.execute.return_value.fetchall.return_value = []

        # Execute
        result = kongaloosh.get_entries_by_date()

        # Assert
        self.assertEqual(result, [])
        mock_g.db.execute.assert_called_once_with(
            """SELECT entries.location FROM entries
            ORDER BY entries.published DESC
            """
        )

    @patch("kongaloosh.g")
    @patch("kongaloosh.file_parser_json")
    @patch("os.path.exists")
    def test_get_entries_by_date_with_entries(
        self, mock_exists, mock_file_parser, mock_g
    ):
        # Setup
        mock_g.db.execute.return_value.fetchall.return_value = [
            ("entry1",),
            ("entry2",),
            ("entry3",),
        ]
        mock_exists.return_value = True
        mock_file_parser.side_effect = [
            post.BlogPost(
                title="Entry 1", content="", slug="", u_uid="", url="", published=""
            ),
            post.BlogPost(
                title="Entry 2", content="", slug="", u_uid="", url="", published=""
            ),
            post.BlogPost(
                title="Entry 3", content="", slug="", u_uid="", url="", published=""
            ),
        ]

        # Execute
        result = kongaloosh.get_entries_by_date()

        # Assert
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], post.BlogPost)
        self.assertEqual(result[0].title, "Entry 1")
        self.assertEqual(result[1].title, "Entry 2")
        self.assertEqual(result[2].title, "Entry 3")
        mock_g.db.execute.assert_called_once_with(
            """SELECT entries.location FROM entries
            ORDER BY entries.published DESC
            """
        )
        self.assertEqual(mock_exists.call_count, 3)
        self.assertEqual(mock_file_parser.call_count, 3)

    @patch("kongaloosh.g")
    @patch("kongaloosh.file_parser_json")
    @patch("os.path.exists")
    def test_get_entries_by_date_with_missing_files(
        self, mock_exists, mock_file_parser, mock_g
    ):
        # Setup
        mock_g.db.execute.return_value.fetchall.return_value = [
            ("entry1",),
            ("entry2",),
            ("entry3",),
        ]
        mock_exists.side_effect = [True, False, True]
        mock_file_parser.side_effect = [
            post.BlogPost(
                title="Entry 1", content="", slug="", u_uid="", url="", published=""
            ),
            post.BlogPost(
                title="Entry 3", content="", slug="", u_uid="", url="", published=""
            ),
        ]

        # Execute
        result = kongaloosh.get_entries_by_date()

        # Assert
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], post.BlogPost)
        self.assertEqual(result[0].title, "Entry 1")
        self.assertEqual(result[1].title, "Entry 3")
        mock_g.db.execute.assert_called_once_with(
            """SELECT entries.location FROM entries
            ORDER BY entries.published DESC
            """
        )
        self.assertEqual(mock_exists.call_count, 3)
        self.assertEqual(mock_file_parser.call_count, 2)


if __name__ == "__main__":
    unittest.main()
