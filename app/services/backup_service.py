"""
Backup service: create, list, and manage automated backup files on disk.
Backups use the same ZIP format as the manual Full Backup export.
"""
import hashlib
import io
import json
import logging
import os
import sqlite3
import subprocess
import tempfile
import zipfile
from datetime import datetime, timedelta
from urllib.parse import urlsplit, unquote

logger = logging.getLogger(__name__)

# Most mail servers reject attachments much over 20-25 MB.
BACKUP_EMAIL_MAX_BYTES = 20 * 1024 * 1024
BACKUP_EMAIL_MIN_DAYS = 7
BACKUP_EMAIL_MAX_DAYS = 180


def get_backup_dir(app):
    """Return the backup directory path (creates it if missing)."""
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///') and ':memory:' not in db_uri:
        db_path = db_uri.replace('sqlite:///', '')
        data_dir = os.path.dirname(db_path)
    else:
        data_dir = app.config['UPLOAD_FOLDER']
    backup_dir = os.path.join(data_dir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def create_backup_file(user, upload_folder, backup_dir, include_db_dump=False):
    """
    Create a full backup ZIP for *user* and save it to *backup_dir*.
    Returns the filename of the created backup.

    include_db_dump: also embed a full database dump (database.dump for
    Postgres, database.sqlite for SQLite). The dump contains every user's
    data plus password hashes and API keys, so only admin-level backups
    should pass True.
    """
    from config import APP_VERSION

    export_data = {
        'export_info': {
            'exported_at': datetime.utcnow().isoformat(),
            'username': user.username,
            'app_version': APP_VERSION,
            'backup_type': 'full'
        },
        'user_preferences': {
            'language': user.language,
            'distance_unit': user.distance_unit,
            'volume_unit': user.volume_unit,
            'consumption_unit': user.consumption_unit,
            'currency': user.currency
        },
        'vehicles': [],
        'fuel_stations': [],
        'fuel_price_history': []
    }

    files_to_backup = []  # [(filename, file_type, record_type, record_id)]

    for vehicle in user.get_all_vehicles():
        vehicle_data = _serialize_vehicle(vehicle, files_to_backup)
        export_data['vehicles'].append(vehicle_data)

    for station in user.fuel_stations.all():
        export_data['fuel_stations'].append(_serialize_station(station))
        for price in station.price_history.all():
            export_data['fuel_price_history'].append({
                'id': price.id,
                'station_id': station.id,
                'station_name': station.name,
                'date': price.date.isoformat() if price.date else None,
                'fuel_type': price.fuel_type,
                'price_per_unit': price.price_per_unit,
                'created_at': price.created_at.isoformat() if price.created_at else None
            })

    manifest = {
        'version': APP_VERSION,
        'created_at': datetime.utcnow().isoformat(),
        'username': user.username,
        'files': []
    }

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        seen_files = set()
        for filename, file_type, record_type, record_id in files_to_backup:
            if not filename or filename in seen_files:
                continue
            seen_files.add(filename)
            file_path = os.path.join(upload_folder, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    file_hash = hashlib.sha256(file_data).hexdigest()
                    zf.writestr(f'uploads/{filename}', file_data)
                    manifest['files'].append({
                        'filename': filename,
                        'type': record_type,
                        'record_id': record_id,
                        'file_type': file_type,
                        'size': len(file_data),
                        'sha256': file_hash
                    })
                except (IOError, OSError):
                    pass

        export_data['files_manifest'] = {
            'total_files': len(manifest['files']),
            'files': manifest['files']
        }

        if include_db_dump:
            dump = create_db_dump()
            if dump:
                dump_name, dump_bytes = dump
                zf.writestr(dump_name, dump_bytes)
                manifest['database_dump'] = {
                    'filename': dump_name,
                    'size': len(dump_bytes),
                    'sha256': hashlib.sha256(dump_bytes).hexdigest(),
                }

        zf.writestr('data.json', json.dumps(export_data, indent=2))
        zf.writestr('manifest.json', json.dumps(manifest, indent=2))

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f'pitstop_backup_{user.username}_{timestamp}.zip'
    fpath = os.path.join(backup_dir, fname)

    with open(fpath, 'wb') as f:
        f.write(zip_buffer.getvalue())

    logger.info('Automated backup created: %s', fpath)
    return fname


def list_backups(backup_dir):
    """Return a list of backup dicts sorted newest-first."""
    if not os.path.exists(backup_dir):
        return []
    backups = []
    for fname in os.listdir(backup_dir):
        if fname.endswith('.zip'):
            fpath = os.path.join(backup_dir, fname)
            stat = os.stat(fpath)
            backups.append({
                'filename': fname,
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_mtime)
            })
    backups.sort(key=lambda x: x['created_at'], reverse=True)
    return backups


def cleanup_old_backups(backup_dir, retention_count):
    """Delete backups beyond *retention_count* (oldest first). Returns count deleted."""
    backups = list_backups(backup_dir)
    to_delete = backups[retention_count:]
    deleted = 0
    for backup in to_delete:
        try:
            os.remove(os.path.join(backup_dir, backup['filename']))
            deleted += 1
            logger.info('Deleted old backup: %s', backup['filename'])
        except OSError as e:
            logger.warning('Could not delete backup %s: %s', backup['filename'], e)
    return deleted


# ---------------------------------------------------------------------------
# Serialisation helpers (mirror the logic in api.py export_full_backup)
# ---------------------------------------------------------------------------

def _serialize_vehicle(vehicle, files_to_backup):
    vd = {
        'id': vehicle.id,
        'name': vehicle.name,
        'vehicle_type': vehicle.vehicle_type,
        'make': vehicle.make,
        'model': vehicle.model,
        'year': vehicle.year,
        'registration': vehicle.registration,
        'vin': vehicle.vin,
        'fuel_type': vehicle.fuel_type,
        'mileage_mode': vehicle.mileage_mode,
        'tank_capacity': vehicle.tank_capacity,
        'battery_capacity': vehicle.battery_capacity,
        'is_active': vehicle.is_active,
        'notes': vehicle.notes,
        'image_filename': vehicle.image_filename,
        'mot_status': vehicle.mot_status,
        'mot_expiry': vehicle.mot_expiry.isoformat() if vehicle.mot_expiry else None,
        'tax_status': vehicle.tax_status,
        'tax_due': vehicle.tax_due.isoformat() if vehicle.tax_due else None,
        'created_at': vehicle.created_at.isoformat() if vehicle.created_at else None,
        'specifications': [],
        'fuel_logs': [],
        'expenses': [],
        'reminders': [],
        'maintenance_schedules': [],
        'recurring_expenses': [],
        'documents': [],
        'trips': [],
        'charging_sessions': [],
        'parts': [],
        'attachments': [],
        'vehicle_notes': []
    }

    if vehicle.image_filename:
        files_to_backup.append((vehicle.image_filename, 'image', 'vehicle', vehicle.id))

    for att in vehicle.attachments.all():
        vd['attachments'].append({
            'id': att.id, 'filename': att.filename,
            'original_filename': att.original_filename, 'file_type': att.file_type,
            'file_size': att.file_size, 'description': att.description,
            'created_at': att.created_at.isoformat() if att.created_at else None
        })
        files_to_backup.append((att.filename, att.file_type, 'vehicle_attachment', att.id))

    for spec in vehicle.specs.all():
        vd['specifications'].append({
            'id': spec.id, 'spec_type': spec.spec_type, 'label': spec.label,
            'value': spec.value,
            'created_at': spec.created_at.isoformat() if spec.created_at else None
        })

    from app.models import FuelLog
    for log in vehicle.fuel_logs.order_by(FuelLog.date.desc()).all():
        ld = {
            'id': log.id,
            'date': log.date.isoformat() if log.date else None,
            'odometer': log.odometer, 'trip_reading': log.trip_reading, 'volume': log.volume,
            'price_per_unit': log.price_per_unit, 'total_cost': log.total_cost,
            'is_full_tank': log.is_full_tank, 'is_missed': log.is_missed,
            'station': log.station, 'notes': log.notes,
            'created_at': log.created_at.isoformat() if log.created_at else None,
            'attachments': []
        }
        for att in log.attachments.all():
            ld['attachments'].append({
                'id': att.id, 'filename': att.filename,
                'original_filename': att.original_filename, 'file_type': att.file_type,
                'file_size': att.file_size, 'description': att.description,
                'created_at': att.created_at.isoformat() if att.created_at else None
            })
            files_to_backup.append((att.filename, att.file_type, 'fuel_log_attachment', att.id))
        vd['fuel_logs'].append(ld)

    from app.models import Expense
    for exp in vehicle.expenses.order_by(Expense.date.desc()).all():
        ed = {
            'id': exp.id,
            'date': exp.date.isoformat() if exp.date else None,
            'category': exp.category, 'description': exp.description,
            'cost': exp.cost, 'odometer': exp.odometer, 'vendor': exp.vendor,
            'notes': exp.notes,
            'created_at': exp.created_at.isoformat() if exp.created_at else None,
            'attachments': []
        }
        for att in exp.attachments.all():
            ed['attachments'].append({
                'id': att.id, 'filename': att.filename,
                'original_filename': att.original_filename, 'file_type': att.file_type,
                'file_size': att.file_size, 'description': att.description,
                'created_at': att.created_at.isoformat() if att.created_at else None
            })
            files_to_backup.append((att.filename, att.file_type, 'expense_attachment', att.id))
        vd['expenses'].append(ed)

    for rem in vehicle.reminders.all():
        vd['reminders'].append({
            'id': rem.id, 'title': rem.title, 'description': rem.description,
            'reminder_type': rem.reminder_type,
            'due_date': rem.due_date.isoformat() if rem.due_date else None,
            'recurrence': rem.recurrence, 'recurrence_interval': rem.recurrence_interval,
            'notify_days_before': rem.notify_days_before,
            'notification_sent': rem.notification_sent,
            'is_completed': rem.is_completed,
            'completed_at': rem.completed_at.isoformat() if rem.completed_at else None,
            'created_at': rem.created_at.isoformat() if rem.created_at else None
        })

    for sched in vehicle.maintenance_schedules.all():
        vd['maintenance_schedules'].append({
            'id': sched.id, 'name': sched.name, 'maintenance_type': sched.maintenance_type,
            'description': sched.description,
            'interval_miles': sched.interval_miles, 'interval_km': sched.interval_km,
            'interval_months': sched.interval_months,
            'last_performed_date': sched.last_performed_date.isoformat() if sched.last_performed_date else None,
            'last_performed_odometer': sched.last_performed_odometer,
            'next_due_date': sched.next_due_date.isoformat() if sched.next_due_date else None,
            'next_due_odometer': sched.next_due_odometer,
            'estimated_cost': sched.estimated_cost, 'auto_remind': sched.auto_remind,
            'remind_days_before': sched.remind_days_before,
            'remind_miles_before': sched.remind_miles_before,
            'is_active': sched.is_active,
            'created_at': sched.created_at.isoformat() if sched.created_at else None
        })

    for rec in vehicle.recurring_expenses.all():
        vd['recurring_expenses'].append({
            'id': rec.id, 'name': rec.name, 'category': rec.category,
            'description': rec.description, 'amount': rec.amount, 'vendor': rec.vendor,
            'frequency': rec.frequency,
            'start_date': rec.start_date.isoformat() if rec.start_date else None,
            'end_date': rec.end_date.isoformat() if rec.end_date else None,
            'last_generated': rec.last_generated.isoformat() if rec.last_generated else None,
            'next_due': rec.next_due.isoformat() if rec.next_due else None,
            'auto_create': rec.auto_create, 'notify_before_days': rec.notify_before_days,
            'is_active': rec.is_active,
            'created_at': rec.created_at.isoformat() if rec.created_at else None
        })

    for doc in vehicle.documents.all():
        vd['documents'].append({
            'id': doc.id, 'title': doc.title, 'document_type': doc.document_type,
            'description': doc.description, 'filename': doc.filename,
            'original_filename': doc.original_filename, 'file_type': doc.file_type,
            'file_size': doc.file_size,
            'issue_date': doc.issue_date.isoformat() if doc.issue_date else None,
            'expiry_date': doc.expiry_date.isoformat() if doc.expiry_date else None,
            'reference_number': doc.reference_number,
            'remind_before_expiry': doc.remind_before_expiry,
            'remind_days': doc.remind_days,
            'created_at': doc.created_at.isoformat() if doc.created_at else None
        })
        files_to_backup.append((doc.filename, doc.file_type, 'document', doc.id))

    from app.models import Trip
    for trip in vehicle.trips.order_by(Trip.date.desc()).all():
        vd['trips'].append({
            'id': trip.id,
            'date': trip.date.isoformat() if trip.date else None,
            'start_odometer': trip.start_odometer, 'end_odometer': trip.end_odometer,
            'distance': trip.distance, 'purpose': trip.purpose,
            'description': trip.description, 'start_location': trip.start_location,
            'end_location': trip.end_location, 'notes': trip.notes,
            'created_at': trip.created_at.isoformat() if trip.created_at else None
        })

    from app.models import ChargingSession
    for cs in vehicle.charging_sessions.order_by(ChargingSession.date.desc()).all():
        vd['charging_sessions'].append({
            'id': cs.id,
            'date': cs.date.isoformat() if cs.date else None,
            'start_time': cs.start_time.isoformat() if cs.start_time else None,
            'end_time': cs.end_time.isoformat() if cs.end_time else None,
            'odometer': cs.odometer, 'kwh_added': cs.kwh_added,
            'start_soc': cs.start_soc, 'end_soc': cs.end_soc,
            'cost_per_kwh': cs.cost_per_kwh, 'total_cost': cs.total_cost,
            'charger_type': cs.charger_type, 'location': cs.location,
            'network': cs.network, 'notes': cs.notes,
            'created_at': cs.created_at.isoformat() if cs.created_at else None
        })

    for part in vehicle.parts.all():
        vd['parts'].append({
            'id': part.id, 'name': part.name, 'part_type': part.part_type,
            'specification': part.specification, 'quantity': part.quantity,
            'unit': part.unit, 'part_number': part.part_number,
            'supplier_url': part.supplier_url, 'notes': part.notes,
            'created_at': part.created_at.isoformat() if part.created_at else None,
            'updated_at': part.updated_at.isoformat() if part.updated_at else None
        })

    from app.models import VehicleNote
    for note in vehicle.vehicle_notes.order_by(VehicleNote.created_at.asc()).all():
        vd['vehicle_notes'].append({
            'id': note.id, 'title': note.title, 'content': note.content,
            'is_pinned': note.is_pinned,
            'created_at': note.created_at.isoformat() if note.created_at else None,
            'updated_at': note.updated_at.isoformat() if note.updated_at else None,
        })

    return vd


def _serialize_station(station):
    return {
        'id': station.id, 'name': station.name, 'brand': station.brand,
        'address': station.address, 'city': station.city, 'postcode': station.postcode,
        'latitude': station.latitude, 'longitude': station.longitude,
        'notes': station.notes, 'is_favorite': station.is_favorite,
        'times_used': station.times_used,
        'last_used': station.last_used.isoformat() if station.last_used else None,
        'created_at': station.created_at.isoformat() if station.created_at else None
    }


# ---------------------------------------------------------------------------
# Database dump
# ---------------------------------------------------------------------------

def _parse_postgres_url(uri):
    """Split a SQLAlchemy Postgres URL into pg_dump connection parts."""
    parts = urlsplit(uri.replace('postgresql+psycopg2://', 'postgresql://')
                        .replace('postgresql+psycopg://', 'postgresql://'))
    return {
        'host': parts.hostname or 'localhost',
        'port': str(parts.port or 5432),
        'user': unquote(parts.username) if parts.username else None,
        'password': unquote(parts.password) if parts.password else None,
        'dbname': parts.path.lstrip('/'),
    }


def create_db_dump():
    """
    Dump the whole database. Returns (filename, bytes) or None on failure
    (logged, never raised -- a failed dump must not abort the backup).
    """
    from flask import current_app
    uri = current_app.config['SQLALCHEMY_DATABASE_URI']

    try:
        if uri.startswith('postgresql'):
            conn = _parse_postgres_url(uri)
            cmd = ['pg_dump', '-Fc', '--no-owner', '-h', conn['host'], '-p', conn['port']]
            if conn['user']:
                cmd += ['-U', conn['user']]
            cmd.append(conn['dbname'])
            env = dict(os.environ)
            if conn['password']:
                env['PGPASSWORD'] = conn['password']
            result = subprocess.run(cmd, env=env, capture_output=True, timeout=300)
            if result.returncode != 0:
                logger.error('pg_dump failed: %s', result.stderr.decode('utf-8', 'replace').strip())
                return None
            return 'database.dump', result.stdout

        if uri.startswith('sqlite:///') and ':memory:' not in uri:
            db_path = uri.replace('sqlite:///', '')
            fd, tmp_path = tempfile.mkstemp(suffix='.sqlite')
            os.close(fd)
            try:
                src = sqlite3.connect(db_path)
                dst = sqlite3.connect(tmp_path)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
                    src.close()
                with open(tmp_path, 'rb') as f:
                    return 'database.sqlite', f.read()
            finally:
                os.remove(tmp_path)
    except (OSError, subprocess.SubprocessError, sqlite3.Error) as e:
        logger.error('Database dump failed: %s', e)
    return None


# ---------------------------------------------------------------------------
# Emailed backups
# ---------------------------------------------------------------------------

def clamp_email_interval(value):
    """Parse the email interval (days), clamped to the allowed range."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = BACKUP_EMAIL_MIN_DAYS
    return max(BACKUP_EMAIL_MIN_DAYS, min(BACKUP_EMAIL_MAX_DAYS, days))


def backup_email_due(now, last_sent, interval_days):
    """True if a backup email is due: never sent, unparseable, or interval elapsed."""
    if not last_sent:
        return True
    try:
        last = datetime.fromisoformat(last_sent)
    except ValueError:
        return True
    return now - last >= timedelta(days=interval_days)


def get_primary_admin():
    """The primary admin is the admin account with the lowest id."""
    from app.models import User
    return User.query.filter_by(is_admin=True).order_by(User.id).first()


def build_email_attachment(zip_path, max_bytes=BACKUP_EMAIL_MAX_BYTES):
    """
    Pick what to attach so the email stays under max_bytes. Tiers:
      1. the full backup ZIP
      2. ZIP without uploaded files (data.json + manifest + database dump)
      3. the database dump alone
      4. data.json alone
    Returns (filename, bytes, description) or None if nothing fits.
    """
    with open(zip_path, 'rb') as f:
        full = f.read()
    name = os.path.basename(zip_path)
    if len(full) <= max_bytes:
        return name, full, 'the full backup (data, uploaded files and database dump)'

    with zipfile.ZipFile(io.BytesIO(full)) as zin:
        names = zin.namelist()
        slim = io.BytesIO()
        with zipfile.ZipFile(slim, 'w', zipfile.ZIP_DEFLATED) as zout:
            for n in names:
                if not n.startswith('uploads/'):
                    zout.writestr(n, zin.read(n))
        slim_bytes = slim.getvalue()
        if len(slim_bytes) <= max_bytes:
            return (name.replace('.zip', '_no_uploads.zip'), slim_bytes,
                    'a reduced backup WITHOUT uploaded files (too large to email)')

        for dump_name in ('database.dump', 'database.sqlite'):
            if dump_name in names:
                data = zin.read(dump_name)
                if len(data) <= max_bytes:
                    return (dump_name, data,
                            'the database dump only (backup too large to email; '
                            'the full backup is on the server)')

        if 'data.json' in names:
            data = zin.read('data.json')
            if len(data) <= max_bytes:
                return ('data.json', data,
                        'the app data (data.json) only (backup too large to email; '
                        'the full backup is on the server)')
    return None


def email_backup(zip_path, recipient, max_bytes=BACKUP_EMAIL_MAX_BYTES):
    """Email a backup ZIP (with size fallback) to recipient. Returns (ok, error)."""
    from app.services.notifications import NotificationService

    chosen = build_email_attachment(zip_path, max_bytes)
    if not chosen:
        return False, 'Backup is too large to email'
    filename, data, description = chosen

    with zipfile.ZipFile(zip_path) as zf:
        entries = zf.namelist()
    has_dump = any(n in entries for n in ('database.dump', 'database.sqlite'))
    note = '' if has_dump else (
        '\n\nNote: no database dump is included (pg_dump was unavailable or failed; '
        'see the server logs).')
    body = (
        f'Attached is {description}.\n\n'
        'This file contains your data, and the database dump (if present) also '
        'contains password hashes and API keys. Store it somewhere private.'
        f'{note}'
    )
    return NotificationService.send_email(
        recipient,
        f'Pitstop backup {datetime.utcnow().strftime("%Y-%m-%d")}',
        body,
        attachments=[(filename, data)],
    )


def send_backup_email_now(app, primary=None):
    """
    Create a fresh backup for the primary admin, email it, and record the
    send time. Returns (ok, error_message).
    """
    from app.models import AppSettings
    primary = primary or get_primary_admin()
    if not primary or not primary.email:
        return False, 'No primary admin with an email address'

    backup_dir = get_backup_dir(app)
    fname = create_backup_file(primary, app.config['UPLOAD_FOLDER'], backup_dir,
                               include_db_dump=True)
    ok, error = email_backup(os.path.join(backup_dir, fname), primary.email)
    if ok:
        AppSettings.set('backup_email_last_sent', datetime.utcnow().isoformat())
    else:
        logger.error('Backup email failed: %s', error)
    return ok, error


# ---------------------------------------------------------------------------
# Scheduler tick
# ---------------------------------------------------------------------------

def run_scheduled_backup_tick(app, now=None):
    """
    One hourly scheduler check. Disk backups follow the daily/weekly/monthly
    schedule; the emailed backup has its own interval clock. Both only fire
    during the configured backup hour (UTC).
    """
    from app.models import AppSettings, User

    now = now or datetime.utcnow()
    target_hour = int(AppSettings.get('backup_hour', '2'))
    if now.hour != target_hour:
        return

    disk_due = AppSettings.get('backup_enabled', 'false') == 'true'
    if disk_due:
        frequency = AppSettings.get('backup_frequency', 'daily')
        if frequency == 'weekly' and now.weekday() != 0:
            disk_due = False
        elif frequency == 'monthly' and now.day != 1:
            disk_due = False
    if disk_due:
        last_run = AppSettings.get('backup_last_run', '')
        try:
            if last_run and (now - datetime.fromisoformat(last_run)).total_seconds() < 3600:
                disk_due = False
        except ValueError:
            pass

    email_due = AppSettings.get('backup_email_enabled', 'false') == 'true'
    if email_due:
        interval = clamp_email_interval(AppSettings.get('backup_email_interval_days', '7'))
        email_due = backup_email_due(now, AppSettings.get('backup_email_last_sent', ''), interval)
    if email_due:
        last_attempt = AppSettings.get('backup_email_last_attempt', '')
        try:
            if last_attempt and (now - datetime.fromisoformat(last_attempt)).total_seconds() < 3600:
                email_due = False
        except ValueError:
            pass

    if not (disk_due or email_due):
        return

    backup_dir = get_backup_dir(app)
    upload_folder = app.config['UPLOAD_FOLDER']
    retention = int(AppSettings.get('backup_retention', '7'))
    primary = get_primary_admin()

    if disk_due:
        for admin_user in User.query.filter_by(is_admin=True).all():
            try:
                fname = create_backup_file(admin_user, upload_folder, backup_dir, include_db_dump=True)
                logger.info('Scheduled backup created for %s: %s', admin_user.username, fname)
            except Exception as e:
                logger.error('Scheduled backup failed for %s: %s', admin_user.username, e)
        AppSettings.set('backup_last_run', now.isoformat())

    if email_due:
        AppSettings.set('backup_email_last_attempt', now.isoformat())
        try:
            ok, error = send_backup_email_now(app, primary)
            if ok:
                logger.info('Scheduled backup emailed to %s', primary.email)
            else:
                logger.error('Scheduled backup email failed: %s', error)
        except Exception as e:
            logger.error('Scheduled backup email failed: %s', e)

    cleanup_old_backups(backup_dir, retention)
