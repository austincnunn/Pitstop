from flask import Flask, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel, gettext as _
from config import Config
from app import units
import os
import secrets

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
babel = Babel()
csrf = CSRFProtect()

# Supported languages
LANGUAGES = {
    'en': 'English',
    'de': 'Deutsch',
    'es': 'Español',
    'fr': 'Français',
    'it': 'Italiano',
    'nl': 'Nederlands',
    'pt': 'Português',
    'pl': 'Polski',
    'sv': 'Svenska',
    'da': 'Dansk',
    'no': 'Norsk',
    'fi': 'Suomi',
    'ja': '日本語',
    'zh': '中文',
    'ko': '한국어'
}

DATE_FORMATS = {
    'DD/MM/YYYY': {
        'default': '%d/%m/%Y',
        'short': '%d %b',
        'long': '%d %B %Y',
        'datetime': '%d/%m/%Y %H:%M',
        'long_datetime': '%d %B %Y at %H:%M',
    },
    'MM/DD/YYYY': {
        'default': '%m/%d/%Y',
        'short': '%b %d',
        'long': '%B %d, %Y',
        'datetime': '%m/%d/%Y %H:%M',
        'long_datetime': '%B %d, %Y at %H:%M',
    },
    'YYYY-MM-DD': {
        'default': '%Y-%m-%d',
        'short': '%b %d',
        'long': '%Y-%m-%d',
        'datetime': '%Y-%m-%d %H:%M',
        'long_datetime': '%Y-%m-%d %H:%M',
    },
    'DD.MM.YYYY': {
        'default': '%d.%m.%Y',
        'short': '%d %b',
        'long': '%d %B %Y',
        'datetime': '%d.%m.%Y %H:%M',
        'long_datetime': '%d %B %Y at %H:%M',
    },
}


def _run_schema_migrations(app):
    """Add missing columns to existing tables.

    SQLite doesn't support adding columns via db.create_all() for existing tables,
    so we manually add any missing columns here.
    """
    from sqlalchemy import text, inspect

    # Define schema migrations: table -> [(column_name, column_type), ...]
    migrations = {
        'vehicles': [
            ('tessie_vin', 'VARCHAR(20)'),
            ('tessie_enabled', 'BOOLEAN DEFAULT FALSE'),
            ('tessie_last_odometer', 'FLOAT'),
            ('tessie_battery_level', 'INTEGER'),
            ('tessie_battery_range', 'FLOAT'),
            ('tessie_last_updated', 'TIMESTAMP'),
            ('tracking_unit', "VARCHAR(20) DEFAULT 'mileage'"),
            ('default_fuel_grade', 'VARCHAR(20)'),
            ('mileage_mode', "VARCHAR(10) DEFAULT 'odometer'"),
        ],
        'fuel_logs': [
            ('fuel_grade', "VARCHAR(20) DEFAULT 'regular'"),
            ('trip_reading', 'FLOAT'),
            ('distance_unknown', 'BOOLEAN DEFAULT FALSE'),
        ],
        'users': [
            ('date_format', "VARCHAR(20) DEFAULT 'DD/MM/YYYY'"),
            ('password_reset_token', 'VARCHAR(100)'),
            ('password_reset_expires', 'TIMESTAMP'),
            ('show_menu_supplies', 'BOOLEAN DEFAULT TRUE'),
            ('show_menu_notes', 'BOOLEAN DEFAULT TRUE'),
            ('show_menu_shopping', 'BOOLEAN DEFAULT TRUE'),
            ('failed_login_attempts', 'INTEGER DEFAULT 0'),
            ('locked_until', 'TIMESTAMP'),
            ('dashboard_widget_order', 'VARCHAR(255)'),
            ('show_widget_monthly_spending', 'BOOLEAN DEFAULT TRUE'),
            ('show_widget_cheapest_fuel', 'BOOLEAN DEFAULT TRUE'),
            ('show_widget_vehicles', 'BOOLEAN DEFAULT TRUE'),
            ('show_widget_recent_fuel', 'BOOLEAN DEFAULT TRUE'),
            ('show_widget_recent_expenses', 'BOOLEAN DEFAULT TRUE'),
            ('show_widget_fuel_costs_by_grade', 'BOOLEAN DEFAULT TRUE'),
            ('unit_system', "VARCHAR(20) DEFAULT 'imperial'"),
            ('oidc_subject', 'VARCHAR(255)'),
        ],
        'charging_sessions': [
            ('tessie_charge_id', 'VARCHAR(50)'),
        ],
        'attachments': [
            ('shopping_item_id', 'INTEGER'),
        ],
    }

    # Define unique indexes to create after adding columns
    # SQLite doesn't support adding UNIQUE columns directly via ALTER TABLE
    unique_indexes = [
        ('charging_sessions', 'tessie_charge_id', 'ix_charging_sessions_tessie_charge_id'),
        ('users', 'password_reset_token', 'ix_users_password_reset_token'),
        ('users', 'oidc_subject', 'ix_users_oidc_subject'),
    ]

    with db.engine.connect() as conn:
        inspector = inspect(db.engine)

        for table_name, columns in migrations.items():
            # Check if table exists
            if table_name not in inspector.get_table_names():
                continue

            # Get existing columns
            existing_cols = [col['name'] for col in inspector.get_columns(table_name)]

            # Add missing columns
            for col_name, col_type in columns:
                if col_name not in existing_cols:
                    try:
                        conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}'))
                        app.logger.info(f'Added column {col_name} to {table_name}')
                    except Exception as e:
                        app.logger.warning(f'Could not add column {col_name} to {table_name}: {e}')

        # Create unique indexes
        for table_name, col_name, index_name in unique_indexes:
            if table_name not in inspector.get_table_names():
                continue
            # Check if index already exists
            existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
            if index_name not in existing_indexes:
                try:
                    conn.execute(text(f'CREATE UNIQUE INDEX {index_name} ON {table_name} ({col_name})'))
                    app.logger.info(f'Created unique index {index_name} on {table_name}.{col_name}')
                except Exception as e:
                    app.logger.warning(f'Could not create index {index_name}: {e}')

        conn.commit()


def get_locale():
    """Select the best language for the user"""
    # If user is logged in and has a language preference, use it
    if current_user.is_authenticated and current_user.language:
        return current_user.language

    # Otherwise, try to match browser language
    return request.accept_languages.best_match(LANGUAGES.keys(), default='en')


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Babel configuration
    app.config['BABEL_DEFAULT_LOCALE'] = 'en'
    app.config['BABEL_SUPPORTED_LOCALES'] = list(LANGUAGES.keys())

    # Ensure data directories exist
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///') and ':memory:' not in db_uri:
        data_dir = os.path.dirname(db_uri.replace('sqlite:///', ''))
    else:
        data_dir = app.config['UPLOAD_FOLDER']
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'backups'), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    babel.init_app(app, locale_selector=get_locale)

    # Exempt API endpoints from CSRF (they use API key auth; api.bp still checks browser-session requests itself)
    from app.routes import api, homeassistant
    csrf.exempt(api.bp)
    csrf.exempt(homeassistant.bp)

    from app.models import User, AppSettings

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.services.oidc import init_oidc
    init_oidc(app)

    # Compiled by the Dockerfile; mtime busts browser caches on each new image
    tailwind_css = os.path.join(app.static_folder, 'css', 'tailwind.css')
    tailwind_css_url = (
        f"{app.static_url_path}/css/tailwind.css?v={int(os.path.getmtime(tailwind_css))}"
        if os.path.exists(tailwind_css) else None
    )

    # Make languages and branding available in templates
    @app.context_processor
    def inject_globals():
        branding = AppSettings.get_all_branding()
        update_latest = update_url = None
        if current_user and current_user.is_authenticated and current_user.is_admin:
            update_latest = AppSettings.get('update_latest')
            update_url = AppSettings.get('update_url')
        return {
            'UPDATE_LATEST': update_latest,
            'UPDATE_URL': update_url,
            'LANGUAGES': LANGUAGES,
            'APP_NAME': branding.get('app_name', 'Pitstop'),
            'APP_TAGLINE': branding.get('app_tagline', 'Maintenance Tracker'),
            'APP_LOGO': branding.get('logo_filename'),
            'PRIMARY_COLOR': branding.get('primary_color', '#0284c7'),
            'TAILWIND_CSS_URL': tailwind_css_url,
            'TAILWIND_ASSET_URL': app.config.get('TAILWIND_ASSET_URL', '/static/vendor/tailwindcss.js'),
            'TAILWIND_CDN_URL': app.config.get('TAILWIND_CDN_URL', 'https://cdn.tailwindcss.com'),
            'FLATPICKR_JS_ASSET_URL': app.config.get('FLATPICKR_JS_ASSET_URL', '/static/vendor/flatpickr.min.js'),
            'FLATPICKR_JS_CDN_URL': app.config.get('FLATPICKR_JS_CDN_URL', 'https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.js'),
            'FLATPICKR_CSS_ASSET_URL': app.config.get('FLATPICKR_CSS_ASSET_URL', '/static/vendor/flatpickr.min.css'),
            'FLATPICKR_CSS_CDN_URL': app.config.get('FLATPICKR_CSS_CDN_URL', 'https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.css'),
        }

    @app.template_filter('format_date')
    def format_date_filter(value, style='default'):
        if value is None:
            return ''
        user_format = 'DD/MM/YYYY'
        if current_user and current_user.is_authenticated:
            user_format = getattr(current_user, 'date_format', None) or 'DD/MM/YYYY'
        formats = DATE_FORMATS.get(user_format, DATE_FORMATS['DD/MM/YYYY'])
        fmt = formats.get(style, formats['default'])
        return value.strftime(fmt)

    @app.template_filter('format_distance')
    def format_distance_filter(value, user, unit=None):
        if value is None:
            return '-'
        unit = unit or user.distance_unit
        if user.unit_system == 'british' and unit == 'mi':
            return f"{units.miles_to_furlongs(value):,.1f} furlongs"
        return f"{value:,.1f} {unit}"

    @app.template_filter('format_volume')
    def format_volume_filter(value, user):
        if value is None:
            return '-'
        if user.unit_system == 'british':
            return f"{units.uk_gallons_to_firkins(value):,.2f} firkins"
        return f"{value:,.2f} {units.unit_label(user.volume_unit)}"

    @app.template_filter('format_consumption')
    def format_consumption_filter(value, user):
        if value is None:
            return '-'
        if user.unit_system == 'british':
            return f"{units.mpg_uk_to_rods_per_hogshead(value):,.0f} rods/hogshead"
        return f"{value:,.2f} {units.unit_label(user.consumption_unit)}"

    @app.template_filter('unit_label')
    def unit_label_filter(code):
        return units.unit_label(code)

    @app.template_filter('fuel_type_label')
    def fuel_type_label_filter(code):
        # Stored value 'petrol' displays as its translated label ("Gas" in English)
        from app.models import FUEL_TYPES
        return dict(FUEL_TYPES).get(code, (code or '').replace('_', ' ').title())

    from app.routes import main, auth, vehicles, fuel, expenses, api, reminders, maintenance, documents, stations, recurring, homeassistant, calendar, trips, charging, admin, supplies, notes, shopping
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(vehicles.bp)
    app.register_blueprint(fuel.bp)
    app.register_blueprint(expenses.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(reminders.bp)
    app.register_blueprint(maintenance.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(stations.bp)
    app.register_blueprint(recurring.bp)
    app.register_blueprint(homeassistant.bp)
    app.register_blueprint(calendar.bp)
    app.register_blueprint(trips.bp)
    app.register_blueprint(charging.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(supplies.bp)
    app.register_blueprint(notes.bp)
    app.register_blueprint(shopping.bp)

    # Health check endpoint for container orchestration
    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}, 200

    from urllib.parse import urlsplit
    cdns = ' '.join(sorted({
        '{0.scheme}://{0.netloc}'.format(urlsplit(app.config.get(key) or ''))
        for key in ('TAILWIND_CDN_URL', 'FLATPICKR_JS_CDN_URL', 'FLATPICKR_CSS_CDN_URL')
        if urlsplit(app.config.get(key) or '').netloc
    } | {'https://cdn.jsdelivr.net'}))
    csp = (
        "default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' {cdns}; "
        f"style-src 'self' 'unsafe-inline' {cdns} https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        # The service worker re-fetches CDN assets, and its fetches fall under connect-src
        f"connect-src 'self' {cdns} https://fonts.googleapis.com https://fonts.gstatic.com; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
    )

    # Security headers
    @app.after_request
    def add_security_headers(response):
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Enable XSS filter in browsers
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Permissions policy (formerly feature policy)
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        # Content Security Policy: scripts/styles only from here and the CDNs we use; no third-party
        # images, connections, plugins or framing. Inline scripts stay allowed because templates use them.
        response.headers['Content-Security-Policy'] = csp
        return response

    with app.app_context():
        db.create_all()
        # Run schema migrations for new columns on existing tables
        _run_schema_migrations(app)
        # Create default admin user if no users exist
        if User.query.count() == 0:
            admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
            admin_password = os.environ.get('ADMIN_PASSWORD')

            if not admin_password:
                # Generate a secure random password
                admin_password = secrets.token_urlsafe(16)
                print("=" * 60)
                print("SECURITY NOTICE: Default admin account created")
                print(f"Username: {admin_username}")
                print(f"Password: {admin_password}")
                print("Please change this password immediately after first login!")
                print("Set ADMIN_PASSWORD environment variable to avoid this message.")
                print("=" * 60)

            admin = User(username=admin_username, email=admin_email, is_admin=True)
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()

    # Start background schedulers (only in the main process, not reloader)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        _start_reminder_scheduler(app)
        _start_backup_scheduler(app)
        _start_actual_sync_scheduler(app)
        if app.config.get('UPDATE_CHECK_ENABLED'):
            _start_update_check_scheduler(app)

    return app


def _start_reminder_scheduler(app):
    """Start a background thread that processes reminders daily."""
    import threading
    import time
    import logging

    logger = logging.getLogger(__name__)

    def reminder_loop():
        """Check reminders every hour."""
        # Wait 60 seconds after startup before first check
        time.sleep(60)

        while True:
            try:
                with app.app_context():
                    from app.services.reminder_processor import process_due_reminders
                    stats = process_due_reminders()
                    if stats['sent'] > 0 or stats['failed'] > 0:
                        logger.info(
                            f"Reminder check: {stats['sent']} sent, "
                            f"{stats['failed']} failed, {stats['skipped']} skipped"
                        )
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}")

            # Check every hour
            time.sleep(3600)

    thread = threading.Thread(target=reminder_loop, daemon=True, name='reminder-scheduler')
    thread.start()
    app.logger.info("Started background reminder scheduler (hourly checks)")


def _start_backup_scheduler(app):
    """Start a background thread that creates automated backups on schedule."""
    import threading
    import time
    import logging

    logger = logging.getLogger(__name__)

    def backup_loop():
        """Check every hour whether a scheduled backup (disk and/or email) is due."""
        time.sleep(90)  # short initial delay so DB is fully ready

        while True:
            try:
                with app.app_context():
                    from app.services.backup_service import run_scheduled_backup_tick
                    run_scheduled_backup_tick(app)
            except Exception as e:
                logger.error('Error in backup scheduler: %s', e)

            time.sleep(3600)

    thread = threading.Thread(target=backup_loop, daemon=True, name='backup-scheduler')
    thread.start()
    app.logger.info("Started background backup scheduler (hourly checks)")


def _start_actual_sync_scheduler(app):
    """Start a background thread that imports Actual Budget expenses daily (when enabled)."""
    import threading
    import time
    import logging

    logger = logging.getLogger(__name__)

    def actual_sync_loop():
        time.sleep(120)

        while True:
            try:
                with app.app_context():
                    from app.services.actual_budget import run_scheduled_actual_sync_tick
                    run_scheduled_actual_sync_tick(app)
            except Exception as e:
                logger.error('Error in Actual Budget sync scheduler: %s', e)

            time.sleep(3600)

    thread = threading.Thread(target=actual_sync_loop, daemon=True, name='actual-sync-scheduler')
    thread.start()
    app.logger.info("Started background Actual Budget sync scheduler (hourly checks)")


def _start_update_check_scheduler(app):
    """Start a background thread that checks GitHub for a newer version every 6 hours."""
    import threading
    import time
    import logging

    logger = logging.getLogger(__name__)

    def update_check_loop():
        time.sleep(30)

        while True:
            try:
                with app.app_context():
                    from app.services.update_check import run_update_check_tick
                    run_update_check_tick()
            except Exception as e:
                logger.error('Error in update check scheduler: %s', e)

            # Each worker runs its own loop; 6h keeps well under GitHub's 60 unauthenticated requests/hour
            time.sleep(6 * 3600)

    thread = threading.Thread(target=update_check_loop, daemon=True, name='update-check-scheduler')
    thread.start()
    app.logger.info("Started background update check scheduler (6-hourly checks)")
