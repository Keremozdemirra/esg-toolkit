# marginal-abatement

Which parts of your decarbonisation plan pay for themselves, and what does the
rest actually cost?

`marginal-abatement` builds a MACC: measures ranked by cost per tonne avoided,
stacked cheapest-first into a staircase. Measures that save more than they cost
sit below the axis. It also answers the two follow-up questions — what a given
carbon price makes worth doing, and the cheapest feasible route to a target
when measures block or depend on each other.

No dependencies beyond the Python standard library.

## Use

```bash
python3 -m marginal_abatement.cli examples/measures.csv --carbon-price 80 --target 3000
```

```
Marginal abatement cost curve at a 5.0% discount rate
  Measure                         Cost/t   Abatement  Cumulative
  --------------------------------------------------------------------------
  Compressed air leak repair       -94.5         140         140      ######|
  LED lighting retrofit            -82.9         310         450       #####|
  Variable speed drives            -44.9         240         690         ###|
  Building envelope insulation     -24.2         520       1,210          ##|
  Rooftop solar PV                   7.7       1,420       2,630            |
  Gas boiler efficiency upgrade     24.3         260       2,890            |##
  Heat pump replacing gas boiler    40.2       1,850       4,740            |###
  Process electrification          153.8       2,600       7,340            |##########
  On-site battery storage          386.4         190       7,530            |########################
  Green hydrogen for process heat  477.6       1,900       9,430            |##############################
  --------------------------------------------------------------------------
  Total abatement                 9,430 t/yr
  Available at zero cost          1,210 t/yr
  Cost of the full curve      1,410,226 EUR/yr

  At 80 EUR/t, 4,740 t/yr of abatement pays for itself (50% of the curve).
```

Input is a CSV of measures. `opex` is the annual operating cost *change*, so
energy savings are negative. `excludes` and `requires` are semicolon-separated
lists of other measure names.

```csv
name,capex,opex,abatement,lifetime,excludes,requires
LED lighting retrofit,180000,-46000,310,12,,
Heat pump replacing gas boiler,1450000,-42000,1850,20,Gas boiler efficiency upgrade,Building envelope insulation
```

## The cost metric

Levelised cost of abatement, discounting both the money and the tonnes over the
measure's lifetime:

```
LCA = capex / (abatement · AF) + opex / abatement        AF(r,n) = (1−(1+r)^−n)/r
```

Discounting the tonnes as well as the cash is a convention, not a law. It is
used here because it makes the metric independent of *when* in the lifetime the
abatement lands; undiscounted tonnes would flatter long-lived measures. Either
choice is defensible if stated, so it is stated. One consequence worth knowing:
a measure with no capex has a cost per tonne that does not move with the
discount rate at all, because the annuity factor cancels. There is a test for
that.

`annuity_factor` handles a zero discount rate, where the closed form divides by
zero and the limit is just the number of years.

## Where the greedy solver gives up ground

Run the example with `--target 3000` and watch what happens:

```
    - Gas boiler efficiency upgrade           260 t        24.3/t
    - Process electrification               2,600 t       153.8/t
```

The solver took a cheap 260-tonne boiler upgrade, which excluded the heat pump —
1,850 tonnes at 40.2/t — and then had to reach for process electrification at
153.8/t to make up the difference. A better plan exists and greedy did not find
it.

With mutually exclusive options this is a set-cover-with-conflicts problem and
greedy is only an approximation.

`optimal_selection` solves it exactly, and on this data the gap is not small:

| Target | Greedy | Optimal | Saving |
| ---: | ---: | ---: | ---: |
| 3,000 t | 354,955 | 12,076 | 97% |
| 5,000 t | 354,955 | 348,646 | 2% |
| 7,000 t | 1,335,874 | 422,998 | 68% |

At 3,000 t the optimal plan simply skips the boiler upgrade and takes the heat
pump, which is obvious in hindsight and invisible to a cost-ordered walk.

The exact solver is exhaustive with pruning and is only viable because real
MACCs are small. Above 22 measures it **raises rather than quietly falling back
to greedy** — a caller who asked for the optimum should be told when they are
not getting it. Use `feasible_selection` when you want the greedy answer
knowingly, and say in your write-up that it is approximate.

A test asserts `optimal_selection` never costs more than `feasible_selection`,
on this dataset and on forty randomly generated curves. That property is the
solver's entire justification, so it is pinned rather than assumed.

## What a MACC assumes

The staircase treats measures as independent and additive, which they are not.
Insulate a building and the heat pump you install afterwards has less heat left
to decarbonise, so its abatement is smaller than the standalone figure. This
tool lets you declare those relationships with `excludes` and `requires` and
honours them, but it cannot correct a curve whose author never noticed the
overlap. That remains the analyst's job, and it is where most bad MACCs go
wrong.

## What this is not

It does not source cost data, validate your abatement estimates, or model
implementation risk, ramp-up time, or capital constraints. Every number in the
input file is an assumption someone made, and the curve is only as good as the
worst of them.

## Licence

MIT.
