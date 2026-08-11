# carbon-bridge

Emissions went down 21% last year. Was that decarbonisation, or was it just a
bad year for sales?

`carbon-bridge` answers that. It takes a change in greenhouse gas emissions
between two periods and splits it into four drivers that add up exactly to the
observed change:

| Driver | What it captures | Reads as |
| --- | --- | --- |
| **Activity** | The portfolio produced more or less in total | Growth |
| **Mix / structure** | Output shifted between clean and dirty segments | Portfolio effect |
| **Energy intensity** | Energy consumed per unit of output changed | Efficiency |
| **Emission factor** | Carbon content of the energy consumed changed | Fuel switching, grid mix, PPAs |

The first two describe *what* was produced. The last two describe *how cleanly*
it was produced. Only the last two are decarbonisation.

No dependencies beyond the Python standard library.

## Install

```bash
git clone <this repo>
cd projects/001-carbon-bridge
python3 -m unittest discover -s tests -t .   # 37 tests, no deps needed
```

## Use

Input is a long-format CSV, one row per segment per period:

```csv
period,segment,activity,energy,emissions
2022,Aluminium extrusion,118000,52000,18720
2022,Coating line,64000,21000,7560
2023,Aluminium extrusion,124000,53500,17120
2023,Coating line,69000,21800,6976
```

Units are yours to choose; the tool never converts. Activity can be tonnes,
units, or revenue. Energy can be MWh or GJ. Emissions can be tCO2e or kg.
Column headers are matched case-insensitively and common aliases are accepted
(`year`/`facility`/`production`/`tCO2e`/...), and both `1,234.56` and
`1.234,56` parse correctly.

```bash
python3 -m carbon_bridge.cli examples/manufacturing.csv
```

```
2022 -> 2024
============================================================
  Emissions 2022               34,176.0 tCO2e
  Emissions 2024               26,919.0 tCO2e
  Change                        -7,257.0 tCO2e  (-21.2%)

  Driver contributions
  ----------------------------------------------------------
  Activity                     |####################          +4,362.4 tCO2e
  Mix / structure          ####|                                -846.1 tCO2e
  Energy intensity  ###########|                              -2,256.6 tCO2e
  Emission factor   ##########################################-8,516.7 tCO2e
  ----------------------------------------------------------
  Explained                                                   -7,257.0 tCO2e
  Residual                                                        +0.0 tCO2e
```

Useful flags:

```bash
--from 2022 --to 2024      # pick the periods; defaults to first and last
--series                   # decompose every consecutive pair
--series --fixed-base      # compare every period against the first
--format markdown|json     # instead of the text table
--output report.md         # write to a file
--unit ktCO2e              # relabel the unit
```

As a library:

```python
from carbon_bridge import Segment, decompose

base   = [Segment("Plant A", 120_000, 48_000, 15_600)]
target = [Segment("Plant A", 131_000, 49_500, 14_200)]

result = decompose(base, target, base_period="2023", target_period="2024")
print(result.effects)    # {'activity': ..., 'structure': ..., ...}
print(result.residual)   # ~1e-12
```

## Method

The identity being decomposed is

```
E_i = Q · S_i · I_i · F_i
```

for each segment `i`, where `Q` is total activity, `S_i = Q_i/Q` is the segment's
share, `I_i = En_i/Q_i` is energy intensity and `F_i = E_i/En_i` is the emission
factor. The four terms multiply back to `E_i`, so the identity is closed.

The change is split using the **additive Logarithmic Mean Divisia Index, method I**:

```
ΔE_x = Σ_i  L(E_i^T, E_i^0) · ln(x_i^T / x_i^0)      L(a,b) = (a−b)/(ln a − ln b)
```

LMDI-I is chosen over Laspeyres-style decompositions for one reason: it is
*perfect*. The four effects sum back to the observed change with no residual, so
there is no interaction term left over to allocate by judgement. The test suite
asserts this on 200 randomly generated portfolios, and the `Residual` line in
every report shows what was actually left over — it should always read `+0.0`.

**Zero values.** A plant that opens or closes between the two periods has a zero
on one side, and `ln 0` is undefined. Following Ang & Liu (2007), zeros are
replaced by `1e-12`; the decomposition converges to its analytical limit and the
error introduced is of the order of the substitute itself, which is why the
residual reads `5e-12` rather than exactly zero.

**Chaining is path dependent.** With `--series`, the total change telescopes
exactly, so chained and fixed-base runs always agree on *how much* emissions
moved. They do not agree on the split between the four drivers, because additive
LMDI-I depends on the route taken and not only on the endpoints. This is a
property of the method, not a bug — it is pinned by a test. Chained is the more
honest choice when the intermediate periods are real observations.

**What this is not.** It attributes a change that already happened. It does not
forecast, it does not validate your inventory, and it will faithfully decompose
bad data into four bad numbers. Garbage in, four kinds of garbage out.

## References

- Ang, B.W. (2005). *The LMDI approach to decomposition analysis: a practical guide.* Energy Policy 33(7), 867–871.
- Ang, B.W. & Liu, N. (2007). *Handling zero values in the logarithmic mean Divisia index decomposition approach.* Energy Policy 35(1), 238–246.

## Licence

MIT.
