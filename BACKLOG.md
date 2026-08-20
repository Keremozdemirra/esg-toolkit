# Backlog

Working queue. The next unchecked item is the one being built. An item stays
unchecked and picks up a `status:` note if it spans more than one working
session — finishing something half-built takes priority over starting the next
one.

Rules of thumb applied to every item:

- one job per tool, done properly, rather than a suite of half-features
- standard library unless a dependency earns its place
- tests that assert a real property, not that the code ran
- a README that says what the tool is *not* for
- any published factor, threshold or rate gets a citation and a vintage

---

## Done

- [x] **001 — carbon-bridge** · Additive LMDI-I decomposition of an emissions change into activity, mix, intensity and emission-factor effects. 37 tests, zero dependencies.
- [x] **002 — target-path** · Absolute-contraction and intensity-convergence pathways, gap assessment, rebased required rate, cumulative budget. Extended with budget-preserving rebasing: the closed-form rate that keeps cumulative emissions inside the original budget rather than merely landing on the endpoint, with the conservation law under test. 39 tests, zero dependencies.
- [x] **003 — marginal-abatement** · Levelised cost of abatement, cost curve, carbon-price unlocking, a greedy solver and an exact one that provably never costs more. 46 tests, zero dependencies.

- [x] **004 — embedded-emissions** · Specific embedded emissions per tonne of a CBAM good, with topological precursor resolution, cycle detection, a runtime accounting-identity check and origin attribution that does not double count a shared precursor. Moved here from the cbam-calc repository, where it was built; CBAM is EU sustainability regulation and belongs under this roof rather than in a repository of its own. 36 tests, zero dependencies.

## Queue

### Emissions and energy

- [ ] **003 — scope2-dual** · Location-based vs market-based Scope 2 accounting side by side, with contractual instruments (PPAs, RECs, GOs) applied under GHG Protocol Scope 2 Guidance quality criteria.
- [ ] **005 — energy-baseline** · Weather-normalise energy consumption against heating and cooling degree days so efficiency claims survive a mild winter.
- [ ] **006 — grid-intensity** · Time-matched vs annual-matched clean electricity accounting: hourly load against hourly grid intensity, and what 24/7 matching would actually cost.
- [ ] **007 — fleet-transition** · Total cost of ownership and abatement for replacing a vehicle fleet, with residual value, charging infrastructure and duty-cycle constraints.

### Reporting, disclosure and compliance

- [ ] **008 — materiality-matrix** · Double-materiality assessment as data rather than a slide: impact and financial scores per topic, stakeholder weighting, sensitivity of the threshold, and an auditable trail of who scored what.
- [ ] **009 — disclosure-diff** · Diff two sustainability reports and surface what changed: restated figures, dropped metrics, quietly moved baselines.
- [ ] **010 — taxonomy-screen** · EU Taxonomy eligibility and alignment screening for a revenue/capex/opex breakdown, including the do-no-significant-harm gates and minimum safeguards checklist.

- [ ] **012 — dpp-schema** · Digital Product Passport data model: schema, validation and a round-trip export, built against the ESPR data requirements.
- [ ] **013 — assurance-trail** · Turn a spreadsheet of sustainability figures into a numbered evidence register with sources, owners, calculation notes and open queries.

### Circularity and life-cycle

- [ ] **014 — lca-lite** · Attributional cradle-to-gate LCA from a bill of materials with a pluggable factor database, contribution analysis and a proper uncertainty range.
- [ ] **015 — circularity-index** · Material Circularity Indicator for a product: virgin vs recycled input, utility, end-of-life recovery, and where the biggest lever sits.
- [ ] **016 — packaging-fees** · Extended producer responsibility fee modelling across several jurisdictions from a packaging specification.

### Valuation and financial modelling

- [ ] **019 — carbon-price-var** · Value at risk from carbon pricing: exposure by scope and jurisdiction against a set of price paths, with the internal carbon price that would neutralise it.
- [ ] **020 — green-premium** · Compare the all-in cost of a low-carbon option against its conventional alternative, and express the gap as a required carbon price.
- [ ] **021 — payback-ladder** · Rank capital projects by discounted payback, IRR and abatement, and show where the three orderings disagree.
- [ ] **022 — portfolio-optimiser** · Mean-variance optimisation with a carbon-intensity constraint, and the efficient frontier you give up to meet it.

### Analysis and research tooling

- [ ] **029 — sankey-flow** · Material and energy flow diagrams from a flow table, with the mass balance actually enforced.

---

## Moved out of this queue

This backlog was the original list, and three repositories were carved out of it
afterwards without it being pruned. The following items describe work that now
belongs elsewhere. Two of them had already been built there, so leaving them
here would have had the daily loop build the same thing twice.

| Item | Now lives in | Status |
| --- | --- | --- |
| 017 — dcf-lab | `analyst-toolkit` | built there on 2026-08-19 |
| 018 — scenario-engine | `analyst-toolkit` | queued there |
| 023 — waterfall | `analyst-toolkit` | queued there |
| 024 — cohort-retention | `analyst-toolkit` | queued there |
| 025 — market-sizer | `analyst-toolkit` | built there |
| 026 — benford-check | `analyst-toolkit` | moved there by this change |
| 027 — survey-weights | `analyst-toolkit` | queued there |
| 028 — unit-guard | `unitguard` | the whole repository is this |
| 030 — assumption-log | `analyst-toolkit` | queued there |

What remains here is deliberately sustainability and climate work. Where an item
needs a general analytical tool, it uses the one in `analyst-toolkit` rather
than growing its own; where it needs units, it uses `unitguard`.
