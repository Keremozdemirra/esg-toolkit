# cbam-embedded

A CBAM declarant has to report the emissions embedded in each imported good.
For anything past a simple product that means tracing emissions through a chain:
crude steel carries pig iron, which carries coke and sintered ore, each with its
own process and its own emissions.

`cbam-embedded` resolves that chain and computes **specific embedded emissions**
(SEE) — tCO2e per tonne of good — for every process in an installation.

No dependencies beyond the Python standard library.

## Use

```python
from cbam_embedded import EmissionPair, PrecursorInput, ProductionProcess, resolve, render

processes = [
    ProductionProcess(
        name="coke-oven", good="coke", activity_level=480_000,
        attributed=EmissionPair(direct=312_000),
        electricity_mwh=54_000, electricity_factor=0.31,
    ),
    ProductionProcess(
        name="blast-furnace", good="pig iron", activity_level=900_000,
        attributed=EmissionPair(direct=1_046_000),
        electricity_mwh=126_000, electricity_factor=0.31,
        precursors=(PrecursorInput("coke", 372_000, source="coke-oven"),),
    ),
]

print(render(resolve(processes, "My plant")))
```

```
Embedded emissions — Illustrative integrated steel plant
  Process               Good                Output t  SEE direct  SEE indir.  From prec.
  ------------------------------------------------------------------------------------
  coke-oven             coke                 480,000      0.6500      0.0349         0.0
  sinter-plant          sintered ore       1,250,000      0.2221      0.0294    46,020.0
  blast-furnace         pig iron             900,000      1.7245      0.0967   553,987.1
  bof-steelmaking       crude steel        1,010,000      1.6216      0.1147 1,605,663.8
```

Run the worked example with `PYTHONPATH=. python3 examples/steel_installation.py`.
Its figures are illustrative and come from no published dataset; they exist to
exercise the precursor chain.

## Where the carbon was actually released

The SEE of crude steel says how much carbon a tonne carries. It does not say
whether that carbon came out of the coke oven or the blast furnace — and that
is the question an abatement decision turns on. `render_attribution` splits the
SEE by the process that actually released the emissions:

```python
print(render_attribution(installation.by_name("bof-steelmaking")))
```

```
Origin of embedded emissions — crude steel (bof-steelmaking)
========================================================================
  Released at                           Direct    Indirect     Share
  --------------------------------------------------------------------
  blast-furnace                         1.0126      0.0378     60.5%
  sinter-plant                          0.2221      0.0251     14.2%
  coke-oven                             0.2341      0.0126     14.2%
  bof-steelmaking                       0.1168      0.0298      8.4%
  purchased: iron ore                   0.0337      0.0087      2.4%
  purchased: scrap                      0.0023      0.0008      0.2%
  --------------------------------------------------------------------
  Total (= SEE)                         1.6216      0.1147    100.0%
  tCO2e per tonne of crude steel. Direct and indirect are not summed.
```

Only 8.4% of the carbon in this plant's crude steel is released in the steel
shop. Three fifths of it comes from the blast furnace, and the decarbonisation
argument is therefore about ironmaking, not about the BOF. The totals reproduce
the SEE line from the table above exactly, which is the point of the next
section.

Every entry is keyed by the process that *released* the emissions, not by the
immediate supplier. When a shared input is reached down two different paths —
sinter and coke both feed the blast furnace, and a real bill of materials is
worse than that — the contributions accumulate into a single entry rather than
appearing twice under different intermediates. Purchased precursors are keyed
`purchased: <good>` so they can never collide with a process of the same name.

`result.origin_map` gives the same thing as a dict if you want to compute on it.

## Three decisions worth knowing about

**Direct and indirect never merge.** CBAM reports them separately and the
certificate calculation treats them differently, so `EmissionPair` carries both
end to end. `.total` exists but nothing in the module calls it. Collapsing the
streams early loses information you cannot recover downstream, and a test
asserts they stay distinct.

**A precursor with no stated emissions is refused, not assumed to be zero.**
If a precursor has no source process inside the installation it must carry
`purchased_see` — supplier data, or a default value from the current
implementing act. Silently treating an unstated input as emission-free is the
most reliable way to understate a good, so the constructor raises instead.

**A cycle is an error, not something to iterate.** Precursors form a graph, and
the module resolves it topologically. A circular bill of materials would
converge to a number under fixed-point iteration, and that number would mean
nothing, so `resolve` raises and names the loop.

## The accounting identity

For every process, what leaves equals what was attributed plus what came in:

```
SEE x activity_level  ==  own emissions + embedded emissions of precursors
```

separately for the direct and the indirect stream. `Installation.verify()`
checks it at runtime on every resolve, and the test suite asserts it on 150
randomly generated chains. If it ever fails, the arithmetic has drifted and no
figure downstream can be trusted — which is why it raises rather than warns.

The origin attribution is a *partition* of the SEE, so it carries a second
conservation law:

```
sum over origins of contribution  ==  SEE
```

again separately per stream. Double counting a shared precursor is exactly the
failure mode that would break it, so this is checked at resolve time too rather
than being left to be noticed in a report, and it is swept over its own 150
random chains — this time including purchased precursors, which the first sweep
did not generate.

## Regulatory scope, and what is deliberately missing

The structure follows Regulation (EU) 2023/956 establishing the CBAM and
Implementing Regulation (EU) 2023/1773 on reporting obligations during the
transitional period.

**No default values are bundled, and this is on purpose.** Default values, the
goods scope, and the free allocation adjustment are set by implementing acts,
have been revised more than once, and this repository does not track those
releases. Supply them yourself from the version of the rules you are working
to, and record the date. A tool shipping stale regulatory constants is worse
than one shipping none, because the stale ones look authoritative.

Retrieved August 2026. Verify against the current consolidated text before
relying on any of this.

## What this is not

It does not calculate your certificate liability (that is `002-certificate-cost`),
does not screen CN codes for scope, does not validate your installation data,
has no CLI and reads no input files yet — it is a library you drive from Python —
and is not a substitute for a verifier or for advice from someone accountable
for your declaration. It resolves a graph and does arithmetic on the numbers you
give it.

## Licence

MIT.
