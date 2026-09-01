"""
Unit conversion service for Bevi Stoq inventory calculations.

Handles conversion between compatible units (weight, volume, count, packaging).
Provides validation and centralized conversion logic.
"""

from enum import Enum
from typing import Literal

UnitType = Literal["weight", "volume", "count", "packaging"]


class UnitDimension(Enum):
    """Measurement dimension types."""
    WEIGHT = "weight"
    VOLUME = "volume"
    COUNT = "count"
    PACKAGING = "packaging"


# Define all supported units and their dimensions
UNIT_DIMENSION_MAP = {
    # Weight
    "g": UnitDimension.WEIGHT,
    "kg": UnitDimension.WEIGHT,
    "tonne": UnitDimension.WEIGHT,
    # Volume
    "ml": UnitDimension.VOLUME,
    "litre": UnitDimension.VOLUME,
    "l": UnitDimension.VOLUME,
    # Count
    "pcs": UnitDimension.COUNT,
    "pc": UnitDimension.COUNT,
    "piece": UnitDimension.COUNT,
    "pieces": UnitDimension.COUNT,
    # Packaging
    "box": UnitDimension.PACKAGING,
    "boxes": UnitDimension.PACKAGING,
    "bag": UnitDimension.PACKAGING,
    "bags": UnitDimension.PACKAGING,
}

# Conversion factors for each dimension (base unit in brackets)
# Weight base unit: g
WEIGHT_CONVERSIONS = {
    "g": 1.0,
    "kg": 1000.0,
    "tonne": 1_000_000.0,
}

# Volume base unit: ml
VOLUME_CONVERSIONS = {
    "ml": 1.0,
    "litre": 1000.0,
    "l": 1000.0,
}

# Count base unit: pcs
COUNT_CONVERSIONS = {
    "pcs": 1.0,
    "pc": 1.0,
    "piece": 1.0,
    "pieces": 1.0,
}

# Packaging base unit: box (no standard conversion - just tracking)
PACKAGING_CONVERSIONS = {
    "box": 1.0,
    "boxes": 1.0,
    "bag": 1.0,
    "bags": 1.0,
}

# Map dimensions to their conversion tables
DIMENSION_CONVERSIONS = {
    UnitDimension.WEIGHT: WEIGHT_CONVERSIONS,
    UnitDimension.VOLUME: VOLUME_CONVERSIONS,
    UnitDimension.COUNT: COUNT_CONVERSIONS,
    UnitDimension.PACKAGING: PACKAGING_CONVERSIONS,
}


def get_unit_dimension(unit: str) -> UnitDimension:
    """Get the dimension type of a unit (weight, volume, count, packaging)."""
    normalized = unit.lower().strip()
    if normalized not in UNIT_DIMENSION_MAP:
        raise ValueError(f"Unknown unit: {unit}")
    return UNIT_DIMENSION_MAP[normalized]


def are_units_compatible(unit1: str, unit2: str) -> bool:
    """Check if two units can be converted to each other."""
    try:
        return get_unit_dimension(unit1) == get_unit_dimension(unit2)
    except ValueError:
        return False


def convert_to_base_unit(quantity: float, from_unit: str, base_unit: str) -> float:
    """
    Convert a quantity from one unit to a base unit.

    Args:
        quantity: The amount to convert
        from_unit: The unit to convert from
        base_unit: The target base unit (must be compatible)

    Returns:
        The converted quantity in the base unit

    Raises:
        ValueError: If units are not compatible or unknown
    """
    if quantity < 0:
        raise ValueError("Quantity cannot be negative")

    from_unit_norm = from_unit.lower().strip()
    base_unit_norm = base_unit.lower().strip()

    # Same unit - no conversion needed
    if from_unit_norm == base_unit_norm:
        return quantity

    # Get dimensions
    from_dim = get_unit_dimension(from_unit_norm)
    base_dim = get_unit_dimension(base_unit_norm)

    # Check compatibility
    if from_dim != base_dim:
        raise ValueError(
            f"Cannot convert {from_unit} to {base_unit}: "
            f"incompatible dimensions ({from_dim.value} vs {base_dim.value})"
        )

    # Get conversion factors
    conversions = DIMENSION_CONVERSIONS[from_dim]

    if from_unit_norm not in conversions:
        raise ValueError(f"Conversion not available for unit: {from_unit}")
    if base_unit_norm not in conversions:
        raise ValueError(f"Conversion not available for unit: {base_unit}")

    # Convert: first to base unit of dimension, then to target base unit
    from_to_base = conversions[from_unit_norm]  # e.g., 1000 (kg to base g)
    base_to_target = 1.0 / conversions[base_unit_norm]  # e.g., 0.001 (g to kg)

    converted = quantity * from_to_base * base_to_target
    return round(converted, 6)  # Round to 6 decimals to avoid floating point errors


def convert_from_base_unit(quantity: float, base_unit: str, to_unit: str) -> float:
    """Convert from a base unit to another compatible unit."""
    # This is the reverse of convert_to_base_unit
    if quantity < 0:
        raise ValueError("Quantity cannot be negative")

    base_unit_norm = base_unit.lower().strip()
    to_unit_norm = to_unit.lower().strip()

    # Same unit - no conversion needed
    if base_unit_norm == to_unit_norm:
        return quantity

    # Get dimensions
    base_dim = get_unit_dimension(base_unit_norm)
    to_dim = get_unit_dimension(to_unit_norm)

    # Check compatibility
    if base_dim != to_dim:
        raise ValueError(
            f"Cannot convert {base_unit} to {to_unit}: "
            f"incompatible dimensions ({base_dim.value} vs {to_dim.value})"
        )

    # Get conversion factors
    conversions = DIMENSION_CONVERSIONS[base_dim]

    if base_unit_norm not in conversions:
        raise ValueError(f"Conversion not available for unit: {base_unit}")
    if to_unit_norm not in conversions:
        raise ValueError(f"Conversion not available for unit: {to_unit}")

    base_factor = conversions[base_unit_norm]
    to_factor = conversions[to_unit_norm]

    converted = quantity * base_factor / to_factor
    return round(converted, 6)


def format_quantity_with_unit(quantity: float, unit: str) -> str:
    """Format a quantity with its unit for display."""
    return f"{quantity} {unit}"
