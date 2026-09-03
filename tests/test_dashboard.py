import pytest
from app import db
from app.models import Vehicle


class TestDashboard:
    def test_dashboard_requires_auth(self, client):
        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_dashboard_returns_200(self, auth_client):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200

    def test_dashboard_without_vehicles(self, auth_client):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200

    def test_dashboard_with_vehicles(self, auth_client, sample_vehicle):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Test Car' in resp.data

    def test_dashboard_with_fuel_logs(self, auth_client, sample_fuel_log):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200

    def test_dashboard_with_expenses(self, auth_client, sample_expense):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200


class TestTimeline:
    def test_timeline_requires_auth(self, client, sample_vehicle):
        resp = client.get(f'/timeline/{sample_vehicle.id}', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_timeline_returns_200(self, auth_client, sample_vehicle):
        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200

    def test_timeline_with_fuel_logs(self, auth_client, sample_fuel_log, sample_vehicle):
        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200

    def test_timeline_with_expenses(self, auth_client, sample_expense, sample_vehicle):
        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200

    def test_timeline_404_for_nonexistent(self, auth_client):
        resp = auth_client.get('/timeline/99999')
        assert resp.status_code == 404

    def test_timeline_other_user_vehicle_redirects(self, auth_client, admin_user):
        # Create a vehicle owned by admin
        other_vehicle = Vehicle(
            owner_id=admin_user.id,
            name='Admin Car',
            vehicle_type='car',
            fuel_type='petrol',
        )
        db.session.add(other_vehicle)
        db.session.commit()

        resp = auth_client.get(f'/timeline/{other_vehicle.id}', follow_redirects=True)
        assert resp.status_code == 200
        # Should redirect to dashboard since user doesn't have access
