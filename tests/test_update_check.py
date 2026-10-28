from unittest.mock import MagicMock, patch

import requests

from app.models import AppSettings
from app.services import update_check
from app.services.update_check import check_for_update, run_update_check_tick


def _resp(status=200, data=None):
    r = MagicMock(status_code=status)
    r.json.return_value = data or {}
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(str(status))
    return r


def _github(release=None, dev_head=None):
    """Fake requests.get: release tag (None = 404) and dev branch head SHA."""
    def get(url, timeout):
        if url.endswith('/releases/latest'):
            if release is None:
                return _resp(404)
            return _resp(data={'tag_name': release, 'html_url': f'https://github.com/x/releases/{release}'})
        return _resp(data={'sha': dev_head})
    return get


def _dev(monkeypatch, sha='abc1234'):
    monkeypatch.setattr(update_check, 'RELEASE_CHANNEL', 'dev')
    monkeypatch.setattr(update_check, 'GIT_SHA', sha)


def test_newer_release_stored(app):
    with app.app_context(), patch('requests.get', _github(release='v99.0.0')):
        run_update_check_tick()
        assert AppSettings.get('update_latest') == '99.0.0'
        assert AppSettings.get('update_url').endswith('v99.0.0')


def test_equal_or_older_release_not_flagged(app, monkeypatch):
    monkeypatch.setattr(update_check, 'APP_VERSION', '0.15.0')
    for tag in ('v0.15.0', 'v0.9.9', '0.14.10'):
        with patch('requests.get', _github(release=tag)):
            assert not check_for_update()['update_available'], tag
    with patch('requests.get', _github(release='v0.15.1')):
        assert check_for_update()['latest'] == '0.15.1'


def test_no_releases_on_stable_is_no_update(app):
    with patch('requests.get', _github(release=None)):
        assert check_for_update()['update_available'] is False


def test_dev_build_sees_new_dev_commit(app, monkeypatch):
    _dev(monkeypatch)
    with patch('requests.get', _github(release=None, dev_head='def5678' + '0' * 33)):
        result = check_for_update()
    assert result['update_available'] and result['latest'] == 'dev+def5678'
    assert result['url'].endswith('/compare/abc1234...dev')

    with patch('requests.get', _github(release=None, dev_head='abc1234' + '0' * 33)):
        assert check_for_update()['update_available'] is False


def test_dev_build_prefers_newer_release(app, monkeypatch):
    _dev(monkeypatch)
    with patch('requests.get', _github(release='v99.0.0', dev_head='def5678' + '0' * 33)):
        result = check_for_update()
    assert result['latest'] == '99.0.0' and 'releases' in result['url']


def test_network_error_keeps_previous_value(app):
    with app.app_context():
        AppSettings.set('update_latest', '1.2.3')
        with patch('requests.get', side_effect=requests.ConnectionError('offline')):
            run_update_check_tick()
        assert AppSettings.get('update_latest') == '1.2.3'


def test_banner_only_for_admins(app, admin_client, client, test_user):
    with app.app_context():
        AppSettings.set('update_latest', '99.0.0')
    assert b'99.0.0 is available' in admin_client.get('/dashboard').data

    admin_client.get('/auth/logout')
    client.post('/auth/login', data={'username': 'testuser', 'password': 'TestPass123!'})
    assert b'99.0.0 is available' not in client.get('/dashboard').data
