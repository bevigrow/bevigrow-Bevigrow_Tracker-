"""Unit conversion and compatibility utilities for Bevi Stoq."""

from enum import Enum
from typing import Optional, Tuple

class UnitFamily(str, Enum):
    """Compatible unit families."""
    WEIGHT = "weight"
    VOLUME = "volume"
    COUNT = "count"
    LENGTH = "length"
    AREA = "area"

# Define unit families and their conversions
UNIT_FAMILIES = {
    UnitFamily.WEIGHT: {
        "units": ["g", "kg", "tonne", "mg", "lb", "oz"],
        "base_unit": "g",
        "conversions": {
            "g": 1,
            "kg": 1000,
            "tonne": 1000000,
            "mg": 0.001,
            "lb": 453.592,
            "oz": 28.3495,
        }
    },
    UnitFamily.VOLUME: {
        "units": ["ml", "l", "litre", "cl", "dl"],
        "base_unit": "ml",
        "conversions": {
            "ml": 1,
            "l": 1000,
            "litre": 1000,
            "cl": 10,
            "dl": 100,
        }
    },
    UnitFamily.COUNT: {
        "units": ["pcs", "pc", "pieces", "box", "bag", "packet", "carton"],
        "base_unit": "pcs",
        "conversions": {
            "pcs": 1,
            "pc": 1,
            "pieces": 1,
            "box": 1,
            "bag": 1,
            "packet": 1,
            "carton": 1,
        }
    }
}

def get_unit_family(unit: str) -> Optional[UnitFamily]:
    """Get the family of a unit."""
    unit_lower = unit.lower()
    for family, config in UNIT_FAMILIES.items():
        if unit_lower in [u.lower() for u in config["units"]]:
            return family
    return None

def are_units_compatible(unit1: str, unit2: str) -> bool:
    """Check if two units are compatible (same family)."""
    family1 = get_unit_family(unit1)
    family2 = get_unit_family(unit2)
    return family1 is not None and family1 == family2

def convert_quantity(quantity: float, from_unit: str, to_unit: str) -> Optional[float]:
    """Convert quantity from one unit to another."""
    if not are_units_compatible(from_unit, to_unit):
        return None

    from_unit_lower = from_unit.lower()
    to_unit_lower = to_unit.lower()

    family = get_unit_family(from_unit)
    config = UNIT_FAMILIES[family]

    # Convert to base unit first
    from_conversion = next(
        (v for k, v in config["conversions"].items() if k.lower() == from_unit_lower),
        None
    )
    to_conversion = next(
        (v for k, v in config["conversions"].items() if k.lower() == to_unit_lower),
        None
    )

    if from_conversion is None or to_conversion is None:
        return None

    # Convert: quantity * (from_conversion / to_conversion)
    return round(quantity * (from_conversion / to_conversion), 4)

def normalize_quantity_to_base_unit(quantity: float, unit: str) -> Tuple[float, str]:
    """Convert quantity to base unit of its family."""
    family = get_unit_family(unit)
    if family is None:
        return quantity, unit

    config = UNIT_FAMILIES[family]
    base_unit = config["base_unit"]

    converted = convert_quantity(quantity, unit, base_unit)
    if converted is None:
        return quantity, unit

    return converted, base_unit

def get_compatible_units(unit: str) -> list[str]:
    """Get all compatible units for a given unit."""
    family = get_unit_family(unit)
    if family is None:
        return [unit]
    return UNIT_FAMILIES[family]["units"]

def validate_unit(unit: str) -> bool:
    """Check if unit is valid."""
    return get_unit_family(unit) is not None
