import pytest
from app import db
from app.models import Expense


class TestExpenseIndex:
    def test_index_requires_auth(self, client):
        resp = client.get('/expenses/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_index_returns_200(self, auth_client):
        resp = auth_client.get('/expenses/')
        assert resp.status_code == 200

    def test_index_shows_expenses(self, auth_client, sample_expense):
        resp = auth_client.get('/expenses/')
        assert resp.status_code == 200


class TestExpenseNew:
    def test_new_requires_auth(self, client):
        resp = client.get('/expenses/new', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_new_form_returns_200(self, auth_client, sample_vehicle):
        resp = auth_client.get('/expenses/new')
        assert resp.status_code == 200

    def test_create_expense(self, auth_client, sample_vehicle, test_user):
        resp = auth_client.post('/expenses/new', data={
            'vehicle_id': str(sample_vehicle.id),
            'date': '2024-02-10',
            'category': 'maintenance',
            'description': 'Tire rotation',
            'cost': '50.00',
        }, follow_redirects=True)
        assert resp.status_code == 200
        expense = Expense.query.filter_by(
            vehicle_id=sample_vehicle.id,
            description='Tire rotation'
        ).first()
        assert expense is not None
        assert expense.cost == 50.0
        assert expense.user_id == test_user.id

    def test_create_expense_with_optional_fields(self, auth_client, sample_vehicle):
        resp = auth_client.post('/expenses/new', data={
            'vehicle_id': str(sample_vehicle.id),
            'date': '2024-02-15',
            'category': 'insurance',
            'description': 'Annual insurance',
            'cost': '500.00',
            'vendor': 'Insurance Co',
            'notes': 'Full coverage',
        }, follow_redirects=True)
        assert resp.status_code == 200
        expense = Expense.query.filter_by(description='Annual insurance').first()
        assert expense is not None
        assert expense.vendor == 'Insurance Co'


class TestExpenseEdit:
    def test_edit_requires_auth(self, client, sample_expense):
        resp = client.get(f'/expenses/{sample_expense.id}/edit', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_edit_form_returns_200(self, auth_client, sample_expense):
        resp = auth_client.get(f'/expenses/{sample_expense.id}/edit')
        assert resp.status_code == 200

    def test_edit_expense(self, auth_client, sample_expense):
        resp = auth_client.post(f'/expenses/{sample_expense.id}/edit', data={
            'date': '2024-01-20',
            'category': 'maintenance',
            'description': 'Updated oil change',
            'cost': '85.00',
        }, follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_expense)
        assert sample_expense.description == 'Updated oil change'
        assert sample_expense.cost == 85.0


class TestExpenseDelete:
    def test_delete_requires_auth(self, client, sample_expense):
        resp = client.post(f'/expenses/{sample_expense.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_delete_expense(self, auth_client, sample_expense):
        expense_id = sample_expense.id
        resp = auth_client.post(f'/expense_id/delete'.replace('expense_id', str(expense_id)),
                                follow_redirects=True)
        # Use correct URL
        resp = auth_client.post(f'/expenses/{expense_id}/delete', follow_redirects=True)
        assert resp.status_code == 200
        assert Expense.query.get(expense_id) is None
