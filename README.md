# esg-toolkit

Small, focused tools for sustainability and financial analysis. Each one does a
single job that would otherwise be a fragile spreadsheet, and each one is
self-contained: its own folder, its own README, its own tests, no shared
framework to learn.

Most of them lean on the standard library only. Where a dependency is genuinely
needed it is declared in that project's `pyproject.toml` and nowhere else.

## Projects

| # | Project | What it does |
| --- | --- | --- |
| 001 | [carbon-bridge](projects/001-carbon-bridge) | Splits a change in emissions into activity, mix, energy-intensity and emission-factor effects (additive LMDI-I), so you can tell decarbonisation apart from a slow year. |
| 002 | [target-path](projects/002-target-path) | Builds absolute-contraction and intensity-convergence target pathways, measures actuals against them, and reports the annual cut still needed after a slip — both to reach the endpoint and to stay inside the cumulative budget, which are not the same number. |
| 003 | [marginal-abatement](projects/003-marginal-abatement) | Builds a marginal abatement cost curve, shows what a carbon price unlocks, and finds the cheapest feasible route to a target under exclusion and prerequisite constraints. |

## Why these exist

Sustainability and corporate finance work runs on spreadsheets that are copied,
edited and re-copied until nobody can say where a number came from. The tools
here take the small analytical steps that recur in that work — decomposing a
change, running a scenario, checking a disclosure against a framework — and give
them a tested implementation with a readable audit trail.

Anything that depends on published emission factors, regulatory thresholds or
market data cites its source in that project's README, with the vintage of the
data. Figures go stale; the citation is how you find out.

## Layout

```
projects/
  NNN-project-name/
    README.md          what it does, how to run it, what it is not
    <package>/         the implementation
    tests/             python3 -m unittest discover -s tests -t .
    examples/          a working input file
    pyproject.toml     dependencies, if any
```

## Roadmap

See [BACKLOG.md](BACKLOG.md).

## Licence

MIT, per project. See [LICENSE](LICENSE).
