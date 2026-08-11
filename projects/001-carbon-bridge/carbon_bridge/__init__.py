"""carbon-bridge: attribute a change in emissions to its underlying drivers."""

from .lmdi import (
    Decomposition,
    DecompositionError,
    Segment,
    SegmentEffect,
    decompose,
    decompose_series,
    logarithmic_mean,
)
from .loader import load_periods
from .report import narrative, segment_table, summary, to_markdown, waterfall

__version__ = "0.1.0"

__all__ = [
    "Decomposition",
    "DecompositionError",
    "Segment",
    "SegmentEffect",
    "decompose",
    "decompose_series",
    "load_periods",
    "logarithmic_mean",
    "narrative",
    "segment_table",
    "summary",
    "to_markdown",
    "waterfall",
]
