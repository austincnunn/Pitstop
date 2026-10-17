"""Tests for the Actual Budget expense import integration."""
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import requests

from app import db
from app.models import AppSettings, Expense, Vehicle
from app.services.actual_budget import ActualBudgetService, run_scheduled_actual_sync_tick

NOW = datetime(2026, 10, 17, 12, 0, 0)


def _response(data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {'data': data}
    return resp


def _fake_get(transactions, accounts=None):
    accounts = accounts if accounts is not None else [{'id': 'acc1', 'name': 'Checking', 'closed': False}]

    def fake(url, headers=None, params=None, timeout=None):
        assert headers['x-api-key'] == 'key'
        if url.endswith('/accounts'):
            return _response(accounts)
        if url.endswith('/payees'):
            return _response([{'id': 'p1', 'name': 'Shell'}, {'id': 'p2', 'name': 'Jiffy Lube'}])
        if url.endswith('/categories'):
            return _response([
                {'id': 'cat-fuel', 'name': 'Fuel', 'is_income': False, 'hidden': False},
                {'id': 'cat-pay', 'name': 'Paycheck', 'is_income': True, 'hidden': False},
            ])
        if '/transactions' in url:
            return _response(transactions)
        raise AssertionError(url)
    return fake


def _configure(vehicle, category='maintenance'):
    AppSettings.set('actual_api_url', 'http://actual:5007')
    AppSettings.set('actual_api_key', 'key')
    AppSettings.set('actual_budget_sync_id', 'sync-1')
    AppSettings.set('actual_category_map', json.dumps({
        'cat-car': {'name': 'Car', 'vehicle_id': vehicle.id, 'category': category},
    }))


def _txn(id, amount=-4567, category='cat-car', **kw):
    return {'id': id, 'account': 'acc1', 'date': '2026-10-10', 'amount': amount,
            'payee': 'p2', 'category': category, 'notes': None, 'transfer_id': None, **kw}


class TestSyncExpenses:
    def test_imports_mapped_transaction_and_dedupes(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        with patch('app.services.actual_budget.requests.get', side_effect=_fake_get([_txn('t1')])):
            ok, stats = ActualBudgetService.sync_expenses(now=NOW)
            assert ok and stats['imported'] == 1

            expense = Expense.query.filter_by(actual_transaction_id='t1').one()
            assert expense.cost == 45.67
            assert expense.vendor == 'Jiffy Lube'
            assert expense.description == 'Jiffy Lube'
            assert expense.category == 'maintenance'
            assert expense.user_id == sample_vehicle.owner_id
            assert expense.date.isoformat() == '2026-10-10'

            ok, stats = ActualBudgetService.sync_expenses(now=NOW)
            assert ok and stats['imported'] == 0 and stats['skipped'] == 1
        assert Expense.query.filter_by(actual_transaction_id='t1').count() == 1
        assert AppSettings.get('actual_last_sync') == NOW.isoformat()

    def test_skips_unmapped_transfer_refund_and_missing_vehicle(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        maps = json.loads(AppSettings.get('actual_category_map'))
        maps['cat-gone'] = {'name': 'Old', 'vehicle_id': 999999, 'category': 'other'}
        AppSettings.set('actual_category_map', json.dumps(maps))
        txns = [
            _txn('t-unmapped', category='cat-groceries'),
            _txn('t-transfer', transfer_id='x'),
            _txn('t-refund', amount=2000),
            _txn('t-gone', category='cat-gone'),
        ]
        with patch('app.services.actual_budget.requests.get', side_effect=_fake_get(txns)):
            ok, stats = ActualBudgetService.sync_expenses(now=NOW)
        assert ok and stats == {'imported': 0, 'skipped': 4, 'errors': []}
        assert Expense.query.count() == 0

    def test_split_children_imported_individually(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        parent = _txn('parent', amount=-3000, category=None, payee='p1', subtransactions=[
            {'id': 'child1', 'amount': -2000, 'category': 'cat-car', 'payee': None},
            {'id': 'child2', 'amount': -1000, 'category': 'cat-groceries', 'payee': None},
        ])
        with patch('app.services.actual_budget.requests.get', side_effect=_fake_get([parent])):
            ok, stats = ActualBudgetService.sync_expenses(now=NOW)
        assert ok and stats['imported'] == 1 and stats['skipped'] == 1
        child = Expense.query.filter_by(actual_transaction_id='child1').one()
        assert child.cost == 20.0
        assert child.vendor == 'Shell'  # inherited from parent

    def test_timeout_returns_error(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        with patch('app.services.actual_budget.requests.get', side_effect=requests.exceptions.Timeout):
            ok, message = ActualBudgetService.sync_expenses(now=NOW)
        assert not ok and 'timed out' in message
        assert AppSettings.get('actual_last_sync') is None

    def test_http_error_returns_error(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        with patch('app.services.actual_budget.requests.get', return_value=_response(None, status=401)):
            ok, message = ActualBudgetService.sync_expenses(now=NOW)
        assert not ok and 'API key' in message

    def test_no_mapping_returns_error(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        AppSettings.set('actual_category_map', '{}')
        ok, message = ActualBudgetService.sync_expenses(now=NOW)
        assert not ok

    def test_since_uses_overlap_but_not_before_start(self, app):
        AppSettings.set('actual_last_sync', NOW.isoformat())
        assert ActualBudgetService._sync_since(NOW) == (NOW - timedelta(days=7)).date()
        AppSettings.set('actual_sync_start', '2026-10-15')
        assert ActualBudgetService._sync_since(NOW).isoformat() == '2026-10-15'


class TestScheduledTick:
    def test_disabled_does_nothing(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        with patch.object(ActualBudgetService, 'sync_expenses') as sync:
            run_scheduled_actual_sync_tick(app, now=NOW)
        sync.assert_not_called()

    def test_never_synced_runs(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        AppSettings.set('actual_sync_enabled', 'true')
        with patch('app.services.actual_budget.requests.get', side_effect=_fake_get([_txn('t1')])):
            run_scheduled_actual_sync_tick(app, now=NOW)
        assert Expense.query.count() == 1
        assert AppSettings.get('actual_last_sync') == NOW.isoformat()

    def test_not_due_skips(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        AppSettings.set('actual_sync_enabled', 'true')
        AppSettings.set('actual_last_sync', (NOW - timedelta(hours=5)).isoformat())
        with patch.object(ActualBudgetService, 'sync_expenses') as sync:
            run_scheduled_actual_sync_tick(app, now=NOW)
        sync.assert_not_called()

    def test_due_runs_and_failure_keeps_timestamp(self, app, test_user, sample_vehicle):
        _configure(sample_vehicle)
        AppSettings.set('actual_sync_enabled', 'true')
        old = (NOW - timedelta(hours=25)).isoformat()
        AppSettings.set('actual_last_sync', old)
        with patch('app.services.actual_budget.requests.get', side_effect=requests.exceptions.ConnectionError):
            run_scheduled_actual_sync_tick(app, now=NOW)
        assert AppSettings.get('actual_last_sync') == old


class TestRoutes:
    def test_routes_admin_only(self, auth_client):
        assert auth_client.post('/api/actual/sync').status_code == 403
        assert auth_client.post('/api/actual/test').status_code == 403
        resp = auth_client.post('/auth/actual-settings', data={'actual_api_url': 'http://x'})
        assert resp.status_code in (302, 403)
        assert AppSettings.get('actual_api_url') is None
        assert auth_client.get('/auth/actual-mapping').status_code in (302, 403)

    def test_settings_blank_secret_keeps_stored_value(self, admin_client):
        AppSettings.set('actual_api_key', 'original')
        resp = admin_client.post('/auth/actual-settings', data={
            'actual_api_url': 'http://actual:5007/', 'actual_api_key': '',
            'actual_budget_sync_id': 'sync-1', 'actual_sync_enabled': 'on',
        })
        assert resp.status_code == 302
        assert AppSettings.get('actual_api_key') == 'original'
        assert AppSettings.get('actual_api_url') == 'http://actual:5007'
        assert AppSettings.get('actual_sync_enabled') == 'true'

    def test_settings_rejects_non_http_url(self, admin_client):
        admin_client.post('/auth/actual-settings', data={'actual_api_url': 'file:///etc/passwd'})
        assert AppSettings.get('actual_api_url') is None

    def test_settings_page_does_not_render_secret(self, admin_client):
        AppSettings.set('actual_api_key', 'super-secret-key')
        resp = admin_client.get('/auth/settings')
        assert resp.status_code == 200
        assert b'super-secret-key' not in resp.data
        assert b'integration-actual' in resp.data

    def test_mapping_round_trip(self, admin_client, admin_user):
        vehicle = Vehicle(owner_id=admin_user.id, name='Truck', vehicle_type='truck', fuel_type='diesel')
        db.session.add(vehicle)
        db.session.commit()
        _configure(vehicle)
        with patch('app.services.actual_budget.requests.get', side_effect=_fake_get([])):
            resp = admin_client.get('/auth/actual-mapping')
        assert resp.status_code == 200
        assert b'Fuel' in resp.data and b'Paycheck' not in resp.data

        admin_client.post('/auth/actual-mapping', data={
            'category_ids': ['cat-fuel', 'cat-other'],
            'name_cat-fuel': 'Fuel', 'vehicle_cat-fuel': str(vehicle.id), 'category_cat-fuel': 'bogus',
            'name_cat-other': 'Other', 'vehicle_cat-other': '',
        })
        assert json.loads(AppSettings.get('actual_category_map')) == {
            'cat-fuel': {'name': 'Fuel', 'vehicle_id': vehicle.id, 'category': 'other'},
        }

    def test_mapping_page_shows_error_when_unreachable(self, admin_client):
        resp = admin_client.get('/auth/actual-mapping')
        assert resp.status_code == 200
        assert b'not configured' in resp.data

    def test_sync_endpoint(self, admin_client, admin_user):
        vehicle = Vehicle(owner_id=admin_user.id, name='Truck', vehicle_type='truck', fuel_type='diesel')
        db.session.add(vehicle)
        db.session.commit()
        _configure(vehicle)
        with patch('app.services.actual_budget.requests.get', side_effect=_fake_get([_txn('t1')])):
            data = admin_client.post('/api/actual/sync').get_json()
        assert data['success'] and data['imported'] == 1

    def test_test_endpoint_uses_form_values(self, admin_client):
        with patch('app.services.actual_budget.requests.get', side_effect=_fake_get([])) as get:
            data = admin_client.post('/api/actual/test', data={
                'actual_api_url': 'http://actual:5007', 'actual_api_key': 'key',
                'actual_budget_sync_id': 'sync-1',
            }).get_json()
        assert data['success']
        assert get.call_args[0][0] == 'http://actual:5007/v1/budgets/sync-1/accounts'
