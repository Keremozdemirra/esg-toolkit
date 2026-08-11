# target-path

A target of "42% by 2030" is a single number. The path to it is what determines
whether you make it, and how much carbon ends up in the atmosphere on the way.

`target-path` builds the trajectory, measures where you actually are against it,
and answers the question that matters once you have slipped: *what does the
annual cut have to be from here to still land on the endpoint.*

No dependencies beyond the Python standard library.

## The two pathway shapes

**Absolute contraction** removes a fixed percentage *of the base year* every
year, so the path is a straight line:

```
E(t) = E_base · (1 − r · (t − t_base))
```

This matters more than it sounds. A linear path is strictly harder than a
compounding one at the same headline rate, because a compounding path quietly
shrinks its own annual cut every year. At 4.2% over a decade, linear lands at
58.0% of the base year and compounding at 65.2% — a seven-point gap, from the
same-sounding commitment. There is a test pinning that inequality.

**Intensity convergence** puts a linear path under an intensity metric and
multiplies by your own activity forecast:

```
I(t) = I_base · (1 − r · (t − t_base))      E(t) = I(t) · A(t)
```

With flat activity the two collapse to the same numbers, which is asserted in
the tests. With growth they do not, and that is the point:

```
year,pathway,intensity,actual,gap
2020,100000.0,100.0,,
2021,101548.0,95.8,,
2022,103050.0,91.6,,
```

Intensity is falling on schedule. Absolute emissions are rising. Both statements
are true, and `total_reduction` goes negative rather than reporting progress.

## Use

```bash
python3 -m target_path.cli \
  --base-emissions 100000 --base-year 2020 --target-year 2030 \
  --ambition 1.5C --actuals examples/actuals.csv
```

```
absolute contraction at 4.20% per year
==============================================================
  2020 base            100,000.0 tCO2e
  2030 target           58,000.0 tCO2e
  Total reduction           42.0%
  Cumulative budget     790,000.0 tCO2e

  Year           Pathway        Actual           Gap  Status
  ----------------------------------------------------------
  2020         100,000.0     100,000.0          +0.0  on track
  2023          87,400.0      93,800.0      +6,400.0  behind
  2025          79,000.0      88,400.0      +9,400.0  behind
  2030          58,000.0

  As at 2025: 11.6% below the base year, pathway requires 21.0%.
  To still land on 2030, emissions must now fall 6.88% of today's level every year.
  Cumulative emissions to date are +29,000.0 tCO2e against budget.
```

That last block is the useful part. Five years of visible progress, and the
required annual cut has gone from 4.2% to 6.88% — the arithmetic of delay, which
is invisible if you only track the endpoint.

Other flags: `--rate 0.042` instead of `--ambition`, `--activity` for an
intensity pathway, `--format csv|json`, `--unit`.

As a library:

```python
from target_path import absolute_contraction, assess

path = absolute_contraction(100_000, 2020, 2030, rate=0.042)
a = assess(path, 2025, actual=88_400)

a.on_track                  # False
a.gap                       # +9400.0
a.required_rate_from_here() # 0.0688
path.budget()               # 790000.0
```

## Cumulative budget

`Pathway.budget()` integrates the trajectory rather than reading its endpoint.
Two companies can commit to the same 2030 number and differ by a large margin in
what they actually emit getting there, and the atmosphere responds to the
integral, not the endpoint. `Assessment.cumulative_overshoot()` measures the same
thing against actuals. There is a test showing a company that hits its target
year exactly while having blown its budget — front-loading is invisible to
endpoint compliance and this is how you see it.

## On the reduction rates

The SBTi has published a minimum linear annual reduction of **4.2%** for
1.5°C-aligned near-term Scope 1 and 2 targets, with a lower rate applied to
Scope 3. Those figures are in `REFERENCE_RATES` behind `--ambition`.

**Check the current criteria before relying on them.** SBTi criteria are
versioned and have been revised — the Absolute Contraction Approach was itself
updated — and this repository does not track those releases. The rate is a
plain argument for exactly that reason: pass `--rate` with the number from the
criteria version you are actually working to. Retrieved August 2026 from
[sciencebasedtargets.org](https://sciencebasedtargets.org/).

## What this is not

It is not a validated SBTi submission tool, it does not implement the
sector-specific SDA pathways, and it takes no view on whether your base year,
boundary, or activity forecast is honest. It draws a line and tells you which
side of it you are on.

## Licence

MIT.
