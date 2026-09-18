"""Tests for emailed backups, DB dumps and the scheduler tick."""
import io
import os
import sqlite3
import zipfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app import db as _db_ext
from app.models import AppSettings, User
from app.services import backup_service as bs
from app.services.notifications import NotificationService


def _make_zip(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)


# --- send_email attachments -------------------------------------------------

class TestSendEmailAttachments:
    def _send(self, attachments=None):
        cfg = {'host': 'h', 'port': 587, 'username': 'u', 'password': 'p',
               'sender': 's@example.com', 'sender_name': 'Pitstop',
               'use_tls': False, 'use_ssl': False}
        server = MagicMock()
        with patch.object(NotificationService, 'get_smtp_config', return_value=cfg), \
                patch('app.services.notifications.smtplib.SMTP', return_value=server):
            ok, err = NotificationService.send_email('to@example.com', 'Subj', 'body',
                                                     attachments=attachments)
        assert ok, err
        return server.sendmail.call_args[0][2]

    def test_with_attachment_is_multipart_mixed(self):
        raw = self._send([('backup.zip', b'PKdata')])
        assert 'multipart/mixed' in raw
        assert 'filename="backup.zip"' in raw

    def test_without_attachment_unchanged(self):
        raw = self._send()
        assert 'multipart/alternative' in raw
        assert 'multipart/mixed' not in raw


# --- pure helpers -----------------------------------------------------------

class TestHelpers:
    @pytest.mark.parametrize('value,expected', [
        ('30', 30), ('1', 7), ('0', 7), ('9999', 180), ('abc', 7), (None, 7), ('7', 7), ('180', 180),
    ])
    def test_clamp_email_interval(self, value, expected):
        assert bs.clamp_email_interval(value) == expected

    def test_backup_email_due(self):
        now = datetime(2026, 1, 20, 2, 0)
        assert bs.backup_email_due(now, '', 7)
        assert bs.backup_email_due(now, 'garbage', 7)
        assert not bs.backup_email_due(now, (now - timedelta(days=6)).isoformat(), 7)
        assert bs.backup_email_due(now, (now - timedelta(days=7)).isoformat(), 7)

    def test_parse_postgres_url(self):
        c = bs._parse_postgres_url('postgresql+psycopg://us%40er:p%40ss@db.host:5433/pitstop')
        assert c == {'host': 'db.host', 'port': '5433', 'user': 'us@er',
                     'password': 'p@ss', 'dbname': 'pitstop'}

    def test_primary_admin_is_lowest_id(self, app, admin_user):
        other = User(username='admin2', email='a2@example.com', is_admin=True)
        other.set_password('Whatever123!')
        _db_ext.session.add(other)
        _db_ext.session.commit()
        assert bs.get_primary_admin().id == min(admin_user.id, other.id)


# --- create_db_dump ---------------------------------------------------------

class TestDbDump:
    def test_postgres_uses_list_argv_and_env_password(self, app):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg://pitstop:s3cret@postgres:5432/pitstop'
        with patch('app.services.backup_service.subprocess.run') as run:
            run.return_value = MagicMock(returncode=0, stdout=b'DUMP', stderr=b'')
            assert bs.create_db_dump() == ('database.dump', b'DUMP')
        cmd = run.call_args[0][0]
        assert cmd[0] == 'pg_dump' and cmd[-1] == 'pitstop'
        assert 's3cret' not in ' '.join(cmd)
        assert run.call_args.kwargs['env']['PGPASSWORD'] == 's3cret'
        assert run.call_args.kwargs.get('shell') is not True

    def test_failure_returns_none(self, app):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://u:p@h/db'
        with patch('app.services.backup_service.subprocess.run') as run:
            run.return_value = MagicMock(returncode=1, stdout=b'', stderr=b'boom')
            assert bs.create_db_dump() is None

    def test_missing_pg_dump_returns_none(self, app):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://u:p@h/db'
        with patch('app.services.backup_service.subprocess.run', side_effect=FileNotFoundError):
            assert bs.create_db_dump() is None

    def test_sqlite_copy(self, app, tmp_path):
        path = tmp_path / 'x.db'
        conn = sqlite3.connect(path)
        conn.execute('create table t (a)')
        conn.execute("insert into t values ('hello')")
        conn.commit()
        conn.close()
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path}'
        name, data = bs.create_db_dump()
        assert name == 'database.sqlite'
        out = tmp_path / 'copy.db'
        out.write_bytes(data)
        assert sqlite3.connect(out).execute('select a from t').fetchone() == ('hello',)


# --- create_backup_file dump inclusion --------------------------------------

class TestBackupFileDump:
    def test_dump_only_when_requested(self, app, admin_user, tmp_path):
        plain_dir, full_dir = tmp_path / 'plain', tmp_path / 'full'
        plain_dir.mkdir()
        full_dir.mkdir()
        with patch('app.services.backup_service.create_db_dump', return_value=('database.dump', b'D')):
            plain = bs.create_backup_file(admin_user, str(tmp_path), str(plain_dir))
            full = bs.create_backup_file(admin_user, str(tmp_path), str(full_dir), include_db_dump=True)
        assert 'database.dump' not in zipfile.ZipFile(plain_dir / plain).namelist()
        assert 'database.dump' in zipfile.ZipFile(full_dir / full).namelist()

    def test_user_export_route_has_no_dump(self, auth_client):
        resp = auth_client.get('/api/export/backup')
        assert resp.status_code == 200
        assert 'database.dump' not in zipfile.ZipFile(io.BytesIO(resp.data)).namelist()


# --- tiered email attachment ------------------------------------------------

class TestEmailTiers:
    @pytest.fixture
    def zip_path(self, tmp_path):
        p = tmp_path / 'pitstop_backup_x.zip'
        _make_zip(p, {'data.json': b'{"a":1}', 'manifest.json': b'{}',
                      'database.dump': b'D' * 50, 'uploads/big.bin': os.urandom(5000)})
        return str(p)

    def test_full_zip_when_small(self, zip_path):
        name, data, desc = bs.build_email_attachment(zip_path, max_bytes=10_000_000)
        assert name.endswith('.zip') and 'no_uploads' not in name
        assert 'uploads/big.bin' in zipfile.ZipFile(io.BytesIO(data)).namelist()

    def test_drops_uploads_first(self, zip_path):
        name, data, desc = bs.build_email_attachment(zip_path, max_bytes=1500)
        assert 'no_uploads' in name
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        assert 'uploads/big.bin' not in names and 'database.dump' in names

    def test_dump_only_then_data_json(self, zip_path):
        with patch.object(bs.zipfile, 'ZipFile', wraps=zipfile.ZipFile):
            name, data, _ = bs.build_email_attachment(zip_path, max_bytes=60)
        assert name == 'database.dump'
        name, data, _ = bs.build_email_attachment(zip_path, max_bytes=10)
        assert name == 'data.json'
        assert bs.build_email_attachment(zip_path, max_bytes=1) is None


# --- scheduler tick ---------------------------------------------------------

class TestSchedulerTick:
    def _setup(self, app, admin_user, **settings):
        base = {'backup_hour': '2', 'backup_email_enabled': 'true',
                'backup_email_interval_days': '7', 'backup_enabled': 'false',
                'smtp_host': 'h', 'smtp_username': 'u'}
        base.update(settings)
        for k, v in base.items():
            AppSettings.set(k, v)

    def test_wrong_hour_does_nothing(self, app, admin_user):
        self._setup(app, admin_user)
        with patch.object(bs, 'send_backup_email_now') as send:
            bs.run_scheduled_backup_tick(app, now=datetime(2026, 1, 1, 5, 0))
        send.assert_not_called()

    def test_email_sent_when_due_even_if_disk_disabled(self, app, admin_user):
        self._setup(app, admin_user)
        with patch.object(bs, 'send_backup_email_now', return_value=(True, None)) as send:
            bs.run_scheduled_backup_tick(app, now=datetime(2026, 1, 1, 2, 0))
        send.assert_called_once()

    def test_not_due_within_interval(self, app, admin_user):
        now = datetime(2026, 1, 10, 2, 0)
        self._setup(app, admin_user, backup_email_last_sent=(now - timedelta(days=3)).isoformat())
        with patch.object(bs, 'send_backup_email_now') as send:
            bs.run_scheduled_backup_tick(app, now=now)
        send.assert_not_called()

    def test_disabled_does_nothing(self, app, admin_user):
        self._setup(app, admin_user, backup_email_enabled='false')
        with patch.object(bs, 'send_backup_email_now') as send:
            bs.run_scheduled_backup_tick(app, now=datetime(2026, 1, 1, 2, 0))
        send.assert_not_called()

    def test_hourly_retry_guard(self, app, admin_user):
        now = datetime(2026, 1, 1, 2, 30)
        self._setup(app, admin_user, backup_email_last_attempt=(now - timedelta(minutes=20)).isoformat())
        with patch.object(bs, 'send_backup_email_now') as send:
            bs.run_scheduled_backup_tick(app, now=now)
        send.assert_not_called()


# --- send_backup_email_now --------------------------------------------------

class TestSendNow:
    def test_success_records_last_sent(self, app, admin_user):
        with patch.object(NotificationService, 'send_email', return_value=(True, None)) as send:
            ok, err = bs.send_backup_email_now(app)
        assert ok and err is None
        assert send.call_args[0][0] == admin_user.email
        assert send.call_args.kwargs['attachments']
        assert AppSettings.get('backup_email_last_sent')

    def test_failure_leaves_last_sent_unchanged(self, app, admin_user):
        with patch.object(NotificationService, 'send_email', return_value=(False, 'smtp down')):
            ok, err = bs.send_backup_email_now(app)
        assert not ok and err == 'smtp down'
        assert not AppSettings.get('backup_email_last_sent', '')

    def test_no_primary_admin(self, app):
        User.query.delete()
        _db_ext.session.commit()
        ok, err = bs.send_backup_email_now(app)
        assert not ok


# --- admin routes -----------------------------------------------------------

class TestAdminRoutes:
    def test_save_settings_clamps_and_persists(self, admin_client):
        admin_client.post('/admin/backups/settings', data={
            'backup_frequency': 'daily', 'backup_hour': '2', 'backup_retention': '7',
            'backup_email_enabled': 'on', 'backup_email_interval_days': '3',
        }, follow_redirects=True)
        assert AppSettings.get('backup_email_enabled') == 'true'
        assert AppSettings.get('backup_email_interval_days') == '7'
        admin_client.post('/admin/backups/settings', data={
            'backup_frequency': 'daily', 'backup_hour': '2', 'backup_retention': '7',
            'backup_email_interval_days': '99999',
        }, follow_redirects=True)
        assert AppSettings.get('backup_email_enabled') == 'false'
        assert AppSettings.get('backup_email_interval_days') == '180'

    def test_page_renders(self, admin_client):
        resp = admin_client.get('/admin/backups')
        assert resp.status_code == 200
        assert b'Email a backup to the primary admin' in resp.data

    def test_email_now_requires_admin(self, auth_client):
        assert auth_client.post('/admin/backups/email-now').status_code == 403

    def test_email_now(self, admin_client):
        with patch('app.routes.admin.send_backup_email_now', return_value=(True, None)):
            resp = admin_client.post('/admin/backups/email-now', follow_redirects=True)
        assert b'Backup emailed' in resp.data


class TestSettingsNav:
    def test_admin_sees_backups_link(self, admin_client):
        assert b'href="/admin/backups"' in admin_client.get('/auth/settings').data

    def test_non_admin_does_not(self, auth_client):
        assert b'/admin/backups' not in auth_client.get('/auth/settings').data

    def test_backups_page_shows_nav_with_backups_active(self, admin_client):
        import re
        html = admin_client.get('/admin/backups').data.decode()
        active = re.findall(r'<a href="[^"]*" class="settings-nav-item active', html)
        assert len(active) == 1
        assert re.search(r'href="/admin/backups" class="settings-nav-item active', html)
        # tab links point back at the settings page instead of in-page anchors
        assert 'href="/auth/settings#account"' in html
        assert 'showSection' not in html

    def test_settings_page_still_has_units_active(self, admin_client):
        import re
        html = admin_client.get('/auth/settings').data.decode()
        assert re.search(r'href="#units" class="settings-nav-item active', html)
        assert html.count('settings-nav-item active') == 1
        assert "showSection('account', event)" in html
