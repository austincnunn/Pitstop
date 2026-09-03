import pytest
from app import db
from app.models import Trip
from datetime import date


@pytest.fixture
def sample_trip(app, test_user, sample_vehicle):
    trip = Trip(
        vehicle_id=sample_vehicle.id,
        user_id=test_user.id,
        date=date(2024, 2, 1),
        start_odometer=10000.0,
        end_odometer=10150.0,
        purpose='business',
        description='Client meeting',
    )
    db.session.add(trip)
    db.session.commit()
    return trip


class TestTripIndex:
    def test_index_requires_auth(self, client):
        resp = client.get('/trips/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_index_returns_200(self, auth_client):
        resp = auth_client.get('/trips/')
        assert resp.status_code == 200

    def test_index_shows_trips(self, auth_client, sample_trip):
        resp = auth_client.get('/trips/')
        assert resp.status_code == 200
        assert b'Client meeting' in resp.data


class TestTripNew:
    def test_new_requires_auth(self, client):
        resp = client.get('/trips/new', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_new_form_returns_200(self, auth_client, sample_vehicle):
        resp = auth_client.get('/trips/new')
        assert resp.status_code == 200

    def test_create_trip(self, auth_client, sample_vehicle, test_user):
        resp = auth_client.post('/trips/new', data={
            'vehicle_id': str(sample_vehicle.id),
            'date': '2024-03-01',
            'start_odometer': '12000',
            'end_odometer': '12200',
            'purpose': 'business',
            'description': 'Business trip',
            'start_location': 'Office',
            'end_location': 'Client',
        }, follow_redirects=True)
        assert resp.status_code == 200
        trip = Trip.query.filter_by(description='Business trip').first()
        assert trip is not None
        assert trip.start_odometer == 12000.0
        assert trip.end_odometer == 12200.0
        assert trip.user_id == test_user.id


class TestTripEdit:
    def test_edit_requires_auth(self, client, sample_trip):
        resp = client.get(f'/trips/{sample_trip.id}/edit', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_edit_form_returns_200(self, auth_client, sample_trip):
        resp = auth_client.get(f'/trips/{sample_trip.id}/edit')
        assert resp.status_code == 200

    def test_edit_trip(self, auth_client, sample_trip):
        resp = auth_client.post(f'/trips/{sample_trip.id}/edit', data={
            'date': '2024-02-01',
            'start_odometer': '10000',
            'end_odometer': '10200',
            'purpose': 'personal',
            'description': 'Updated trip',
        }, follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_trip)
        assert sample_trip.description == 'Updated trip'
        assert sample_trip.purpose == 'personal'


class TestTripDelete:
    def test_delete_requires_auth(self, client, sample_trip):
        resp = client.post(f'/trips/{sample_trip.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_delete_trip(self, auth_client, sample_trip):
        trip_id = sample_trip.id
        resp = auth_client.post(f'/trips/{trip_id}/delete', follow_redirects=True)
        assert resp.status_code == 200
        assert Trip.query.get(trip_id) is None


class TestTripReport:
    def test_report_requires_auth(self, client):
        resp = client.get('/trips/report', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_report_returns_200(self, auth_client):
        resp = auth_client.get('/trips/report')
        assert resp.status_code == 200

    def test_report_with_trips(self, auth_client, sample_trip):
        resp = auth_client.get('/trips/report')
        assert resp.status_code == 200
