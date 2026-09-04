"""Conversion helpers for the 'British' unit system.

A joke option in Settings that displays real, correctly-converted archaic
units on top of the app's already-correct UK Imperial values (miles / UK
gallons / UK mpg) -- it's a display-layer transform only, not a new way of
storing or calculating data.
"""

FURLONGS_PER_MILE = 8
UK_GALLONS_PER_FIRKIN = 9
RODS_PER_MILE = 320
UK_GALLONS_PER_HOGSHEAD = 54


def miles_to_furlongs(miles):
    return miles * FURLONGS_PER_MILE


def uk_gallons_to_firkins(gallons):
    return gallons / UK_GALLONS_PER_FIRKIN


def mpg_uk_to_rods_per_hogshead(mpg):
    return mpg * RODS_PER_MILE * UK_GALLONS_PER_HOGSHEAD
