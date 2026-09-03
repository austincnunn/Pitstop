"""Tests for the public REST API v1 (API key authenticated)."""
import pytest
from datetime import date
from app import db as _db_ext
from app.models import User, Vehicle, FuelLog, Expense


class TestApiKeyAuth:
    def test_no_api_key_returns_401(self, client):
        resp = client.get('/api/v1/vehicles')
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['code'] == 'missing_api_key'

    def test_invalid_api_key_returns_401(self, client):
        resp = client.get('/api/v1/vehicles', headers={'X-API-Key': 'invalid-key'})
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['code'] == 'invalid_api_key'

    def test_bearer_token_auth(self, client, api_headers, test_user):
        """API key also works as Bearer token."""
        api_key = api_headers['X-API-Key']
        resp = client.get(
            '/api/v1/vehicles',
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert resp.status_code == 200


class TestV1Vehicles:
    def test_list_vehicles_empty(self, client, api_headers):
        resp = client.get('/api/v1/vehicles', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'vehicles' in data
        assert 'count' in data
        assert data['count'] == 0

    def test_list_vehicles_with_vehicle(self, client, api_headers, sample_vehicle):
        resp = client.get('/api/v1/vehicles', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['count'] == 1
        assert data['vehicles'][0]['name'] == 'Test Car'

    def test_get_vehicle(self, client, api_headers, sample_vehicle):
        resp = client.get(f'/api/v1/vehicles/{sample_vehicle.id}', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['id'] == sample_vehicle.id
        assert data['name'] == 'Test Car'

    def test_get_vehicle_not_found(self, client, api_headers):
        resp = client.get('/api/v1/vehicles/99999', headers=api_headers)
        assert resp.status_code == 404

    def test_get_vehicle_other_user(self, client, api_headers, admin_user, app):
        """Cannot access another user's vehicle."""
        other_vehicle = Vehicle(
            owner_id=admin_user.id,
            name='Admin Car',
            vehicle_type='car',
        )
        _db_ext.session.add(other_vehicle)
        _db_ext.session.commit()
        resp = client.get(f'/api/v1/vehicles/{other_vehicle.id}', headers=api_headers)
        assert resp.status_code == 404

    def test_create_vehicle(self, client, api_headers):
        resp = client.post(
            '/api/v1/vehicles',
            json={'name': 'New Car', 'vehicle_type': 'car'},
            headers=api_headers
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'New Car'
        assert data['vehicle_type'] == 'car'
        assert 'id' in data

    def test_create_vehicle_missing_name(self, client, api_headers):
        resp = client.post(
            '/api/v1/vehicles',
            json={'vehicle_type': 'car'},
            headers=api_headers
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['code'] == 'validation_error'

    def test_create_vehicle_missing_type(self, client, api_headers):
        resp = client.post(
            '/api/v1/vehicles',
            json={'name': 'No Type'},
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_create_vehicle_invalid_type(self, client, api_headers):
        resp = client.post(
            '/api/v1/vehicles',
            json={'name': 'Bad', 'vehicle_type': 'spaceship'},
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_create_vehicle_no_body(self, client, api_headers):
        # Flask returns 415 when no Content-Type is set, 400 when JSON body is empty/invalid
        resp = client.post('/api/v1/vehicles', headers=api_headers)
        assert resp.status_code in (400, 415)

    def test_update_vehicle(self, client, api_headers, sample_vehicle):
        resp = client.put(
            f'/api/v1/vehicles/{sample_vehicle.id}',
            json={'name': 'Updated Car'},
            headers=api_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == 'Updated Car'

    def test_update_vehicle_no_body(self, client, api_headers, sample_vehicle):
        resp = client.put(
            f'/api/v1/vehicles/{sample_vehicle.id}',
            headers=api_headers
        )
        assert resp.status_code in (400, 415)

    def test_update_vehicle_not_owner(self, client, api_headers, admin_user, app):
        """Non-owner cannot update a vehicle they can access (shared)."""
        other_vehicle = Vehicle(
            owner_id=admin_user.id,
            name='Admin Car',
            vehicle_type='car',
        )
        _db_ext.session.add(other_vehicle)
        _db_ext.session.commit()
        # 404 because it's not in user's vehicles list
        resp = client.put(
            f'/api/v1/vehicles/{other_vehicle.id}',
            json={'name': 'Hacked'},
            headers=api_headers
        )
        assert resp.status_code in (403, 404)

    def test_delete_vehicle(self, client, api_headers, test_user):
        vehicle = Vehicle(
            owner_id=test_user.id,
            name='To Delete',
            vehicle_type='van',
        )
        _db_ext.session.add(vehicle)
        _db_ext.session.commit()
        vid = vehicle.id
        resp = client.delete(f'/api/v1/vehicles/{vid}', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_delete_vehicle_not_found(self, client, api_headers):
        resp = client.delete('/api/v1/vehicles/99999', headers=api_headers)
        assert resp.status_code == 404


class TestV1FuelLogs:
    def test_list_fuel_logs_empty(self, client, api_headers, sample_vehicle):
        resp = client.get(f'/api/v1/vehicles/{sample_vehicle.id}/fuel', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'fuel_logs' in data
        assert 'total' in data
        assert data['total'] == 0

    def test_list_fuel_logs_with_entry(self, client, api_headers, sample_vehicle, sample_fuel_log):
        resp = client.get(f'/api/v1/vehicles/{sample_vehicle.id}/fuel', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] == 1
        assert data['fuel_logs'][0]['odometer'] == 10000.0

    def test_list_fuel_logs_vehicle_not_found(self, client, api_headers):
        resp = client.get('/api/v1/vehicles/99999/fuel', headers=api_headers)
        assert resp.status_code == 404

    def test_create_fuel_log(self, client, api_headers, sample_vehicle):
        resp = client.post(
            f'/api/v1/vehicles/{sample_vehicle.id}/fuel',
            json={
                'date': '2024-02-01',
                'odometer': 11000,
                'volume': 45.0,
                'price_per_unit': 1.55,
                'total_cost': 69.75,
            },
            headers=api_headers
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['odometer'] == 11000.0
        assert 'id' in data

    def test_create_fuel_log_missing_date(self, client, api_headers, sample_vehicle):
        resp = client.post(
            f'/api/v1/vehicles/{sample_vehicle.id}/fuel',
            json={'odometer': 11000},
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_create_fuel_log_missing_odometer(self, client, api_headers, sample_vehicle):
        resp = client.post(
            f'/api/v1/vehicles/{sample_vehicle.id}/fuel',
            json={'date': '2024-02-01'},
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_create_fuel_log_invalid_date(self, client, api_headers, sample_vehicle):
        resp = client.post(
            f'/api/v1/vehicles/{sample_vehicle.id}/fuel',
            json={'date': 'not-a-date', 'odometer': 11000},
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_get_fuel_log(self, client, api_headers, sample_fuel_log):
        resp = client.get(f'/api/v1/fuel/{sample_fuel_log.id}', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['id'] == sample_fuel_log.id

    def test_get_fuel_log_not_found(self, client, api_headers):
        resp = client.get('/api/v1/fuel/99999', headers=api_headers)
        assert resp.status_code == 404

    def test_update_fuel_log(self, client, api_headers, sample_fuel_log):
        resp = client.put(
            f'/api/v1/fuel/{sample_fuel_log.id}',
            json={'odometer': 10500},
            headers=api_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['odometer'] == 10500.0

    def test_update_fuel_log_invalid_date(self, client, api_headers, sample_fuel_log):
        resp = client.put(
            f'/api/v1/fuel/{sample_fuel_log.id}',
            json={'date': 'bad-date'},
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_update_fuel_log_no_body(self, client, api_headers, sample_fuel_log):
        resp = client.put(
            f'/api/v1/fuel/{sample_fuel_log.id}',
            headers=api_headers
        )
        assert resp.status_code in (400, 415)

    def test_delete_fuel_log(self, client, api_headers, sample_vehicle, test_user):
        log = FuelLog(
            vehicle_id=sample_vehicle.id,
            user_id=test_user.id,
            date=date(2024, 3, 1),
            odometer=12000.0,
            volume=40.0,
            price_per_unit=1.50,
            total_cost=60.0,
        )
        _db_ext.session.add(log)
        _db_ext.session.commit()
        resp = client.delete(f'/api/v1/fuel/{log.id}', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_delete_fuel_log_not_found(self, client, api_headers):
        resp = client.delete('/api/v1/fuel/99999', headers=api_headers)
        assert resp.status_code == 404


class TestV1Expenses:
    def test_list_expenses_empty(self, client, api_headers, sample_vehicle):
        resp = client.get(f'/api/v1/vehicles/{sample_vehicle.id}/expenses', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'expenses' in data
        assert data['total'] == 0

    def test_list_expenses_with_entry(self, client, api_headers, sample_vehicle, sample_expense):
        resp = client.get(f'/api/v1/vehicles/{sample_vehicle.id}/expenses', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] == 1

    def test_list_expenses_vehicle_not_found(self, client, api_headers):
        resp = client.get('/api/v1/vehicles/99999/expenses', headers=api_headers)
        assert resp.status_code == 404

    def test_create_expense(self, client, api_headers, sample_vehicle):
        resp = client.post(
            f'/api/v1/vehicles/{sample_vehicle.id}/expenses',
            json={
                'date': '2024-03-01',
                'category': 'maintenance',
                'description': 'Tyre change',
                'cost': 120.0,
            },
            headers=api_headers
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['description'] == 'Tyre change'
        assert 'id' in data

    def test_create_expense_missing_required(self, client, api_headers, sample_vehicle):
        resp = client.post(
            f'/api/v1/vehicles/{sample_vehicle.id}/expenses',
            json={'date': '2024-03-01', 'category': 'maintenance'},
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_create_expense_invalid_category(self, client, api_headers, sample_vehicle):
        resp = client.post(
            f'/api/v1/vehicles/{sample_vehicle.id}/expenses',
            json={
                'date': '2024-03-01',
                'category': 'unicorn',
                'description': 'Test',
                'cost': 10.0,
            },
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_create_expense_invalid_date(self, client, api_headers, sample_vehicle):
        resp = client.post(
            f'/api/v1/vehicles/{sample_vehicle.id}/expenses',
            json={
                'date': 'not-a-date',
                'category': 'maintenance',
                'description': 'Test',
                'cost': 10.0,
            },
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_get_expense(self, client, api_headers, sample_expense):
        resp = client.get(f'/api/v1/expenses/{sample_expense.id}', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['id'] == sample_expense.id

    def test_get_expense_not_found(self, client, api_headers):
        resp = client.get('/api/v1/expenses/99999', headers=api_headers)
        assert resp.status_code == 404

    def test_update_expense(self, client, api_headers, sample_expense):
        resp = client.put(
            f'/api/v1/expenses/{sample_expense.id}',
            json={'cost': 100.0},
            headers=api_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['cost'] == 100.0

    def test_update_expense_invalid_category(self, client, api_headers, sample_expense):
        resp = client.put(
            f'/api/v1/expenses/{sample_expense.id}',
            json={'category': 'invalid'},
            headers=api_headers
        )
        assert resp.status_code == 400

    def test_update_expense_no_body(self, client, api_headers, sample_expense):
        resp = client.put(
            f'/api/v1/expenses/{sample_expense.id}',
            headers=api_headers
        )
        assert resp.status_code in (400, 415)

    def test_delete_expense(self, client, api_headers, sample_vehicle, test_user):
        expense = Expense(
            vehicle_id=sample_vehicle.id,
            user_id=test_user.id,
            date=date(2024, 4, 1),
            category='cleaning',
            description='Car wash',
            cost=15.0,
        )
        _db_ext.session.add(expense)
        _db_ext.session.commit()
        resp = client.delete(f'/api/v1/expenses/{expense.id}', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_delete_expense_not_found(self, client, api_headers):
        resp = client.delete('/api/v1/expenses/99999', headers=api_headers)
        assert resp.status_code == 404


class TestV1Categories:
    def test_list_categories(self, client, api_headers):
        resp = client.get('/api/v1/categories', headers=api_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'categories' in data
        assert len(data['categories']) > 0
        # Each category should have id and name
        first = data['categories'][0]
        assert 'id' in first
        assert 'name' in first

    def test_list_categories_no_key(self, client):
        resp = client.get('/api/v1/categories')
        assert resp.status_code == 401
