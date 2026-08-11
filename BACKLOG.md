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
- [x] **002 — target-path** · Absolute-contraction and intensity-convergence pathways, gap assessment, rebased required rate, cumulative budget. 27 tests, zero dependencies.
- [x] **003 — marginal-abatement** · Levelised cost of abatement, cost curve, carbon-price unlocking, and a constrained greedy solver with its suboptimality documented and tested. 35 tests, zero dependencies.

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
- [ ] **011 — cbam-calc** · CBAM embedded-emissions calculation for imported goods, default values vs actual data, and the certificate cost under a given EU ETS price path.
- [ ] **012 — dpp-schema** · Digital Product Passport data model: schema, validation and a round-trip export, built against the ESPR data requirements.
- [ ] **013 — assurance-trail** · Turn a spreadsheet of sustainability figures into a numbered evidence register with sources, owners, calculation notes and open queries.

### Circularity and life-cycle

- [ ] **014 — lca-lite** · Attributional cradle-to-gate LCA from a bill of materials with a pluggable factor database, contribution analysis and a proper uncertainty range.
- [ ] **015 — circularity-index** · Material Circularity Indicator for a product: virgin vs recycled input, utility, end-of-life recovery, and where the biggest lever sits.
- [ ] **016 — packaging-fees** · Extended producer responsibility fee modelling across several jurisdictions from a packaging specification.

### Valuation and financial modelling

- [ ] **017 — dcf-lab** · Transparent DCF: driver-based projection, WACC build-up, Gordon and exit-multiple terminal values, and a sensitivity grid that shows how little of the answer comes from the forecast period.
- [ ] **018 — scenario-engine** · Define scenarios as named parameter overlays over a base model, run them all, and report the spread rather than a single point estimate.
- [ ] **019 — carbon-price-var** · Value at risk from carbon pricing: exposure by scope and jurisdiction against a set of price paths, with the internal carbon price that would neutralise it.
- [ ] **020 — green-premium** · Compare the all-in cost of a low-carbon option against its conventional alternative, and express the gap as a required carbon price.
- [ ] **021 — payback-ladder** · Rank capital projects by discounted payback, IRR and abatement, and show where the three orderings disagree.
- [ ] **022 — portfolio-optimiser** · Mean-variance optimisation with a carbon-intensity constraint, and the efficient frontier you give up to meet it.
- [ ] **023 — waterfall** · Build a bridge chart from any two-period dataset — revenue, cost, headcount, emissions — with the arithmetic checked rather than hand-typed.

### Analysis and research tooling

- [ ] **024 — cohort-retention** · Cohort tables and retention curves from a transaction log, with the survivorship traps flagged rather than hidden.
- [ ] **025 — market-sizer** · Top-down and bottom-up market sizing side by side, forced to reconcile, with every assumption sourced.
- [ ] **026 — benford-check** · Screen a set of reported figures against Benford's law and flag what deserves a second look, with an honest note on the method's false-positive rate.
- [ ] **027 — survey-weights** · Post-stratification and raking for survey data, with design effect and effective sample size reported so nobody quotes a margin of error that does not exist.
- [ ] **028 — unit-guard** · Catch unit errors in analytical spreadsheets: dimensional analysis over a formula graph, so kWh never gets added to MWh again.
- [ ] **029 — sankey-flow** · Material and energy flow diagrams from a flow table, with the mass balance actually enforced.
- [ ] **030 — assumption-log** · Extract hardcoded numbers from a model, register them with a source and a review date, and report which ones have gone stale.
