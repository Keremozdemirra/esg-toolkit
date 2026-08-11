"""CSV loading for carbon-bridge.

Expected layout: one row per segment per period, long format.

    period,segment,activity,energy,emissions
    2023,Plant A,120000,48000,15600
    2023,Plant B,80000,26000,10400
    2024,Plant A,131000,49500,14200
    2024,Plant B,74000,23000,8900

Column names are matched case-insensitively and a few common aliases are
accepted, because real exports rarely use the exact header you want.
"""

from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from .lmdi import DecompositionError, Segment

ALIASES: dict[str, tuple[str, ...]] = {
    "period": ("period", "year", "reporting_period", "reporting period", "date"),
    "segment": (
        "segment",
        "name",
        "facility",
        "site",
        "plant",
        "product",
        "country",
        "business_unit",
        "business unit",
    ),
    "activity": ("activity", "output", "production", "volume", "revenue", "units"),
    "energy": ("energy", "energy_consumption", "energy consumption", "consumption", "mwh"),
    "emissions": ("emissions", "co2", "co2e", "ghg", "tco2e", "tco2"),
}


def _resolve_columns(header: Iterable[str]) -> dict[str, str]:
    """Map each required field to the actual column name in the file."""
    normalised = {column.strip().lower(): column for column in header}
    resolved: dict[str, str] = {}
    for field, candidates in ALIASES.items():
        for candidate in candidates:
            if candidate in normalised:
                resolved[field] = normalised[candidate]
                break
        else:
            raise DecompositionError(
                f"could not find a column for {field!r}; "
                f"accepted names: {', '.join(candidates)}"
            )
    return resolved


def _to_float(raw: str, *, field: str, row_number: int) -> float:
    """Parse a number, tolerating thousands separators and blanks."""
    text = (raw or "").strip().replace(" ", "")
    if not text:
        return 0.0
    # 1.234,56 (European) vs 1,234.56 (Anglo). Decide by which separator is last.
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", "." if text.count(",") == 1 else "")
    try:
        return float(text)
    except ValueError as exc:
        raise DecompositionError(
            f"row {row_number}: could not read {field} value {raw!r} as a number"
        ) from exc


def load_periods(path: str | Path) -> "OrderedDict[str, list[Segment]]":
    """Read a long-format CSV into an ordered mapping of period -> segments.

    Periods come back in order of first appearance in the file, so the
    file itself defines the chronology. Duplicate period/segment pairs
    are summed rather than silently overwriting each other.
    """
    path = Path(path)
    if not path.exists():
        raise DecompositionError(f"input file not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise DecompositionError(f"{path} appears to be empty")
        columns = _resolve_columns(reader.fieldnames)

        accumulator: "OrderedDict[str, OrderedDict[str, list[float]]]" = OrderedDict()
        for row_number, row in enumerate(reader, start=2):
            period = (row[columns["period"]] or "").strip()
            segment = (row[columns["segment"]] or "").strip()
            if not period or not segment:
                continue  # blank padding rows are common in exported sheets

            values = [
                _to_float(row[columns[field]], field=field, row_number=row_number)
                for field in ("activity", "energy", "emissions")
            ]
            bucket = accumulator.setdefault(period, OrderedDict())
            running = bucket.setdefault(segment, [0.0, 0.0, 0.0])
            for index, value in enumerate(values):
                running[index] += value

    if not accumulator:
        raise DecompositionError(f"{path} contained no usable rows")

    return OrderedDict(
        (
            period,
            [
                Segment(name, activity, energy, emissions)
                for name, (activity, energy, emissions) in segments.items()
            ],
        )
        for period, segments in accumulator.items()
    )
