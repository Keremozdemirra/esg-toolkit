"""Command line interface for marginal-abatement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .curve import AbatementError, build_curve, feasible_selection, render
from .loader import load_measures


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="macc",
        description=(
            "Build a marginal abatement cost curve: rank measures by cost per "
            "tonne, find the cheapest route to a target, and see what a given "
            "carbon price makes worth doing."
        ),
    )
    p.add_argument("csv", type=Path, help="measures file; see examples/")
    p.add_argument("--rate", type=float, default=0.05, help="discount rate")
    p.add_argument("--target", type=float, help="tonnes per year to abate")
    p.add_argument(
        "--carbon-price", type=float, help="report abatement unlocked at this price"
    )
    p.add_argument("--currency", default="EUR")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        curve = build_curve(load_measures(args.csv), rate=args.rate)
        selection = feasible_selection(curve, args.target) if args.target else None
    except AbatementError as exc:
        print(f"macc: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        payload = {
            "rate": curve.rate,
            "total_abatement": curve.total_abatement,
            "no_regret_abatement": curve.no_regret_abatement,
            "annual_cost": curve.annual_cost(),
            "steps": [
                {
                    "name": s.name,
                    "cost_per_tonne": s.cost_per_tonne,
                    "abatement": s.abatement,
                    "cumulative_abatement": s.cumulative_abatement,
                }
                for s in curve.steps
            ],
        }
        if selection is not None:
            payload["selection"] = [s.name for s in selection]
        print(json.dumps(payload, indent=2))
        return 0

    print(render(curve, currency=args.currency))

    if args.carbon_price is not None:
        unlocked = curve.carbon_price_unlocking(args.carbon_price)
        print()
        print(
            f"  At {args.carbon_price:,.0f} {args.currency}/t, "
            f"{unlocked:,.0f} t/yr of abatement pays for itself "
            f"({unlocked / curve.total_abatement:.0%} of the curve)."
        )

    if selection is not None:
        total = sum(s.abatement for s in selection)
        cost = sum(s.cost_per_tonne * s.abatement for s in selection)
        print()
        print(f"  Cheapest feasible route to {args.target:,.0f} t/yr:")
        for s in selection:
            print(f"    - {s.name:<32}{s.abatement:>10,.0f} t{s.cost_per_tonne:>12,.1f}/t")
        print(f"    {'':<34}{total:>10,.0f} t{cost:>12,.0f} {args.currency}/yr")
        if total > args.target:
            print(
                f"    Overshoots by {total - args.target:,.0f} t because measures are "
                "taken whole."
            )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
