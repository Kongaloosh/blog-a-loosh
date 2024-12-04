import pytest
from datetime import datetime
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
from kongaloosh import handle_event_data, Event, app


@pytest.fixture
def make_request():
    """Helper fixture to create test requests"""

    def _make_request(form_data):
        builder = EnvironBuilder(method="POST", data=form_data)
        env = builder.get_environ()
        return Request(env)

    return _make_request


def test_valid_event_data(make_request):
    """Test processing valid event data"""
    with app.test_request_context():
        request = make_request(
            {
                "dt_start": "2024-03-01",
                "dt_end": "2024-03-02",
                "event_name": "Test Event",
            }
        )

        result = handle_event_data(request)

        assert isinstance(result, Event)
        assert result.event_name == "Test Event"
        assert result.dt_start == datetime.strptime("2024-03-01", "%Y-%m-%d").date()
        assert result.dt_end == datetime.strptime("2024-03-02", "%Y-%m-%d").date()


def test_missing_fields(make_request):
    """Test handling of missing fields"""
    with app.test_request_context():
        request = make_request(
            {
                "dt_start": "2024-03-01",
                # missing dt_end and event_name
            }
        )

        result = handle_event_data(request)

        assert isinstance(result, Event)
        assert result.event_name is None
        assert result.dt_start is None
        assert result.dt_end is None


def test_empty_event_data(make_request):
    """Test handling of empty event data"""
    with app.test_request_context():
        request = make_request({})

        result = handle_event_data(request)

        assert isinstance(result, Event)
        assert result.event_name is None
        assert result.dt_start is None
        assert result.dt_end is None


def test_invalid_date_format(make_request):
    """Test handling of invalid date formats"""
    with app.test_request_context():
        request = make_request(
            {
                "dt_start": "not-a-date",
                "dt_end": "2024-03-02",
                "event_name": "Test Event",
            }
        )

        result = handle_event_data(request)

        assert isinstance(result, Event)
        assert result.event_name is None
        assert result.dt_start is None
        assert result.dt_end is None


def test_partial_event_data(make_request):
    """Test handling of partial event data"""
    with app.test_request_context():
        request = make_request(
            {
                "dt_start": "2024-03-01",
                "event_name": "Test Event",
                # missing dt_end
            }
        )

        result = handle_event_data(request)

        assert isinstance(result, Event)
        assert result.event_name is None
        assert result.dt_start is None
        assert result.dt_end is None


def test_whitespace_handling(make_request):
    """Test handling of whitespace in event data"""
    with app.test_request_context():
        request = make_request(
            {
                "dt_start": "  2024-03-01  ",
                "dt_end": "  2024-03-02  ",
                "event_name": "  Test Event  ",
            }
        )

        result = handle_event_data(request)

        assert isinstance(result, Event)
        assert result.event_name == "Test Event"
        assert result.dt_start == datetime.strptime("2024-03-01", "%Y-%m-%d")
        assert result.dt_end == datetime.strptime("2024-03-02", "%Y-%m-%d")
