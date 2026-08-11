"""marginal-abatement: build and interrogate marginal abatement cost curves."""

from .curve import (
    AbatementError,
    Curve,
    Measure,
    Step,
    annuity_factor,
    build_curve,
    feasible_selection,
    optimal_selection,
    render,
)

__version__ = "0.1.0"

__all__ = [
    "AbatementError",
    "Curve",
    "Measure",
    "Step",
    "annuity_factor",
    "build_curve",
    "feasible_selection",
    "optimal_selection",
    "render",
]
