"""Command line interface for carbon-bridge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .lmdi import DecompositionError, decompose, decompose_series
from .loader import load_periods
from .report import narrative, segment_table, summary, to_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="carbon-bridge",
        description=(
            "Explain a change in emissions by splitting it into activity, mix, "
            "energy intensity and emission factor effects (additive LMDI-I)."
        ),
        epilog=(
            "Input is a long-format CSV with period, segment, activity, energy "
            "and emissions columns. See examples/ for a working file."
        ),
    )
    parser.add_argument("csv", type=Path, help="path to the input CSV")
    parser.add_argument(
        "--from",
        dest="base",
        help="base period label; defaults to the first period in the file",
    )
    parser.add_argument(
        "--to",
        dest="target",
        help="target period label; defaults to the last period in the file",
    )
    parser.add_argument(
        "--series",
        action="store_true",
        help="decompose every consecutive pair of periods instead of just two",
    )
    parser.add_argument(
        "--fixed-base",
        action="store_true",
        help="with --series, compare every period against the first one",
    )
    parser.add_argument(
        "--unit", default="tCO2e", help="emission unit label for the output"
    )
    parser.add_argument(
        "--format",
        choices=("text", "markdown", "json"),
        default="text",
        help="output format",
    )
    parser.add_argument(
        "--output", type=Path, help="write to this file instead of standard output"
    )
    parser.add_argument(
        "--no-segments",
        action="store_true",
        help="omit the per-segment table from text output",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        periods = load_periods(args.csv)
        labels = list(periods)

        if args.series:
            results = decompose_series(periods, chained=not args.fixed_base)
        else:
            base = args.base or labels[0]
            target = args.target or labels[-1]
            for label in (base, target):
                if label not in periods:
                    raise DecompositionError(
                        f"period {label!r} not in file; available: {', '.join(labels)}"
                    )
            if base == target:
                raise DecompositionError("base and target period must differ")
            results = [
                decompose(
                    periods[base],
                    periods[target],
                    base_period=base,
                    target_period=target,
                )
            ]
    except DecompositionError as exc:
        print(f"carbon-bridge: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        text = json.dumps([r.as_dict() for r in results], indent=2)
    elif args.format == "markdown":
        text = to_markdown(results, unit=args.unit)
    else:
        blocks = []
        for result in results:
            block = [summary(result, unit=args.unit), ""]
            if not args.no_segments:
                block += [segment_table(result, unit=args.unit), ""]
            block += ["  " + narrative(result, unit=args.unit), ""]
            blocks.append("\n".join(block))
        text = "\n".join(blocks)

    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"written to {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
