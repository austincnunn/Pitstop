"""Tests for OpenID Connect single sign-on (app/services/oidc.py and the /auth/oidc routes)."""
import time
from urllib.parse import urlparse, parse_qs

import pytest
from app import create_app, db
from app.models import User
from tests.conftest import TestConfig


class OIDCTestConfig(TestConfig):
    OIDC_ENABLED = True
    OIDC_DISCOVERY_URL = 'https://auth.example.com/.well-known/openid-configuration'
    OIDC_CLIENT_ID = 'pitstop'
    OIDC_CLIENT_SECRET = 'client-secret'
    OIDC_SCOPES = 'openid email profile groups'
    OIDC_PROVIDER_NAME = 'Authelia'
    OIDC_REDIRECT_URI = None
    OIDC_AUTO_REGISTER = True
    OIDC_ADMIN_GROUP = None


class FakeOIDCClient:
    """Stands in for the Authlib client so the callback can run without a provider."""

    def __init__(self, id_claims=None, userinfo=None, error=None):
        self.id_claims = id_claims or {}
        self.userinfo_claims = userinfo if userinfo is not None else dict(self.id_claims)
        self.error = error

    def authorize_access_token(self):
        if self.error:
            raise self.error
        return {'access_token': 'at', 'userinfo': dict(self.id_claims)}

    def userinfo(self, token):
        return dict(self.userinfo_claims)


def claims(sub='sub-1', email='sso@example.com', **extra):
    data = {'sub': sub, 'email': email, 'email_verified': True, 'preferred_username': 'ssouser'}
    data.update(extra)
    return data


def make_app(config_class):
    flask_app = create_app(config_class)
    ctx = flask_app.app_context()
    ctx.push()
    return flask_app, ctx


@pytest.fixture
def app():
    """Overrides conftest's app so `client` and `test_user` run with SSO enabled."""
    flask_app, ctx = make_app(OIDCTestConfig)
    yield flask_app
    db.session.remove()
    db.drop_all()
    ctx.pop()


@pytest.fixture
def plain_client():
    """A client for an app with SSO switched off."""
    flask_app, ctx = make_app(TestConfig)
    yield flask_app.test_client()
    db.session.remove()
    db.drop_all()
    ctx.pop()


def use_fake(app, **kwargs):
    fake = FakeOIDCClient(**kwargs)
    app.extensions['pitstop_oidc'] = fake
    return fake


def logged_in_user_id(client):
    with client.session_transaction() as sess:
        return sess.get('_user_id')


# ---------------------------------------------------------------------------
# Disabled / misconfigured
# ---------------------------------------------------------------------------

class TestOIDCDisabled:
    def test_login_page_has_no_sso_button(self, plain_client):
        response = plain_client.get('/auth/login')
        assert b'Sign in with' not in response.data

    def test_sso_routes_404(self, plain_client):
        assert plain_client.get('/auth/oidc/login').status_code == 404
        assert plain_client.get('/auth/oidc/callback').status_code == 404

    def test_missing_secret_disables_sso(self):
        class Incomplete(OIDCTestConfig):
            OIDC_CLIENT_SECRET = None

        flask_app, ctx = make_app(Incomplete)
        try:
            assert 'pitstop_oidc' not in flask_app.extensions
            assert flask_app.test_client().get('/auth/oidc/login').status_code == 404
        finally:
            db.session.remove()
            db.drop_all()
            ctx.pop()


# ---------------------------------------------------------------------------
# Starting the login
# ---------------------------------------------------------------------------

class TestOIDCLoginStart:
    def test_login_page_shows_button(self, client):
        response = client.get('/auth/login')
        assert b'Sign in with Authelia' in response.data

    def test_redirects_to_provider_with_pkce(self, app, client):
        sso = app.extensions['pitstop_oidc']
        sso.server_metadata.update({
            'issuer': 'https://auth.example.com',
            'authorization_endpoint': 'https://auth.example.com/api/oidc/authorization',
            'token_endpoint': 'https://auth.example.com/api/oidc/token',
            '_loaded_at': time.time(),
        })

        response = client.get('/auth/oidc/login?next=/vehicles/')

        assert response.status_code == 302
        location = urlparse(response.headers['Location'])
        assert location.netloc == 'auth.example.com'
        params = parse_qs(location.query)
        assert params['client_id'] == ['pitstop']
        assert params['redirect_uri'] == ['http://localhost/auth/oidc/callback']
        assert params['scope'] == ['openid email profile groups']
        assert params['code_challenge_method'] == ['S256']
        assert 'state' in params and 'nonce' in params
        with client.session_transaction() as sess:
            assert sess['oidc_next'] == '/vehicles/'

    def test_redirect_uri_override(self, app, client):
        app.config['OIDC_REDIRECT_URI'] = 'https://pitstop.example.com/auth/oidc/callback'
        app.extensions['pitstop_oidc'].server_metadata.update({
            'authorization_endpoint': 'https://auth.example.com/api/oidc/authorization',
            '_loaded_at': time.time(),
        })

        response = client.get('/auth/oidc/login')

        params = parse_qs(urlparse(response.headers['Location']).query)
        assert params['redirect_uri'] == ['https://pitstop.example.com/auth/oidc/callback']

    def test_provider_unreachable_falls_back_to_login(self, app, client):
        class Broken:
            def authorize_redirect(self, redirect_uri):
                raise ConnectionError('discovery failed')

        app.extensions['pitstop_oidc'] = Broken()
        response = client.get('/auth/oidc/login', follow_redirects=True)
        assert b'Single sign-on is unavailable' in response.data


# ---------------------------------------------------------------------------
# Callback: matching and creating users
# ---------------------------------------------------------------------------

class TestOIDCCallback:
    def test_creates_new_user(self, app, client):
        use_fake(app, id_claims=claims())

        response = client.get('/auth/oidc/callback')

        assert response.status_code == 302
        user = User.query.filter_by(oidc_subject='sub-1').first()
        assert user is not None
        assert user.username == 'ssouser'
        assert user.email == 'sso@example.com'
        assert not user.is_admin
        assert logged_in_user_id(client) == str(user.id)

    def test_links_existing_user_by_verified_email(self, app, client, test_user):
        use_fake(app, id_claims=claims(email='TEST@example.com'))

        client.get('/auth/oidc/callback')

        db.session.refresh(test_user)
        assert test_user.oidc_subject == 'sub-1'
        assert logged_in_user_id(client) == str(test_user.id)
        assert User.query.filter_by(email='sso@example.com').first() is None

    def test_unverified_email_is_not_linked(self, app, client, test_user):
        use_fake(app, id_claims=claims(email='test@example.com', email_verified=False))

        response = client.get('/auth/oidc/callback', follow_redirects=True)

        assert b'not verified' in response.data
        db.session.refresh(test_user)
        assert test_user.oidc_subject is None
        assert logged_in_user_id(client) is None

    def test_email_linked_to_other_subject_is_rejected(self, app, client, test_user):
        test_user.oidc_subject = 'someone-else'
        db.session.commit()
        use_fake(app, id_claims=claims(email='test@example.com'))

        response = client.get('/auth/oidc/callback', follow_redirects=True)

        assert b'already linked to a different SSO account' in response.data
        assert logged_in_user_id(client) is None

    def test_returning_user_matched_by_subject(self, app, client, test_user):
        test_user.oidc_subject = 'sub-1'
        db.session.commit()
        use_fake(app, id_claims=claims(email='changed@example.com'))

        client.get('/auth/oidc/callback')

        assert logged_in_user_id(client) == str(test_user.id)
        assert User.query.count() == 2  # auto-created admin + test_user

    def test_auto_register_off_rejects_unknown_user(self, app, client):
        app.config['OIDC_AUTO_REGISTER'] = False
        use_fake(app, id_claims=claims())

        response = client.get('/auth/oidc/callback', follow_redirects=True)

        assert b'No Pitstop account matches' in response.data
        assert User.query.filter_by(oidc_subject='sub-1').first() is None

    def test_new_user_without_email_is_rejected(self, app, client):
        use_fake(app, id_claims={'sub': 'sub-1'})

        response = client.get('/auth/oidc/callback', follow_redirects=True)

        assert b'did not return an email address' in response.data

    def test_username_collision_gets_suffix(self, app, client, test_user):
        use_fake(app, id_claims=claims(preferred_username='testuser'))

        client.get('/auth/oidc/callback')

        assert User.query.filter_by(oidc_subject='sub-1').first().username == 'testuser2'

    def test_username_falls_back_to_email(self, app, client):
        use_fake(app, id_claims=claims(preferred_username=None, email='jane.doe@example.com'))

        client.get('/auth/oidc/callback')

        assert User.query.filter_by(oidc_subject='sub-1').first().username == 'jane.doe'

    def test_claims_from_userinfo_are_used(self, app, client):
        # Minimal ID token (as Authelia 4.39+ issues by default); details come from userinfo
        use_fake(app, id_claims={'sub': 'sub-1'}, userinfo=claims())

        client.get('/auth/oidc/callback')

        assert User.query.filter_by(oidc_subject='sub-1').first().email == 'sso@example.com'

    def test_userinfo_subject_mismatch_fails(self, app, client):
        use_fake(app, id_claims=claims(), userinfo=claims(sub='other'))

        response = client.get('/auth/oidc/callback', follow_redirects=True)

        assert b'Single sign-on failed' in response.data
        assert User.query.filter_by(oidc_subject='sub-1').first() is None

    def test_provider_error_fails_cleanly(self, app, client):
        use_fake(app, error=Exception('access_denied'))

        response = client.get('/auth/oidc/callback', follow_redirects=True)

        assert response.status_code == 200
        assert b'Single sign-on failed' in response.data
        assert logged_in_user_id(client) is None


class TestOIDCAdminGroup:
    def test_member_of_admin_group_becomes_admin(self, app, client):
        app.config['OIDC_ADMIN_GROUP'] = 'admins'
        use_fake(app, id_claims=claims(groups=['users', 'admins']))

        client.get('/auth/oidc/callback')

        assert User.query.filter_by(oidc_subject='sub-1').first().is_admin

    def test_admin_removed_from_group_is_demoted(self, app, client, test_user):
        app.config['OIDC_ADMIN_GROUP'] = 'admins'
        test_user.is_admin = True
        test_user.oidc_subject = 'sub-1'
        db.session.commit()
        use_fake(app, id_claims=claims(groups=['users']))

        client.get('/auth/oidc/callback')

        db.session.refresh(test_user)
        assert not test_user.is_admin

    def test_admin_flag_untouched_without_admin_group(self, app, client, test_user):
        test_user.is_admin = True
        test_user.oidc_subject = 'sub-1'
        db.session.commit()
        use_fake(app, id_claims=claims(groups=[]))

        client.get('/auth/oidc/callback')

        db.session.refresh(test_user)
        assert test_user.is_admin


class TestOIDCRedirectAfterLogin:
    def test_next_page_is_honoured(self, app, client):
        use_fake(app, id_claims=claims())
        with client.session_transaction() as sess:
            sess['oidc_next'] = '/vehicles/'

        response = client.get('/auth/oidc/callback')

        assert response.headers['Location'].endswith('/vehicles/')

    def test_external_next_page_is_ignored(self, app, client):
        use_fake(app, id_claims=claims())
        with client.session_transaction() as sess:
            sess['oidc_next'] = 'https://evil.example.com/'

        response = client.get('/auth/oidc/callback')

        assert 'evil.example.com' not in response.headers['Location']
