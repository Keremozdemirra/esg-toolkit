"""cbam-embedded: specific embedded emissions of CBAM goods from installation data."""

from .embedded import (
    CbamError,
    EmissionPair,
    Installation,
    PrecursorInput,
    ProcessResult,
    ProductionProcess,
    PURCHASED,
    render,
    render_attribution,
    resolve,
)

__version__ = "0.1.0"

__all__ = [
    "CbamError",
    "EmissionPair",
    "Installation",
    "PrecursorInput",
    "ProcessResult",
    "ProductionProcess",
    "PURCHASED",
    "render",
    "render_attribution",
    "resolve",
]
