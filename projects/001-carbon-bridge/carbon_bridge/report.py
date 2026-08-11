"""Rendering of decomposition results: text tables, ASCII waterfall, markdown."""

from __future__ import annotations

from typing import Sequence

from .lmdi import EFFECTS, Decomposition

LABELS = {
    "activity": "Activity",
    "structure": "Mix / structure",
    "intensity": "Energy intensity",
    "emission_factor": "Emission factor",
}


def _fmt(value: float, unit: str = "") -> str:
    suffix = f" {unit}" if unit else ""
    return f"{value:+,.1f}{suffix}"


def waterfall(decomposition: Decomposition, unit: str = "tCO2e", width: int = 40) -> str:
    """ASCII waterfall of the four effects, scaled to the largest one."""
    effects = decomposition.effects
    largest = max((abs(v) for v in effects.values()), default=0.0)
    lines = []
    for name in EFFECTS:
        value = effects[name]
        bars = 0 if largest == 0 else round(abs(value) / largest * width)
        if value >= 0:
            body = " " * width + "|" + "#" * bars + " " * (width - bars)
        else:
            body = " " * (width - bars) + "#" * bars + "|" + " " * width
        lines.append(f"  {LABELS[name]:<18}{body}  {_fmt(value, unit)}")
    return "\n".join(lines)


def summary(decomposition: Decomposition, unit: str = "tCO2e") -> str:
    """Human-readable portfolio-level summary."""
    d = decomposition
    pct = (d.total_change / d.base_emissions * 100) if d.base_emissions else float("nan")

    pad = " " * 81  # aligns the totals under the right edge of the waterfall

    return "\n".join(
        [
            f"{d.base_period} -> {d.target_period}",
            "=" * 60,
            f"  Emissions {d.base_period:<12} {d.base_emissions:>14,.1f} {unit}",
            f"  Emissions {d.target_period:<12} {d.target_emissions:>14,.1f} {unit}",
            f"  Change                  {d.total_change:>+14,.1f} {unit}  ({pct:+.1f}%)",
            "",
            "  Driver contributions",
            "  " + "-" * 58,
            waterfall(d, unit=unit),
            "  " + "-" * 58,
            f"  {'Explained':<18}{pad}  {_fmt(d.explained_change, unit)}",
            f"  {'Residual':<18}{pad}  {_fmt(d.residual, unit)}",
        ]
    )


def segment_table(decomposition: Decomposition, unit: str = "tCO2e") -> str:
    """Per-segment breakdown, sorted by absolute total contribution."""
    rows = sorted(decomposition.segments, key=lambda s: -abs(s.total))
    header = (
        f"  {'Segment':<20}{'Base':>12}{'Target':>12}"
        f"{'Activity':>12}{'Mix':>12}{'Intensity':>12}{'Factor':>12}{'Total':>12}"
    )
    lines = [f"  Per-segment contributions ({unit})", "  " + "-" * (len(header) - 2), header]
    for s in rows:
        lines.append(
            f"  {s.name[:19]:<20}{s.base_emissions:>12,.1f}{s.target_emissions:>12,.1f}"
            f"{s.activity:>+12,.1f}{s.structure:>+12,.1f}{s.intensity:>+12,.1f}"
            f"{s.emission_factor:>+12,.1f}{s.total:>+12,.1f}"
        )
    return "\n".join(lines)


def narrative(decomposition: Decomposition, unit: str = "tCO2e") -> str:
    """One paragraph explaining what actually moved the number.

    This is the part a reader usually wants: not the table, but which
    driver dominated and whether the change is real decarbonisation or
    just a change in output.
    """
    d = decomposition
    effects = d.effects
    ranked = sorted(effects.items(), key=lambda kv: -abs(kv[1]))
    direction = "rose" if d.total_change > 0 else "fell"

    lead, lead_value = ranked[0]
    parts = [
        f"Emissions {direction} by {abs(d.total_change):,.1f} {unit} "
        f"between {d.base_period} and {d.target_period}."
    ]
    parts.append(
        f"The dominant driver was {LABELS[lead].lower()} "
        f"({lead_value:+,.1f} {unit}, {abs(lead_value) / max(sum(abs(v) for v in effects.values()), 1e-12):.0%} "
        "of gross driver movement)."
    )

    structural = effects["activity"] + effects["structure"]
    efficiency = effects["intensity"] + effects["emission_factor"]
    parts.append(
        f"Splitting the drivers, {structural:+,.1f} {unit} came from how much and what "
        f"the portfolio produced, and {efficiency:+,.1f} {unit} from how cleanly it "
        "produced it."
    )
    if efficiency < 0 < d.total_change:
        parts.append(
            "Underlying efficiency improved; the increase is explained by growth, "
            "so an intensity-based target would show progress where an absolute "
            "target does not."
        )
    elif efficiency > 0 > d.total_change:
        parts.append(
            "The reduction came from lower output rather than from decarbonisation, "
            "which will reverse if volumes recover."
        )
    return " ".join(parts)


def to_markdown(decompositions: Sequence[Decomposition], unit: str = "tCO2e") -> str:
    """Full markdown report for one or more period comparisons."""
    blocks = ["# Emissions decomposition", ""]
    for d in decompositions:
        pct = (d.total_change / d.base_emissions * 100) if d.base_emissions else float("nan")
        blocks += [
            f"## {d.base_period} → {d.target_period}",
            "",
            narrative(d, unit),
            "",
            "| Item | Value |",
            "| --- | ---: |",
            f"| Emissions, {d.base_period} | {d.base_emissions:,.1f} {unit} |",
            f"| Emissions, {d.target_period} | {d.target_emissions:,.1f} {unit} |",
            f"| Change | {d.total_change:+,.1f} {unit} ({pct:+.1f}%) |",
            "",
            "| Driver | Contribution |",
            "| --- | ---: |",
        ]
        for name in EFFECTS:
            blocks.append(f"| {LABELS[name]} | {d.effects[name]:+,.1f} {unit} |")
        blocks += [
            f"| **Explained** | **{d.explained_change:+,.1f} {unit}** |",
            f"| Residual | {d.residual:+,.3g} {unit} |",
            "",
            "| Segment | Base | Target | Activity | Mix | Intensity | Factor | Total |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for s in sorted(d.segments, key=lambda s: -abs(s.total)):
            blocks.append(
                f"| {s.name} | {s.base_emissions:,.1f} | {s.target_emissions:,.1f} "
                f"| {s.activity:+,.1f} | {s.structure:+,.1f} | {s.intensity:+,.1f} "
                f"| {s.emission_factor:+,.1f} | {s.total:+,.1f} |"
            )
        blocks.append("")
    return "\n".join(blocks)
