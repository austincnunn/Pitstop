import os
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, abort
from flask_login import login_required, current_user
from app import db
from app.models import AppSettings
from app.services.backup_service import (
    get_backup_dir, create_backup_file, list_backups, cleanup_old_backups,
    clamp_email_interval, get_primary_admin, send_backup_email_now,
    BACKUP_EMAIL_MIN_DAYS, BACKUP_EMAIL_MAX_DAYS,
)

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__, url_prefix='/admin')


def _require_admin():
    if not current_user.is_admin:
        abort(403)


# ---------------------------------------------------------------------------
# Backup management
# ---------------------------------------------------------------------------

@bp.route('/backups')
@login_required
def backups():
    _require_admin()
    from flask import current_app
    backup_dir = get_backup_dir(current_app)
    existing = list_backups(backup_dir)

    settings = {
        'backup_enabled': AppSettings.get('backup_enabled', 'false') == 'true',
        'backup_frequency': AppSettings.get('backup_frequency', 'daily'),
        'backup_hour': int(AppSettings.get('backup_hour', '2')),
        'backup_retention': int(AppSettings.get('backup_retention', '7')),
        'backup_email_enabled': AppSettings.get('backup_email_enabled', 'false') == 'true',
        'backup_email_interval_days': clamp_email_interval(AppSettings.get('backup_email_interval_days', '7')),
        'backup_email_last_sent': AppSettings.get('backup_email_last_sent', ''),
    }
    primary = get_primary_admin()

    return render_template('admin/backups.html', backups=existing, settings=settings,
                           backup_dir=backup_dir,
                           primary_admin=primary,
                           smtp_configured=bool(AppSettings.get('smtp_host') and AppSettings.get('smtp_username')),
                           email_min_days=BACKUP_EMAIL_MIN_DAYS, email_max_days=BACKUP_EMAIL_MAX_DAYS)


@bp.route('/backups/settings', methods=['POST'])
@login_required
def save_backup_settings():
    _require_admin()

    enabled = request.form.get('backup_enabled') == 'on'
    frequency = request.form.get('backup_frequency', 'daily')
    hour = request.form.get('backup_hour', '2')
    retention = request.form.get('backup_retention', '7')

    if frequency not in ('daily', 'weekly', 'monthly'):
        frequency = 'daily'
    try:
        hour = max(0, min(23, int(hour)))
    except ValueError:
        hour = 2
    try:
        retention = max(1, min(365, int(retention)))
    except ValueError:
        retention = 7

    AppSettings.set('backup_enabled', 'true' if enabled else 'false')
    AppSettings.set('backup_frequency', frequency)
    AppSettings.set('backup_hour', str(hour))
    AppSettings.set('backup_retention', str(retention))

    AppSettings.set('backup_email_enabled',
                    'true' if request.form.get('backup_email_enabled') == 'on' else 'false')
    AppSettings.set('backup_email_interval_days',
                    str(clamp_email_interval(request.form.get('backup_email_interval_days'))))

    flash('Backup settings saved.', 'success')
    return redirect(url_for('admin.backups'))


@bp.route('/backups/run', methods=['POST'])
@login_required
def run_backup_now():
    _require_admin()
    from flask import current_app
    backup_dir = get_backup_dir(current_app)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    retention = int(AppSettings.get('backup_retention', '7'))

    try:
        fname = create_backup_file(current_user, upload_folder, backup_dir, include_db_dump=True)
        cleanup_old_backups(backup_dir, retention)
        flash(f'Backup created: {fname}', 'success')
    except Exception as e:
        logger.error('Manual backup failed: %s', e)
        flash(f'Backup failed: {e}', 'error')

    return redirect(url_for('admin.backups'))


@bp.route('/backups/email-now', methods=['POST'])
@login_required
def email_backup_now():
    _require_admin()
    from flask import current_app
    ok, error = send_backup_email_now(current_app._get_current_object())
    if ok:
        flash('Backup emailed to the primary admin.', 'success')
    else:
        flash(f'Backup email failed: {error}', 'error')
    return redirect(url_for('admin.backups'))


@bp.route('/backups/download/<path:filename>')
@login_required
def download_backup(filename):
    _require_admin()
    from flask import current_app
    backup_dir = get_backup_dir(current_app)
    # Prevent path traversal
    safe_name = os.path.basename(filename)
    file_path = os.path.join(backup_dir, safe_name)
    if not os.path.exists(file_path):
        abort(404)
    return send_from_directory(backup_dir, safe_name, as_attachment=True)


@bp.route('/backups/delete/<path:filename>', methods=['POST'])
@login_required
def delete_backup(filename):
    _require_admin()
    from flask import current_app
    backup_dir = get_backup_dir(current_app)
    safe_name = os.path.basename(filename)
    file_path = os.path.join(backup_dir, safe_name)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f'Backup deleted: {safe_name}', 'success')
    else:
        flash('Backup file not found.', 'error')
    return redirect(url_for('admin.backups'))
