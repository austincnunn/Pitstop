import pytest
from app import db
from app.models import Reminder
from datetime import date


@pytest.fixture
def sample_reminder(app, test_user, sample_vehicle):
    reminder = Reminder(
        vehicle_id=sample_vehicle.id,
        user_id=test_user.id,
        title='MOT Due',
        reminder_type='mot',
        due_date=date(2025, 6, 1),
        recurrence='none',
        notify_days_before=7,
    )
    db.session.add(reminder)
    db.session.commit()
    return reminder


class TestReminderIndex:
    def test_index_requires_auth(self, client):
        resp = client.get('/reminders/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_index_returns_200(self, auth_client):
        resp = auth_client.get('/reminders/')
        assert resp.status_code == 200

    def test_index_shows_reminders(self, auth_client, sample_reminder):
        resp = auth_client.get('/reminders/')
        assert resp.status_code == 200
        assert b'MOT Due' in resp.data


class TestReminderNew:
    def test_new_requires_auth(self, client):
        resp = client.get('/reminders/new', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_new_form_returns_200(self, auth_client, sample_vehicle):
        resp = auth_client.get('/reminders/new')
        assert resp.status_code == 200

    def test_create_reminder(self, auth_client, sample_vehicle, test_user):
        resp = auth_client.post('/reminders/new', data={
            'vehicle_id': str(sample_vehicle.id),
            'title': 'Service Due',
            'reminder_type': 'service',
            'due_date': '2025-12-01',
            'recurrence': 'none',
            'notify_days_before': '7',
        }, follow_redirects=True)
        assert resp.status_code == 200
        reminder = Reminder.query.filter_by(title='Service Due').first()
        assert reminder is not None
        assert reminder.user_id == test_user.id


class TestReminderEdit:
    def test_edit_requires_auth(self, client, sample_reminder):
        resp = client.get(f'/reminders/{sample_reminder.id}/edit', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_edit_form_returns_200(self, auth_client, sample_reminder):
        resp = auth_client.get(f'/reminders/{sample_reminder.id}/edit')
        assert resp.status_code == 200

    def test_edit_reminder(self, auth_client, sample_reminder):
        resp = auth_client.post(f'/reminders/{sample_reminder.id}/edit', data={
            'title': 'Updated MOT',
            'reminder_type': 'mot',
            'due_date': '2025-07-01',
            'recurrence': 'yearly',
            'notify_days_before': '14',
        }, follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_reminder)
        assert sample_reminder.title == 'Updated MOT'
        assert sample_reminder.recurrence == 'yearly'


class TestReminderDelete:
    def test_delete_requires_auth(self, client, sample_reminder):
        resp = client.post(f'/reminders/{sample_reminder.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_delete_reminder(self, auth_client, sample_reminder):
        reminder_id = sample_reminder.id
        resp = auth_client.post(f'/reminders/{reminder_id}/delete', follow_redirects=True)
        assert resp.status_code == 200
        assert Reminder.query.get(reminder_id) is None


class TestReminderComplete:
    def test_complete_requires_auth(self, client, sample_reminder):
        resp = client.post(f'/reminders/{sample_reminder.id}/complete', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_complete_reminder(self, auth_client, sample_reminder):
        resp = auth_client.post(f'/reminders/{sample_reminder.id}/complete', follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_reminder)
        assert sample_reminder.is_completed is True

    def test_uncomplete_reminder(self, auth_client, sample_reminder):
        sample_reminder.is_completed = True
        db.session.commit()

        resp = auth_client.post(f'/reminders/{sample_reminder.id}/uncomplete', follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_reminder)
        assert sample_reminder.is_completed is False
