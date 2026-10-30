"""Per-vehicle mileage mode: odometer (default) vs rolling trip meter."""
from app import db
from app.models import FuelLog, Vehicle


def add_fill(client, vehicle, day, volume=10.0, **reading):
    data = {'vehicle_id': vehicle.id, 'date': f'2026-01-{day:02d}', 'volume': volume,
            'fuel_grade': 'regular', 'is_full_tank': 'on', **reading}
    return client.post('/fuel/new', data=data, follow_redirects=True)


def set_mode(client, vehicle, mode):
    resp = client.post(f'/vehicles/{vehicle.id}/edit', data={
        'name': vehicle.name, 'vehicle_type': 'car', 'fuel_type': 'petrol', 'mileage_mode': mode,
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(vehicle)
    assert vehicle.mileage_mode == mode


def logs(vehicle):
    return vehicle.fuel_logs.order_by(FuelLog.date, FuelLog.id).all()


def test_new_vehicle_defaults_to_odometer(sample_vehicle):
    assert sample_vehicle.mileage_mode == 'odometer'


def test_trip_meter_rollover_and_mpg(auth_client, sample_vehicle):
    set_mode(auth_client, sample_vehicle, 'trip')
    add_fill(auth_client, sample_vehicle, 1, trip_reading=900)
    add_fill(auth_client, sample_vehicle, 2, trip_reading=200)  # rolled over: 300
    add_fill(auth_client, sample_vehicle, 3, trip_reading=500)  # 300

    a, b, c = logs(sample_vehicle)
    assert [l.trip_reading for l in (a, b, c)] == [900, 200, 500]
    assert [l.odometer for l in (a, b, c)] == [0, 300, 600]
    assert b.get_consumption('mpg') == 30
    assert sample_vehicle.get_average_consumption('mpg') == 30


def test_switching_modes_keeps_existing_logs(auth_client, sample_vehicle):
    add_fill(auth_client, sample_vehicle, 1, odometer=10000)
    add_fill(auth_client, sample_vehicle, 2, odometer=10300)
    set_mode(auth_client, sample_vehicle, 'trip')
    add_fill(auth_client, sample_vehicle, 3, trip_reading=100)  # baseline: distance since 10300 unknown
    add_fill(auth_client, sample_vehicle, 4, trip_reading=400)
    set_mode(auth_client, sample_vehicle, 'odometer')
    add_fill(auth_client, sample_vehicle, 5, odometer=11000)  # baseline again
    add_fill(auth_client, sample_vehicle, 6, odometer=11300)

    o1, o2, t1, t2, o3, o4 = logs(sample_vehicle)
    # Odometer entries untouched, trip entries keep their raw readings
    assert (o1.odometer, o2.odometer, o3.odometer, o4.odometer) == (10000, 10300, 11000, 11300)
    assert (o1.trip_reading, o2.trip_reading, o3.trip_reading) == (None, None, None)
    assert (t1.trip_reading, t2.trip_reading) == (100, 400)
    # Trip entries continue on from the last real odometer reading
    assert (t1.odometer, t2.odometer) == (10300, 10600)
    # Fill-ups right after a switch have unknown distance, so no bogus MPG
    assert t1.get_consumption('mpg') is None and o3.get_consumption('mpg') is None
    assert [l.get_consumption('mpg') for l in (o2, t2, o4)] == [30, 30, 30]
    assert sample_vehicle.get_average_consumption('mpg') == 30


def test_editing_middle_trip_log_recomputes_later_ones(auth_client, sample_vehicle):
    set_mode(auth_client, sample_vehicle, 'trip')
    for day, reading in ((1, 0), (2, 300), (3, 600)):
        add_fill(auth_client, sample_vehicle, day, trip_reading=reading)
    middle = logs(sample_vehicle)[1]
    auth_client.post(f'/fuel/{middle.id}/edit', data={
        'date': '2026-01-02', 'trip_reading': 250, 'volume': 10, 'fuel_grade': 'regular', 'is_full_tank': 'on',
    }, follow_redirects=True)
    assert [l.odometer for l in logs(sample_vehicle)] == [0, 250, 600]

    auth_client.post(f'/fuel/{middle.id}/delete', follow_redirects=True)
    assert [l.odometer for l in logs(sample_vehicle)] == [0, 600]


def test_old_odometer_log_stays_odometer_after_switch(auth_client, sample_vehicle):
    add_fill(auth_client, sample_vehicle, 1, odometer=5000)
    set_mode(auth_client, sample_vehicle, 'trip')
    log = logs(sample_vehicle)[0]

    form = auth_client.get(f'/fuel/{log.id}/edit').data.decode()
    assert 'const fixedMode = "odometer"' in form

    auth_client.post(f'/fuel/{log.id}/edit', data={
        'date': '2026-01-01', 'odometer': 5100, 'volume': 10, 'fuel_grade': 'regular', 'is_full_tank': 'on',
    }, follow_redirects=True)
    db.session.refresh(log)
    assert (log.odometer, log.trip_reading) == (5100, None)


def test_trip_reading_validation(auth_client, sample_vehicle):
    set_mode(auth_client, sample_vehicle, 'trip')
    resp = add_fill(auth_client, sample_vehicle, 1, trip_reading=1000)
    assert b'Trip meter reading must be' in resp.data
    assert sample_vehicle.fuel_logs.count() == 0


def test_api_accepts_trip_reading(client, api_headers, sample_vehicle):
    sample_vehicle.mileage_mode = 'trip'
    db.session.commit()
    url = f'/api/v1/vehicles/{sample_vehicle.id}/fuel'
    first = client.post(url, json={'date': '2026-01-01', 'trip_reading': 950, 'volume': 10}, headers=api_headers)
    second = client.post(url, json={'date': '2026-01-02', 'trip_reading': 50, 'volume': 10}, headers=api_headers)
    assert first.status_code == second.status_code == 201
    assert (second.json['trip_reading'], second.json['odometer']) == (50, 100)
    assert second.json['consumption'] is not None

    bad = client.post(url, json={'date': '2026-01-03', 'trip_reading': 1200}, headers=api_headers)
    assert bad.status_code == 400
