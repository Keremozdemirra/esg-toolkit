"""target-path: build science-based target pathways and measure progress against them."""

from .pathway import (
    REFERENCE_RATES,
    Assessment,
    Pathway,
    Point,
    TargetError,
    absolute_contraction,
    assess,
    compare,
    intensity_convergence,
    required_rate,
    to_rows,
)

__version__ = "0.1.0"

__all__ = [
    "REFERENCE_RATES",
    "Assessment",
    "Pathway",
    "Point",
    "TargetError",
    "absolute_contraction",
    "assess",
    "compare",
    "intensity_convergence",
    "required_rate",
    "to_rows",
]
