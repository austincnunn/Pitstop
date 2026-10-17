"""
Actual Budget integration service

Actual Budget has no native REST API, so this talks to the community
actual-http-api sidecar (https://github.com/jhonderson/actual-http-api),
which wraps the official @actual-app/api Node package.

Transactions whose Actual category is mapped (Settings > Integrations >
Actual Budget > Map categories) are imported as Pitstop expenses.
"""

import json
import logging
from datetime import datetime, timedelta

import requests
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import AppSettings, Expense, Vehicle

logger = logging.getLogger(__name__)

SYNC_OVERLAP_DAYS = 7
DEFAULT_LOOKBACK_DAYS = 30
SYNC_INTERVAL_HOURS = 24


class ActualBudgetService:
    """Service for interacting with an actual-http-api sidecar"""

    TIMEOUT = 60

    @classmethod
    def get_config(cls):
        return {
            'url': (AppSettings.get('actual_api_url') or '').rstrip('/'),
            'api_key': AppSettings.get('actual_api_key') or '',
            'sync_id': AppSettings.get('actual_budget_sync_id') or '',
            'password': AppSettings.get('actual_budget_password') or '',
        }

    @classmethod
    def is_configured(cls):
        config = cls.get_config()
        return bool(config['url'] and config['api_key'] and config['sync_id'])

    @classmethod
    def _get(cls, path, params=None, config=None):
        """GET {url}/v1/budgets/{sync_id}/{path}; returns (success, data or message)"""
        config = config or cls.get_config()
        if not (config['url'] and config['api_key'] and config['sync_id']):
            return False, "Actual Budget is not configured"

        headers = {'x-api-key': config['api_key'], 'Accept': 'application/json'}
        if config.get('password'):
            # ponytail: header name per actual-http-api docs; confirm in its Swagger (/api-docs) if decryption fails
            headers['budget-encryption-password'] = config['password']

        try:
            response = requests.get(
                f"{config['url'].rstrip('/')}/v1/budgets/{config['sync_id']}/{path}",
                headers=headers,
                params=params,
                timeout=cls.TIMEOUT,
            )
        except requests.exceptions.Timeout:
            return False, "Actual Budget API request timed out"
        except requests.exceptions.RequestException as e:
            return False, f"Actual Budget API connection error: {str(e)}"

        if response.status_code in (401, 403):
            return False, "Invalid Actual Budget API key"
        if response.status_code == 404:
            return False, "Budget not found (check the sync ID)"
        if response.status_code != 200:
            return False, f"Actual Budget API error: {response.status_code}"

        try:
            return True, response.json().get('data')
        except ValueError:
            return False, "Actual Budget API returned invalid JSON"

    @classmethod
    def test_connection(cls, config=None):
        success, result = cls._get('accounts', config=config)
        if not success:
            return False, result
        return True, f"Connected - {len(result or [])} account(s) found"

    @classmethod
    def get_accounts(cls):
        return cls._get('accounts')

    @classmethod
    def get_categories(cls):
        return cls._get('categories')

    @classmethod
    def get_payees(cls):
        return cls._get('payees')

    @classmethod
    def get_transactions(cls, account_id, since):
        return cls._get(f'accounts/{account_id}/transactions',
                        params={'since_date': since.isoformat()})

    @classmethod
    def get_category_map(cls):
        try:
            return json.loads(AppSettings.get('actual_category_map') or '{}')
        except ValueError:
            return {}

    @classmethod
    def _sync_since(cls, now):
        """Start date for the transaction window."""
        start = None
        start_str = AppSettings.get('actual_sync_start')
        if start_str:
            try:
                start = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        last_sync = AppSettings.get('actual_last_sync')
        if last_sync:
            try:
                since = (datetime.fromisoformat(last_sync) - timedelta(days=SYNC_OVERLAP_DAYS)).date()
                return max(since, start) if start else since
            except ValueError:
                pass

        return start or (now - timedelta(days=DEFAULT_LOOKBACK_DAYS)).date()

    @classmethod
    def sync_expenses(cls, now=None):
        """
        Import mapped Actual transactions as expenses.

        Returns:
            tuple: (success: bool, stats dict {imported, skipped, errors} or error message)
        """
        now = now or datetime.utcnow()
        category_map = cls.get_category_map()
        if not category_map:
            return False, "No Actual categories are mapped to vehicles yet"

        success, accounts = cls.get_accounts()
        if not success:
            return False, accounts

        success, payees = cls.get_payees()
        if not success:
            return False, payees
        payee_names = {p['id']: p.get('name') for p in (payees or [])}

        since = cls._sync_since(now)
        stats = {'imported': 0, 'skipped': 0, 'errors': []}
        vehicles = {}
        accounts_ok = 0

        for account in accounts or []:
            if account.get('closed'):
                continue
            success, transactions = cls.get_transactions(account['id'], since)
            if not success:
                stats['errors'].append(f"{account.get('name', account['id'])}: {transactions}")
                continue
            accounts_ok += 1

            for txn in transactions or []:
                # Split transactions: import each child, inheriting the parent's payee/date
                children = txn.get('subtransactions') or [txn]
                for child in children:
                    entry = {**txn, **{k: v for k, v in child.items() if v is not None}}
                    if cls._import_transaction(entry, category_map, payee_names, vehicles):
                        stats['imported'] += 1
                    else:
                        stats['skipped'] += 1

        if stats['errors'] and not accounts_ok:
            return False, "; ".join(stats['errors'])

        AppSettings.set('actual_last_sync', now.isoformat())
        return True, stats

    @classmethod
    def _import_transaction(cls, txn, category_map, payee_names, vehicles):
        """Create an Expense from one transaction. Returns True if imported."""
        amount = txn.get('amount') or 0
        if amount >= 0 or txn.get('transfer_id'):
            return False  # refund/income or transfer

        mapping = category_map.get(txn.get('category') or '')
        if not mapping or not mapping.get('vehicle_id'):
            return False

        vehicle_id = int(mapping['vehicle_id'])
        if vehicle_id not in vehicles:
            vehicles[vehicle_id] = db.session.get(Vehicle, vehicle_id)
        vehicle = vehicles[vehicle_id]
        if not vehicle:
            return False

        try:
            date = datetime.strptime(txn['date'], '%Y-%m-%d').date()
        except (KeyError, TypeError, ValueError):
            return False

        payee = payee_names.get(txn.get('payee')) or txn.get('imported_payee')
        notes = txn.get('notes')
        description = (payee or notes or 'Actual Budget transaction')[:200]

        expense = Expense(
            vehicle_id=vehicle.id,
            user_id=vehicle.owner_id,
            date=date,
            category=mapping.get('category') or 'other',
            description=description,
            cost=abs(amount) / 100,
            vendor=payee[:100] if payee else None,
            notes=notes,
            actual_transaction_id=txn['id'],
        )

        if Expense.query.filter_by(actual_transaction_id=txn['id']).first():
            return False

        # Unique constraint still guards a manual sync racing the scheduler
        db.session.add(expense)
        try:
            db.session.commit()
            return True
        except IntegrityError:
            db.session.rollback()
            return False


def run_scheduled_actual_sync_tick(app, now=None):
    """One hourly scheduler check: sync once every SYNC_INTERVAL_HOURS when enabled."""
    if AppSettings.get('actual_sync_enabled', 'false') != 'true':
        return
    if not ActualBudgetService.is_configured():
        return

    now = now or datetime.utcnow()
    last_sync = AppSettings.get('actual_last_sync')
    if last_sync:
        try:
            if now - datetime.fromisoformat(last_sync) < timedelta(hours=SYNC_INTERVAL_HOURS):
                return
        except ValueError:
            pass

    success, result = ActualBudgetService.sync_expenses(now=now)
    if success:
        logger.info('Actual Budget sync: %s imported, %s skipped', result['imported'], result['skipped'])
    else:
        logger.error('Actual Budget sync failed: %s', result)
