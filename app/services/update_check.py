"""Check GitHub for a newer Pitstop release (and, on dev builds, a newer dev commit)."""
import logging
import re

import requests

from config import APP_VERSION, GITHUB_REPO, GIT_SHA, RELEASE_CHANNEL

logger = logging.getLogger(__name__)
API = f'https://api.github.com/repos/{GITHUB_REPO}'


def _vtuple(version):
    return tuple(int(n) for n in re.findall(r'\d+', version or ''))


def check_for_update():
    """Return {'current', 'latest', 'url', 'update_available'}. Raises requests.RequestException on network errors."""
    result = {'current': APP_VERSION, 'latest': None, 'url': None, 'update_available': False}

    response = requests.get(f'{API}/releases/latest', timeout=5)
    if response.status_code != 404:  # 404 = no releases published yet
        response.raise_for_status()
        release = response.json()
        tag = (release.get('tag_name') or '').lstrip('v')
        if _vtuple(tag) > _vtuple(APP_VERSION):
            result.update(latest=tag, url=release.get('html_url'), update_available=True)
            return result

    if RELEASE_CHANNEL == 'dev' and GIT_SHA:
        response = requests.get(f'{API}/commits/dev', timeout=5)
        response.raise_for_status()
        head = response.json().get('sha') or ''
        if head and not head.startswith(GIT_SHA):
            result.update(latest=f'dev+{head[:7]}', url=f'https://github.com/{GITHUB_REPO}/compare/{GIT_SHA}...dev',
                          update_available=True)
    return result


def run_update_check_tick():
    """Store the newest available version in AppSettings so the admin banner can show it."""
    from app.models import AppSettings
    try:
        result = check_for_update()
    except requests.RequestException as e:
        logger.warning('Update check failed: %s', e)
        return
    AppSettings.set('update_latest', result['latest'] if result['update_available'] else '')
    AppSettings.set('update_url', result['url'] or '')
