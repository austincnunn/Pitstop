import os
from pathlib import Path

basedir = Path(__file__).parent.absolute()


APP_VERSION = '0.15.0'
RELEASE_CHANNEL = os.environ.get('RELEASE_CHANNEL', 'stable')
GIT_SHA = os.environ.get('GIT_SHA', '')[:7]  # Short SHA
GITHUB_REPO = 'austincnunn/Pitstop'
TAILWIND_ASSET_URL = os.environ.get('TAILWIND_ASSET_URL', '/static/vendor/tailwindcss.js')
TAILWIND_CDN_URL = os.environ.get('TAILWIND_CDN_URL', 'https://cdn.tailwindcss.com')
FLATPICKR_JS_ASSET_URL = os.environ.get('FLATPICKR_JS_ASSET_URL', '/static/vendor/flatpickr.min.js')
FLATPICKR_JS_CDN_URL = os.environ.get('FLATPICKR_JS_CDN_URL', 'https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.js')
FLATPICKR_CSS_ASSET_URL = os.environ.get('FLATPICKR_CSS_ASSET_URL', '/static/vendor/flatpickr.min.css')
FLATPICKR_CSS_CDN_URL = os.environ.get('FLATPICKR_CSS_CDN_URL', 'https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.css')

# Build display version (e.g., "0.5.0" for stable, "0.5.0-dev+abc1234" for dev)
if RELEASE_CHANNEL == 'dev' and GIT_SHA:
    DISPLAY_VERSION = f"{APP_VERSION}-dev+{GIT_SHA}"
elif RELEASE_CHANNEL == 'dev':
    DISPLAY_VERSION = f"{APP_VERSION}-dev"
else:
    DISPLAY_VERSION = APP_VERSION


class Config:
    APP_VERSION = APP_VERSION
    DISPLAY_VERSION = DISPLAY_VERSION
    RELEASE_CHANNEL = RELEASE_CHANNEL
    GIT_SHA = GIT_SHA
    GITHUB_REPO = GITHUB_REPO
    TAILWIND_ASSET_URL = TAILWIND_ASSET_URL
    TAILWIND_CDN_URL = TAILWIND_CDN_URL
    FLATPICKR_JS_ASSET_URL = FLATPICKR_JS_ASSET_URL
    FLATPICKR_JS_CDN_URL = FLATPICKR_JS_CDN_URL
    FLATPICKR_CSS_ASSET_URL = FLATPICKR_CSS_ASSET_URL
    FLATPICKR_CSS_CDN_URL = FLATPICKR_CSS_CDN_URL
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        import secrets
        # Generate a random key for development, but warn about it
        SECRET_KEY = secrets.token_hex(32)
        import warnings
        warnings.warn(
            "SECRET_KEY environment variable not set. Using randomly generated key. "
            "Sessions will not persist across restarts. Set SECRET_KEY for production.",
            RuntimeWarning
        )
    INTERNAL_API_KEY = os.environ.get('INTERNAL_API_KEY') or __import__('secrets').token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{basedir}/data/pitstop.db'
    # Recycle dead connections (e.g. after a DB restart) instead of erroring on them
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or str(basedir / 'data' / 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Set SESSION_COOKIE_SECURE=true if served over HTTPS (e.g. behind a TLS-terminating reverse proxy)
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

    # OpenID Connect single sign-on (e.g. Authelia, Authentik, Keycloak)
    OIDC_ENABLED = os.environ.get('OIDC_ENABLED', 'false').lower() == 'true'
    OIDC_DISCOVERY_URL = os.environ.get('OIDC_DISCOVERY_URL')  # https://auth.example.com/.well-known/openid-configuration
    OIDC_CLIENT_ID = os.environ.get('OIDC_CLIENT_ID')
    OIDC_CLIENT_SECRET = os.environ.get('OIDC_CLIENT_SECRET')
    OIDC_SCOPES = os.environ.get('OIDC_SCOPES', 'openid email profile groups')
    OIDC_PROVIDER_NAME = os.environ.get('OIDC_PROVIDER_NAME', 'SSO')  # Button reads "Sign in with <name>"
    # Overrides the whole button label, e.g. "Log in"
    OIDC_BUTTON_TEXT = os.environ.get('OIDC_BUTTON_TEXT')
    # Absolute callback URL; only needed if Pitstop builds the wrong one behind a proxy
    OIDC_REDIRECT_URI = os.environ.get('OIDC_REDIRECT_URI')
    # Create a Pitstop account on first SSO login when no existing account matches
    OIDC_AUTO_REGISTER = os.environ.get('OIDC_AUTO_REGISTER', 'true').lower() == 'true'
    # If set, members of this group are Pitstop admins and everyone else is not (synced on every SSO login)
    OIDC_ADMIN_GROUP = os.environ.get('OIDC_ADMIN_GROUP')
    # Make SSO the only way in: hides the password form, register and password reset.
    # Ignored (password login stays on) if SSO isn't fully configured, so you can't lock yourself out.
    OIDC_DISABLE_PASSWORD_LOGIN = os.environ.get('OIDC_DISABLE_PASSWORD_LOGIN', 'false').lower() == 'true'
    # Send /auth/login straight to the provider; /auth/login?local=1 shows the page instead
    OIDC_AUTO_REDIRECT = os.environ.get('OIDC_AUTO_REDIRECT', 'false').lower() == 'true'
