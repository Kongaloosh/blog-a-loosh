import pytest
from unittest.mock import patch
from kongaloosh import resolve_placename, PlaceInfo
import requests


@pytest.fixture
def mock_geonames_response():
    """Mock successful GeoNames API response"""
    return {
        "geonames": [
            {
                "name": "San Francisco",
                "geonameId": 5391959,
                "adminName2": "San Francisco County",
                "adminName1": "California",
                "countryName": "United States",
            }
        ]
    }


def test_resolve_placename_success(mock_geonames_response):
    """Test successful location resolution"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_geonames_response

        result = resolve_placename("geo:37.7749,-122.4194")

        # Verify API call
        mock_get.assert_called_once()
        assert "lat=37.7749" in mock_get.call_args[0][0]
        assert "lng=-122.4194" in mock_get.call_args[0][0]

        # Verify result
        assert isinstance(result, PlaceInfo)
        assert result.name == "San Francisco"
        assert result.geoname_id == 5391959
        assert result.admin_name == "San Francisco County"
        assert result.country_name == "United States"


def test_resolve_placename_no_admin2():
    """Test when adminName2 is missing but adminName1 exists"""
    mock_response = {
        "geonames": [
            {
                "name": "Paris",
                "geonameId": 2988507,
                "adminName1": "Île-de-France",
                "countryName": "France",
            }
        ]
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        result = resolve_placename("geo:48.8566,2.3522")
        assert result.admin_name == "Île-de-France"


def test_resolve_placename_invalid_format():
    """Test with invalid location format"""
    # Test invalid prefix
    with pytest.raises(ValueError) as exc_info:
        resolve_placename("invalid:format")
    assert "must start with 'geo:'" in str(exc_info.value)

    # Test invalid coordinate format
    with pytest.raises(ValueError) as exc_info:
        resolve_placename("geo:invalid")
    assert "must be 'geo:lat,long'" in str(exc_info.value)


def test_resolve_placename_malformed_coordinates():
    """Test with malformed coordinates"""
    with pytest.raises(ValueError) as exc_info:
        resolve_placename("geo:123")
    assert "must be 'geo:lat,long'" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        resolve_placename("geo:123,456,789")
    assert "must be 'geo:lat,long'" in str(exc_info.value)


def test_resolve_placename_empty_response():
    """Test when GeoNames returns no results"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"geonames": []}
        with pytest.raises(ValueError) as exc_info:
            resolve_placename("geo:0,0")
        assert "No geonames api key found" in str(exc_info.value)


def test_resolve_placename_api_error():
    """Test when GeoNames API request fails"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException("API Error")
        with pytest.raises(ValueError) as exc_info:
            resolve_placename("geo:37.7749,-122.4194")
        assert "Error resolving placename" in str(exc_info.value)


def test_resolve_placename_with_semicolon():
    """Test location string with additional parameters after semicolon"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "geonames": [
                {
                    "name": "Tokyo",
                    "geonameId": 1850147,
                    "adminName1": "Tokyo",
                    "countryName": "Japan",
                }
            ]
        }

        result = resolve_placename("geo:35.6762,139.6503;u=10")
        mock_get.assert_called_once()
        assert "lat=35.6762" in mock_get.call_args[0][0]
        assert "lng=139.6503" in mock_get.call_args[0][0]
        assert result.name == "Tokyo"
