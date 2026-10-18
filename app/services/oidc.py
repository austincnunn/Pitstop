"""OpenID Connect single sign-on (Authelia, Authentik, Keycloak, ...)."""
import re
import secrets
from authlib.integrations.flask_client import OAuth
from flask import current_app
from flask_babel import gettext as _
from sqlalchemy import func
from app import db
from app.models import User

USERNAME_MAX_LENGTH = 64


def init_oidc(app):
    """Register the OIDC client on the app when OIDC is enabled and configured."""
    app.jinja_env.globals['password_login_enabled'] = password_login_enabled
    if not app.config.get('OIDC_ENABLED'):
        return

    missing = [key for key in ('OIDC_DISCOVERY_URL', 'OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET')
               if not app.config.get(key)]
    if missing:
        app.logger.error('OIDC_ENABLED is set but %s is missing; SSO login is disabled', ', '.join(missing))
        return

    oauth = OAuth(app)
    oauth.register(
        name='oidc',
        client_id=app.config['OIDC_CLIENT_ID'],
        client_secret=app.config['OIDC_CLIENT_SECRET'],
        server_metadata_url=app.config['OIDC_DISCOVERY_URL'],
        client_kwargs={
            'scope': app.config.get('OIDC_SCOPES') or 'openid email profile',
            'code_challenge_method': 'S256',
        },
    )
    app.extensions['pitstop_oidc'] = oauth.oidc


def get_oidc_client():
    """The registered Authlib client, or None when SSO is off."""
    return current_app.extensions.get('pitstop_oidc')


def is_oidc_enabled():
    return get_oidc_client() is not None


def password_login_enabled():
    """False only when SSO works and OIDC_DISABLE_PASSWORD_LOGIN is set."""
    return not (is_oidc_enabled() and current_app.config.get('OIDC_DISABLE_PASSWORD_LOGIN'))


def _groups(claims):
    groups = claims.get('groups') or []
    if isinstance(groups, str):
        groups = [groups]
    return set(groups)


def _unique_username(claims, email):
    """Pick a free username from preferred_username, falling back to the email's local part."""
    base = claims.get('preferred_username') or email.split('@')[0]
    base = re.sub(r'[^A-Za-z0-9._-]', '', base)[:USERNAME_MAX_LENGTH] or 'user'

    candidate = base
    suffix = 1
    while User.query.filter_by(username=candidate).first():
        suffix += 1
        tail = str(suffix)
        candidate = f'{base[:USERNAME_MAX_LENGTH - len(tail)]}{tail}'
    return candidate


def resolve_user(claims):
    """Find, link or create the Pitstop user for a set of verified OIDC claims.

    Matching order:
      1. a user already linked to this `sub`
      2. an unlinked user with the same email, if the provider says it's verified
      3. a new account, if OIDC_AUTO_REGISTER is on

    Returns (user, None) on success or (None, error message) on failure.
    Commits on success.
    """
    subject = claims.get('sub')
    if not subject:
        return None, _('The identity provider did not return a user ID.')

    email = (claims.get('email') or '').strip()
    user = User.query.filter_by(oidc_subject=subject).first()

    if not user and email:
        existing = User.query.filter(func.lower(User.email) == email.lower()).first()
        if existing:
            if existing.oidc_subject:
                return None, _('This email is already linked to a different SSO account.')
            if claims.get('email_verified') is not True:
                return None, _('Your email is not verified with the identity provider, so it cannot be linked to an existing account.')
            existing.oidc_subject = subject
            user = existing

    if not user:
        if not current_app.config.get('OIDC_AUTO_REGISTER', True):
            return None, _('No Pitstop account matches your SSO login. Ask an administrator to create one.')
        if not email:
            return None, _('The identity provider did not return an email address.')
        user = User(username=_unique_username(claims, email), email=email, oidc_subject=subject)
        # SSO users never type this; it only satisfies the NOT NULL column
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)

    admin_group = current_app.config.get('OIDC_ADMIN_GROUP')
    if admin_group:
        user.is_admin = admin_group in _groups(claims)

    user.register_successful_login()
    db.session.commit()
    return user, None
