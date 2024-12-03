import pytest
from datetime import datetime
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
from unittest.mock import patch, Mock
from kongaloosh import (
    handle_travel_data,
    Travel,
    TravelValidationError,
    app,
    GOOGLE_MAPS_KEY,
)


@pytest.fixture
def make_request():
    """Helper fixture to create test requests"""

    def _make_request(form_data):
        builder = EnvironBuilder(method="POST", data=form_data)
        env = builder.get_environ()
        return Request(env)

    return _make_request


def test_valid_single_location(make_request):
    """Test processing a single valid location"""
    with app.test_request_context():
        request = make_request(
            {
                "geo[]": ["geo:45.5231,-122.6765"],
                "location[]": ["Portland, OR"],
                "date[]": ["2024-03-01"],
            }
        )

        with patch("requests.get") as mock_get:
            mock_get.return_value.content = b"fake_map_data"
            result = handle_travel_data(request)

        assert isinstance(result, Travel)
        assert len(result.trips) == 1
        assert result.trips[0].location == "geo:45.5231,-122.6765"
        assert result.trips[0].location_name == "Portland, OR"
        assert result.trips[0].date == datetime(2024, 3, 1)
        assert result.map_data == b"fake_map_data"
        assert GOOGLE_MAPS_KEY in result.map_url
        assert "45.5231,-122.6765" in result.map_url


def test_multiple_locations(make_request):
    """Test processing multiple locations"""
    with app.test_request_context():
        request = make_request(
            {
                "geo[]": ["geo:45.5231,-122.6765", "geo:47.6062,-122.3321"],
                "location[]": ["Portland, OR", "Seattle, WA"],
                "date[]": ["2024-03-01", "2024-03-02"],
            }
        )

        with patch("requests.get") as mock_get:
            mock_get.return_value.content = b"fake_map_data"
            result = handle_travel_data(request)

        assert len(result.trips) == 2
        assert result.trips[0].location_name == "Portland, OR"
        assert result.trips[1].location_name == "Seattle, WA"
        assert "45.5231,-122.6765" in result.map_url
        assert "47.6062,-122.3321" in result.map_url


def test_missing_dates(make_request):
    """Test validation of missing dates"""
    with app.test_request_context():
        request = make_request(
            {
                "geo[]": ["geo:45.5231,-122.6765", "geo:47.6062,-122.3321"],
                "location[]": ["Portland, OR", "Seattle, WA"],
                "date[]": ["2024-03-01", ""],  # Missing date
            }
        )

        with pytest.raises(TravelValidationError) as exc_info:
            handle_travel_data(request)
        assert "Missing required dates" in str(exc_info.value)


def test_empty_travel_data(make_request):
    """Test handling of empty travel data"""
    with app.test_request_context():
        request = make_request({"geo[]": [], "location[]": [], "date[]": []})

        result = handle_travel_data(request)
        assert isinstance(result, Travel)
        assert len(result.trips) == 0
        assert result.map_url is None
        assert result.map_data is None


def test_mismatched_data_lengths(make_request):
    """Test handling of mismatched data lengths"""
    with app.test_request_context():
        request = make_request(
            {
                "geo[]": ["geo:45.5231,-122.6765"],
                "location[]": ["Portland, OR"],
                "date[]": ["2024-03-01", "2024-03-02"],  # Extra date
            }
        )

        result = handle_travel_data(request)
        assert isinstance(result, Travel)
        assert len(result.trips) == 0


def test_invalid_date_format(make_request):
    """Test handling of invalid date format"""
    with app.test_request_context():
        request = make_request(
            {
                "geo[]": ["geo:45.5231,-122.6765"],
                "location[]": ["Portland, OR"],
                "date[]": ["not-a-date"],
            }
        )

        with pytest.raises(ValueError):
            handle_travel_data(request)


def test_map_url_generation(make_request):
    """Test proper generation of Google Maps static URL"""
    with app.test_request_context():
        request = make_request(
            {
                "geo[]": ["geo:45.5231,-122.6765"],
                "location[]": ["Portland, OR"],
                "date[]": ["2024-03-01"],
            }
        )

        with patch("requests.get") as mock_get:
            mock_get.return_value.content = b"fake_map_data"
            result = handle_travel_data(request)

        expected_coords = "45.5231,-122.6765"
        assert "markers=color:green|" + expected_coords in result.map_url
        assert "path=color:green|weight:5|" + expected_coords in result.map_url
        assert "size=500x500" in result.map_url
        assert "maptype=roadmap" in result.map_url
