"""Tests for the British unit-system gag conversions in app/units.py."""
import pytest
from app.units import miles_to_furlongs, uk_gallons_to_firkins, mpg_uk_to_rods_per_hogshead


class TestUnitConversions:
    def test_miles_to_furlongs(self):
        assert miles_to_furlongs(1) == 8

    def test_uk_gallons_to_firkins(self):
        assert uk_gallons_to_firkins(9) == 1

    def test_mpg_uk_to_rods_per_hogshead(self):
        # 1 mpg-UK = 320 rods/mile * 54 UK-gal/hogshead = 17280 rods/hogshead
        assert mpg_uk_to_rods_per_hogshead(1) == 17280
        # A real ~35 mpg-UK car lands in the classic joke's ballpark (~600k)
        result = mpg_uk_to_rods_per_hogshead(35)
        assert 550000 < result < 650000


class TestUnitDisplayFilters:
    def test_format_distance_imperial(self, app, test_user):
        with app.app_context():
            filt = app.jinja_env.filters['format_distance']
            assert filt(100, test_user) == '100.0 mi'

    def test_format_distance_british(self, app, test_user):
        test_user.unit_system = 'british'
        test_user.distance_unit = 'mi'
        with app.app_context():
            filt = app.jinja_env.filters['format_distance']
            assert filt(1, test_user) == '8.0 furlongs'

    def test_format_distance_british_ignores_km_override(self, app, test_user):
        # A per-vehicle override to km shouldn't get the furlong treatment
        test_user.unit_system = 'british'
        with app.app_context():
            filt = app.jinja_env.filters['format_distance']
            assert filt(100, test_user, 'km') == '100.0 km'

    def test_format_volume_british(self, app, test_user):
        test_user.unit_system = 'british'
        with app.app_context():
            filt = app.jinja_env.filters['format_volume']
            assert filt(9, test_user) == '1.00 firkins'

    def test_format_consumption_british(self, app, test_user):
        test_user.unit_system = 'british'
        with app.app_context():
            filt = app.jinja_env.filters['format_consumption']
            assert filt(1, test_user) == '17,280 rods/hogshead'

    def test_format_distance_none(self, app, test_user):
        with app.app_context():
            filt = app.jinja_env.filters['format_distance']
            assert filt(None, test_user) == '-'
