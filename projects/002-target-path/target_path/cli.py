"""Command line interface for target-path."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .pathway import (
    REFERENCE_RATES,
    TargetError,
    absolute_contraction,
    assess,
    intensity_convergence,
)


def _load_actuals(path: Path) -> dict[int, float]:
    """Read a two-column CSV of year and emissions."""
    if not path.exists():
        raise TargetError(f"actuals file not found: {path}")
    actuals: dict[int, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if len(row) < 2 or not row[0].strip():
                continue
            try:
                year = int(float(row[0].strip()))
                value = float(row[1].strip().replace(",", ""))
            except ValueError:
                if row_number == 1:
                    continue  # header
                raise TargetError(f"row {row_number}: could not parse {row[:2]}")
            actuals[year] = value
    if not actuals:
        raise TargetError(f"{path} contained no usable rows")
    return actuals


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="target-path",
        description=(
            "Build an emission reduction pathway between a base year and a "
            "target year, then measure actual performance against it."
        ),
    )
    p.add_argument("--base-emissions", type=float, required=True)
    p.add_argument("--base-year", type=int, required=True)
    p.add_argument("--target-year", type=int, required=True)
    p.add_argument(
        "--rate",
        type=float,
        help="annual linear reduction as a fraction of the base year, e.g. 0.042",
    )
    p.add_argument(
        "--ambition",
        choices=sorted(REFERENCE_RATES),
        help="use an indicative reference rate instead of --rate (check current criteria)",
    )
    p.add_argument(
        "--activity",
        type=Path,
        help="CSV of year,activity; switches to an intensity-convergence pathway",
    )
    p.add_argument("--actuals", type=Path, help="CSV of year,actual emissions")
    p.add_argument("--unit", default="tCO2e")
    p.add_argument("--format", choices=("text", "csv", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.rate is None and args.ambition is None:
            raise TargetError("supply either --rate or --ambition")
        if args.rate is not None and args.ambition is not None:
            raise TargetError("--rate and --ambition are mutually exclusive")
        rate = args.rate if args.rate is not None else REFERENCE_RATES[args.ambition]

        if args.activity:
            activity = _load_actuals(args.activity)
            base_intensity = args.base_emissions / activity[args.base_year]
            pathway = intensity_convergence(
                base_intensity, activity, args.base_year, args.target_year, rate
            )
        else:
            pathway = absolute_contraction(
                args.base_emissions, args.base_year, args.target_year, rate
            )

        actuals = _load_actuals(args.actuals) if args.actuals else {}
    except (TargetError, KeyError) as exc:
        print(f"target-path: {exc}", file=sys.stderr)
        return 2

    if args.format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(["year", "pathway", "intensity", "actual", "gap"])
        for point in pathway.points:
            actual = actuals.get(point.year, "")
            gap = actual - point.emissions if actual != "" else ""
            writer.writerow(
                [
                    point.year,
                    round(point.emissions, 3),
                    "" if point.intensity is None else round(point.intensity, 6),
                    actual,
                    "" if gap == "" else round(gap, 3),
                ]
            )
        return 0

    if args.format == "json":
        payload = {
            "kind": pathway.kind,
            "rate": pathway.rate,
            "base_year": pathway.base_year,
            "target_year": pathway.target_year,
            "target_emissions": pathway.target_emissions,
            "total_reduction": pathway.total_reduction,
            "budget": pathway.budget(),
            "points": [
                {"year": p.year, "emissions": p.emissions, "intensity": p.intensity}
                for p in pathway.points
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    u = args.unit
    print(f"{pathway.kind.replace('_', ' ')} at {pathway.rate:.2%} per year")
    print("=" * 62)
    print(f"  {pathway.base_year} base       {pathway.base_emissions:>14,.1f} {u}")
    print(f"  {pathway.target_year} target     {pathway.target_emissions:>14,.1f} {u}")
    print(f"  Total reduction  {pathway.total_reduction:>14.1%}")
    print(f"  Cumulative budget{pathway.budget():>14,.1f} {u}")
    print()
    print(f"  {'Year':<8}{'Pathway':>14}{'Actual':>14}{'Gap':>14}  Status")
    print("  " + "-" * 58)
    for point in pathway.points:
        actual = actuals.get(point.year)
        if actual is None:
            print(f"  {point.year:<8}{point.emissions:>14,.1f}{'':>14}{'':>14}")
            continue
        gap = actual - point.emissions
        status = "on track" if gap <= 0 else "behind"
        print(
            f"  {point.year:<8}{point.emissions:>14,.1f}{actual:>14,.1f}"
            f"{gap:>+14,.1f}  {status}"
        )

    if actuals:
        latest = max(actuals)
        if pathway.base_year <= latest <= pathway.target_year:
            a = assess(pathway, latest, actuals[latest])
            print()
            print(f"  As at {latest}: {a.achieved_reduction:.1%} below the base year, "
                  f"pathway requires {1 - a.required / pathway.base_emissions:.1%}.")
            if latest < pathway.target_year:
                print(
                    f"  To still land on {pathway.target_year}, emissions must now fall "
                    f"{a.required_rate_from_here():.2%} of today's level every year."
                )
            overshoot = a.cumulative_overshoot(
                {y: v for y, v in actuals.items() if y <= pathway.target_year}
            )
            print(
                f"  Cumulative emissions to date are {overshoot:+,.1f} {u} against budget."
            )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
