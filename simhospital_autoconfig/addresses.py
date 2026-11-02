"""US address components for generated data.yml files.

Simhospital composes a patient address as "<number> <noun> <street suffix>" and picks
the city from `address.cities`. The config key `streets` holds *suffixes*, not full
street names -- see simhospital/pkg/generator/address/address.go, where StreetSuffix
is documented as "a street suffix, eg.: Road, Street, Place etc." and Streets is
sampled directly by random().

The upstream data.yml ships UK values (London post towns, Road/Street/Lane/Avenue/
Place/Square). A generated config for a US hospital was inheriting those unchanged,
so patients in Chicago were being given London street types.
"""

from __future__ import annotations

# Common US street suffixes, spelled out to match the upstream file's style.
# Drawn from the USPS Publication 28 primary suffix list.
US_STREET_SUFFIXES: list[str] = [
    "Street",
    "Avenue",
    "Road",
    "Drive",
    "Lane",
    "Court",
    "Place",
    "Terrace",
    "Circle",
    "Boulevard",
    "Parkway",
    "Way",
    "Trail",
    "Highway",
    "Square",
    "Loop",
    "Crossing",
    "Run",
    "Path",
    "Ridge",
]

# Used only when the NPPES address carries no city. Simhospital samples from
# `address.cities` unconditionally, so the list must never be empty; callers log a
# warning when they fall back to this, because the result no longer reflects the
# hospital's actual location.
US_CITY_FALLBACK: list[str] = [
    "Springfield",
    "Riverside",
    "Fairview",
    "Greenville",
    "Madison",
    "Georgetown",
    "Arlington",
    "Salem",
    "Burlington",
    "Clinton",
]
