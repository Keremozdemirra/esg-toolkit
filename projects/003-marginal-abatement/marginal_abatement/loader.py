"""CSV loading for marginal-abatement."""

from __future__ import annotations

import csv
from pathlib import Path

from .curve import AbatementError, Measure

REQUIRED = ("name", "capex", "opex", "abatement", "lifetime")


def _number(raw: str, *, field: str, name: str) -> float:
    text = (raw or "").strip().replace(" ", "").replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError as exc:
        raise AbatementError(f"{name}: {field} value {raw!r} is not a number") from exc


def _names(raw: str) -> frozenset[str]:
    """Split a semicolon- or pipe-separated list of measure names."""
    text = (raw or "").strip()
    if not text:
        return frozenset()
    parts = text.replace("|", ";").split(";")
    return frozenset(p.strip() for p in parts if p.strip())


def load_measures(path: str | Path) -> list[Measure]:
    path = Path(path)
    if not path.exists():
        raise AbatementError(f"input file not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = {c.strip().lower(): c for c in (reader.fieldnames or [])}
        missing = [c for c in REQUIRED if c not in header]
        if missing:
            raise AbatementError(f"missing column(s): {', '.join(missing)}")

        measures = []
        for row in reader:
            name = (row[header["name"]] or "").strip()
            if not name:
                continue
            measures.append(
                Measure(
                    name=name,
                    capex=_number(row[header["capex"]], field="capex", name=name),
                    opex=_number(row[header["opex"]], field="opex", name=name),
                    abatement=_number(
                        row[header["abatement"]], field="abatement", name=name
                    ),
                    lifetime=int(
                        _number(row[header["lifetime"]], field="lifetime", name=name)
                    ),
                    excludes=_names(row.get(header.get("excludes", ""), "")),
                    requires=_names(row.get(header.get("requires", ""), "")),
                )
            )
    if not measures:
        raise AbatementError(f"{path} contained no measures")
    return measures
