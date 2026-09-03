from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import gettext as _
from app import db
from app.models import Vehicle, Trip, TRIP_PURPOSES
from app.security import safe_int, safe_float

bp = Blueprint('trips', __name__, url_prefix='/trips')


@bp.route('/')
@login_required
def index():
    """List all trips with filters"""
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]

    # Get filter parameters
    vehicle_filter = request.args.get('vehicle', type=int)
    purpose_filter = request.args.get('purpose')
    year_filter = request.args.get('year', type=int)

    # Base query
    query = Trip.query.filter(Trip.vehicle_id.in_(vehicle_ids))

    # Apply filters
    if vehicle_filter:
        query = query.filter(Trip.vehicle_id == vehicle_filter)
    if purpose_filter:
        query = query.filter(Trip.purpose == purpose_filter)
    if year_filter:
        query = query.filter(db.extract('year', Trip.date) == year_filter)

    trips = query.order_by(Trip.date.desc()).all()

    # Get available years for filter
    years = db.session.query(db.extract('year', Trip.date)).filter(
        Trip.vehicle_id.in_(vehicle_ids)
    ).distinct().all()
    years = sorted([int(y[0]) for y in years if y[0]], reverse=True)

    # Calculate totals
    total_distance = sum(trip.distance for trip in trips)
    business_distance = sum(trip.distance for trip in trips if trip.purpose == 'business')

    return render_template('trips/index.html',
                           trips=trips,
                           vehicles=vehicles,
                           purposes=TRIP_PURPOSES,
                           years=years,
                           vehicle_filter=vehicle_filter,
                           purpose_filter=purpose_filter,
                           year_filter=year_filter,
                           total_distance=total_distance,
                           business_distance=business_distance)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Create a new trip"""
    vehicles = current_user.get_all_vehicles()

    if not vehicles:
        flash(_('Please add a vehicle first'), 'info')
        return redirect(url_for('vehicles.new'))

    if request.method == 'POST':
        vehicle_id = safe_int(request.form.get('vehicle_id'))
        vehicle = Vehicle.query.get_or_404(vehicle_id)

        if vehicle not in vehicles:
            flash(_('Access denied'), 'error')
            return redirect(url_for('trips.index'))

        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()

        trip = Trip(
            vehicle_id=vehicle_id,
            user_id=current_user.id,
            date=date,
            start_odometer=safe_float(request.form.get('start_odometer')),
            end_odometer=safe_float(request.form.get('end_odometer')),
            purpose=request.form.get('purpose'),
            description=request.form.get('description'),
            start_location=request.form.get('start_location'),
            end_location=request.form.get('end_location'),
            notes=request.form.get('notes')
        )

        db.session.add(trip)
        db.session.commit()

        flash(_('Trip logged successfully'), 'success')
        return redirect(url_for('trips.index'))

    # Pre-select vehicle if provided
    selected_vehicle_id = request.args.get('vehicle_id', type=int)

    # Get last odometer for selected vehicle
    last_odometer = 0
    if selected_vehicle_id:
        vehicle = Vehicle.query.get(selected_vehicle_id)
        if vehicle:
            last_odometer = vehicle.get_last_odometer()
    elif len(vehicles) == 1:
        last_odometer = vehicles[0].get_last_odometer()

    return render_template('trips/form.html',
                           trip=None,
                           vehicles=vehicles,
                           purposes=TRIP_PURPOSES,
                           selected_vehicle_id=selected_vehicle_id,
                           last_odometer=last_odometer)


@bp.route('/<int:trip_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(trip_id):
    """Edit an existing trip"""
    trip = Trip.query.get_or_404(trip_id)
    vehicles = current_user.get_all_vehicles()

    if trip.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('trips.index'))

    if request.method == 'POST':
        date_str = request.form.get('date')
        trip.date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else trip.date
        trip.start_odometer = safe_float(request.form.get('start_odometer'))
        trip.end_odometer = safe_float(request.form.get('end_odometer'))
        trip.purpose = request.form.get('purpose')
        trip.description = request.form.get('description')
        trip.start_location = request.form.get('start_location')
        trip.end_location = request.form.get('end_location')
        trip.notes = request.form.get('notes')

        db.session.commit()
        flash(_('Trip updated successfully'), 'success')
        return redirect(url_for('trips.index'))

    return render_template('trips/form.html',
                           trip=trip,
                           vehicles=vehicles,
                           purposes=TRIP_PURPOSES,
                           selected_vehicle_id=trip.vehicle_id,
                           last_odometer=trip.vehicle.get_last_odometer())


@bp.route('/<int:trip_id>/delete', methods=['POST'])
@login_required
def delete(trip_id):
    """Delete a trip"""
    trip = Trip.query.get_or_404(trip_id)
    vehicles = current_user.get_all_vehicles()

    if trip.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('trips.index'))

    db.session.delete(trip)
    db.session.commit()
    flash(_('Trip deleted successfully'), 'success')
    return redirect(url_for('trips.index'))


@bp.route('/report')
@login_required
def report():
    """Tax deduction report showing business vs personal trips"""
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]

    # Get year filter (default to current year)
    year = request.args.get('year', type=int) or datetime.now().year

    # Get all trips for the year
    trips = Trip.query.filter(
        Trip.vehicle_id.in_(vehicle_ids),
        db.extract('year', Trip.date) == year
    ).order_by(Trip.date.asc()).all()

    # Calculate summary by purpose
    summary = {}
    for purpose_code, purpose_label in TRIP_PURPOSES:
        purpose_trips = [t for t in trips if t.purpose == purpose_code]
        summary[purpose_code] = {
            'label': purpose_label,
            'count': len(purpose_trips),
            'distance': sum(t.distance for t in purpose_trips)
        }

    total_distance = sum(t.distance for t in trips)
    business_distance = summary.get('business', {}).get('distance', 0)

    # Get available years for filter
    years = db.session.query(db.extract('year', Trip.date)).filter(
        Trip.vehicle_id.in_(vehicle_ids)
    ).distinct().all()
    years = sorted([int(y[0]) for y in years if y[0]], reverse=True)

    if year not in years and years:
        years.append(year)
        years.sort(reverse=True)

    return render_template('trips/report.html',
                           trips=trips,
                           summary=summary,
                           total_distance=total_distance,
                           business_distance=business_distance,
                           year=year,
                           years=years,
                           vehicles=vehicles)
