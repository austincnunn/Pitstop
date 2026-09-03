import pytest
from app import db
from app.models import Vehicle, ChargingSession
from datetime import date


@pytest.fixture
def ev_vehicle(app, test_user):
    vehicle = Vehicle(
        owner_id=test_user.id,
        name='Tesla Model 3',
        vehicle_type='car',
        make='Tesla',
        model='Model 3',
        year=2023,
        fuel_type='electric',
    )
    db.session.add(vehicle)
    db.session.commit()
    return vehicle


@pytest.fixture
def sample_session(app, test_user, ev_vehicle):
    session = ChargingSession(
        vehicle_id=ev_vehicle.id,
        user_id=test_user.id,
        date=date(2024, 3, 1),
        kwh_added=40.0,
        total_cost=8.0,
        charger_type='ac_home',
    )
    db.session.add(session)
    db.session.commit()
    return session


class TestChargingIndex:
    def test_index_requires_auth(self, client):
        resp = client.get('/charging/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_index_returns_200(self, auth_client):
        resp = auth_client.get('/charging/')
        assert resp.status_code == 200

    def test_index_shows_sessions(self, auth_client, sample_session):
        resp = auth_client.get('/charging/')
        assert resp.status_code == 200


class TestChargingNew:
    def test_new_requires_auth(self, client):
        resp = client.get('/charging/new', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_new_form_returns_200(self, auth_client, ev_vehicle):
        resp = auth_client.get('/charging/new')
        assert resp.status_code == 200

    def test_redirects_if_no_ev(self, auth_client, sample_vehicle):
        # sample_vehicle is petrol, so no EV — should redirect
        resp = auth_client.get('/charging/new', follow_redirects=False)
        assert resp.status_code == 302

    def test_create_charging_session(self, auth_client, ev_vehicle, test_user):
        resp = auth_client.post('/charging/new', data={
            'vehicle_id': str(ev_vehicle.id),
            'date': '2024-04-01',
            'kwh_added': '35.0',
            'total_cost': '7.00',
            'charger_type': 'ac_home',
        }, follow_redirects=True)
        assert resp.status_code == 200
        session = ChargingSession.query.filter_by(
            vehicle_id=ev_vehicle.id,
            kwh_added=35.0
        ).first()
        assert session is not None
        assert session.user_id == test_user.id


class TestChargingEdit:
    def test_edit_requires_auth(self, client, sample_session):
        resp = client.get(f'/charging/{sample_session.id}/edit', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_edit_form_returns_200(self, auth_client, sample_session):
        resp = auth_client.get(f'/charging/{sample_session.id}/edit')
        assert resp.status_code == 200

    def test_edit_charging_session(self, auth_client, sample_session):
        resp = auth_client.post(f'/charging/{sample_session.id}/edit', data={
            'date': '2024-03-01',
            'kwh_added': '45.0',
            'total_cost': '9.00',
            'charger_type': 'dc_fast',
        }, follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_session)
        assert sample_session.kwh_added == 45.0
        assert sample_session.charger_type == 'dc_fast'


class TestChargingDelete:
    def test_delete_requires_auth(self, client, sample_session):
        resp = client.post(f'/charging/{sample_session.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_delete_charging_session(self, auth_client, sample_session):
        session_id = sample_session.id
        resp = auth_client.post(f'/charging/{session_id}/delete', follow_redirects=True)
        assert resp.status_code == 200
        assert ChargingSession.query.get(session_id) is None
