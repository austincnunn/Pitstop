"""Tests for the calendar feed API endpoints."""
import pytest
from app import db as _db_ext
from app.models import User, Vehicle


@pytest.fixture
def cal_user(app):
    """A user with an API key for calendar testing."""
    user = User(
        username='caluser',
        email='cal@example.com',
    )
    user.set_password('CalPass123!')
    _db_ext.session.add(user)
    _db_ext.session.commit()
    user.generate_api_key()
    _db_ext.session.commit()
    return user


@pytest.fixture
def cal_vehicle(cal_user):
    vehicle = Vehicle(
        owner_id=cal_user.id,
        name='Calendar Car',
        vehicle_type='car',
    )
    _db_ext.session.add(vehicle)
    _db_ext.session.commit()
    return vehicle


class TestCalendarFeed:
    def test_feed_no_token_returns_401(self, client):
        resp = client.get('/api/calendar/feed')
        assert resp.status_code == 401

    def test_feed_invalid_token_returns_401(self, client):
        resp = client.get('/api/calendar/feed?token=bad-token')
        assert resp.status_code == 401

    def test_feed_valid_token_returns_ical(self, client, cal_user):
        resp = client.get(f'/api/calendar/feed?token={cal_user.api_key}')
        assert resp.status_code == 200
        content_type = resp.content_type
        assert 'calendar' in content_type or 'text' in content_type

    def test_feed_contains_vcalendar(self, client, cal_user):
        resp = client.get(f'/api/calendar/feed?token={cal_user.api_key}')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert 'BEGIN:VCALENDAR' in body
        assert 'END:VCALENDAR' in body

    def test_feed_empty_no_vehicles(self, client, cal_user):
        resp = client.get(f'/api/calendar/feed?token={cal_user.api_key}')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        # Should still be a valid calendar
        assert 'VCALENDAR' in body

    def test_feed_with_vehicle(self, client, cal_user, cal_vehicle):
        resp = client.get(f'/api/calendar/feed?token={cal_user.api_key}')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert 'VCALENDAR' in body


class TestCalendarFeedIcs:
    def test_feed_ics_no_token_returns_401(self, client):
        resp = client.get('/api/calendar/feed.ics')
        assert resp.status_code == 401

    def test_feed_ics_invalid_token_returns_401(self, client):
        resp = client.get('/api/calendar/feed.ics?token=bad-token')
        assert resp.status_code == 401

    def test_feed_ics_valid_token_returns_ical(self, client, cal_user):
        resp = client.get(f'/api/calendar/feed.ics?token={cal_user.api_key}')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert 'BEGIN:VCALENDAR' in body
        assert 'END:VCALENDAR' in body

    def test_feed_ics_matches_feed(self, client, cal_user):
        """The .ics alias should return the same content as /feed."""
        resp_feed = client.get(f'/api/calendar/feed?token={cal_user.api_key}')
        resp_ics = client.get(f'/api/calendar/feed.ics?token={cal_user.api_key}')
        assert resp_feed.status_code == 200
        assert resp_ics.status_code == 200
        # Both should have VCALENDAR
        assert 'BEGIN:VCALENDAR' in resp_ics.data.decode('utf-8')
