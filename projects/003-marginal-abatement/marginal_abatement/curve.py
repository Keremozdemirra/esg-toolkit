"""Marginal abatement cost curves.

A MACC ranks emission reduction measures by what each one costs per tonne
avoided, then stacks them into a staircase: cheapest first, cumulative
abatement along the horizontal axis. It is the standard way of showing which
part of a decarbonisation target is nearly free and which part is expensive.

The cost metric is the levelised cost of abatement. Both the cash flows and
the tonnes avoided are discounted over the measure's lifetime:

    LCA = (capex + opex_annual · AF) / (abatement_annual · AF)
        = capex / (abatement_annual · AF) + opex_annual / abatement_annual

where AF is the annuity factor

    AF(r, n) = (1 − (1 + r)^(−n)) / r,    AF(0, n) = n.

Discounting the tonnes as well as the money is a choice, not a law. It is made
here because it keeps the ratio dimensionally honest and makes the metric
independent of when in the lifetime the abatement happens. Undiscounted tonnes
would flatter long-lived measures. Either convention is defensible as long as
it is stated, which is the reason this paragraph exists.

**A measure can have a negative cost.** Insulation, leak repair and lighting
retrofits often pay for themselves: the energy saved is worth more than the
capital spent. These sit below the axis on the curve and are the reason MACCs
are drawn the way they are.

**What a MACC assumes, and where it breaks.** The staircase treats measures as
independent and additive. In reality they interact: insulating a building
reduces the abatement available from a heat pump installed afterwards, because
there is less heat left to decarbonise. Interactions are declared explicitly
via ``excludes`` and ``requires`` rather than left implicit, and the solver
respects them. What the model cannot do is silently correct a curve whose
author never thought about the overlap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


class AbatementError(ValueError):
    """Raised when a measure or a curve cannot be constructed."""


def annuity_factor(rate: float, years: int) -> float:
    """Present value of one unit received annually for ``years`` years.

    Handles a zero discount rate, where the closed form divides by zero but
    the limit is simply the number of years.
    """
    if years <= 0:
        raise AbatementError(f"lifetime must be at least one year, got {years}")
    if rate <= -1:
        raise AbatementError(f"discount rate must exceed -100%, got {rate}")
    if rate == 0:
        return float(years)
    return (1 - (1 + rate) ** -years) / rate


@dataclass(frozen=True)
class Measure:
    """One abatement option.

    Attributes
    ----------
    name:      label
    capex:     up-front capital cost, in currency units
    opex:      annual operating cost *change*; negative means a saving
    abatement: annual emissions avoided, in tonnes
    lifetime:  years over which the measure delivers
    excludes:  measures that cannot be taken alongside this one
    requires:  measures that must be taken before this one
    """

    name: str
    capex: float
    opex: float
    abatement: float
    lifetime: int
    excludes: frozenset[str] = field(default_factory=frozenset)
    requires: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise AbatementError("measure needs a name")
        if self.abatement <= 0:
            raise AbatementError(
                f"{self.name}: annual abatement must be positive, got {self.abatement}. "
                "A measure that avoids nothing does not belong on the curve."
            )
        if self.lifetime <= 0:
            raise AbatementError(f"{self.name}: lifetime must be positive")
        if self.capex < 0:
            raise AbatementError(
                f"{self.name}: negative capex is almost always a sign-convention "
                "error; put savings in opex instead"
            )

    def cost_per_tonne(self, rate: float) -> float:
        """Levelised cost of abatement, currency per tonne."""
        af = annuity_factor(rate, self.lifetime)
        return self.capex / (self.abatement * af) + self.opex / self.abatement

    def lifetime_abatement(self) -> float:
        return self.abatement * self.lifetime

    def npv(self, rate: float) -> float:
        """Net present value of the measure's cash flows, costs negative."""
        return -(self.capex + self.opex * annuity_factor(rate, self.lifetime))


@dataclass(frozen=True)
class Step:
    """One tread of the staircase."""

    measure: Measure
    cost_per_tonne: float
    cumulative_abatement: float

    @property
    def name(self) -> str:
        return self.measure.name

    @property
    def abatement(self) -> float:
        return self.measure.abatement


@dataclass(frozen=True)
class Curve:
    """A marginal abatement cost curve."""

    rate: float
    steps: tuple[Step, ...]

    @property
    def total_abatement(self) -> float:
        return self.steps[-1].cumulative_abatement if self.steps else 0.0

    @property
    def no_regret_abatement(self) -> float:
        """Abatement available at zero or negative cost."""
        return sum(s.abatement for s in self.steps if s.cost_per_tonne <= 0)

    def annual_cost(self) -> float:
        """Annualised cost of taking every measure on the curve."""
        return sum(s.cost_per_tonne * s.abatement for s in self.steps)

    def cost_to_abate(self, tonnes: float) -> tuple[float, list[Step]]:
        """Cheapest annualised cost of abating ``tonnes``, and the measures used.

        Measures are taken whole in cost order until the target is met; the
        last one is prorated, which assumes it can be scaled. If yours cannot,
        read the returned list rather than the number.
        """
        if tonnes < 0:
            raise AbatementError("target abatement cannot be negative")
        if tonnes > self.total_abatement + 1e-9:
            raise AbatementError(
                f"target of {tonnes:,.0f} t exceeds the {self.total_abatement:,.0f} t "
                "available on this curve"
            )
        remaining, cost, used = tonnes, 0.0, []
        for step in self.steps:
            if remaining <= 1e-12:
                break
            take = min(step.abatement, remaining)
            cost += take * step.cost_per_tonne
            remaining -= take
            used.append(step)
        return cost, used

    def carbon_price_unlocking(self, price: float) -> float:
        """Abatement that becomes worth doing at a given carbon price."""
        return sum(s.abatement for s in self.steps if s.cost_per_tonne <= price)


def _check_dependencies(measures: Sequence[Measure]) -> None:
    names = {m.name for m in measures}
    for m in measures:
        unknown = (m.requires | m.excludes) - names
        if unknown:
            raise AbatementError(
                f"{m.name}: refers to unknown measure(s) {', '.join(sorted(unknown))}"
            )
        if m.name in m.requires or m.name in m.excludes:
            raise AbatementError(f"{m.name}: cannot require or exclude itself")


def build_curve(measures: Iterable[Measure], rate: float = 0.05) -> Curve:
    """Order measures by cost per tonne and accumulate the abatement.

    Ties are broken by name so the output is deterministic; two measures at
    the same cost per tonne would otherwise swap places between runs and make
    diffs unreadable.
    """
    measures = list(measures)
    if not measures:
        raise AbatementError("no measures supplied")

    seen = set()
    for m in measures:
        if m.name in seen:
            raise AbatementError(f"duplicate measure name: {m.name}")
        seen.add(m.name)
    _check_dependencies(measures)

    ordered = sorted(measures, key=lambda m: (m.cost_per_tonne(rate), m.name))

    steps, cumulative = [], 0.0
    for m in ordered:
        cumulative += m.abatement
        steps.append(Step(m, m.cost_per_tonne(rate), cumulative))
    return Curve(rate, tuple(steps))


def feasible_selection(curve: Curve, tonnes: float) -> list[Step]:
    """Cheapest set of *whole* measures meeting a target, honouring constraints.

    Greedy in cost order, skipping anything excluded by or missing a
    prerequisite of what has already been chosen. Greedy is optimal for the
    unconstrained divisible case and only approximate here; with exclusions
    the problem is a knapsack. The approximation is stated rather than hidden,
    because a MACC's input uncertainty is usually far larger than the gap to
    the true optimum.
    """
    chosen: list[Step] = []
    taken: set[str] = set()
    blocked: set[str] = set()
    total = 0.0

    for step in curve.steps:
        if total >= tonnes:
            break
        m = step.measure
        if m.name in blocked or not m.requires <= taken:
            continue
        chosen.append(step)
        taken.add(m.name)
        blocked |= m.excludes
        total += m.abatement

    if total < tonnes - 1e-9:
        raise AbatementError(
            f"cannot reach {tonnes:,.0f} t with the feasible measures; "
            f"{total:,.0f} t is the most available under the stated constraints"
        )
    return chosen


def render(curve: Curve, currency: str = "EUR", width: int = 30) -> str:
    """Text rendering of the staircase."""
    if not curve.steps:
        return "(empty curve)"
    costs = [s.cost_per_tonne for s in curve.steps]
    scale = max(max(costs), abs(min(costs)), 1e-9)

    lines = [
        f"Marginal abatement cost curve at a {curve.rate:.1%} discount rate",
        "=" * 78,
        f"  {'Measure':<26}{'Cost/t':>12}{'Abatement':>12}{'Cumulative':>12}",
        "  " + "-" * 74,
    ]
    for s in curve.steps:
        bars = round(abs(s.cost_per_tonne) / scale * width)
        bar = (
            " " * (width - bars) + "#" * bars + "|" + " " * width
            if s.cost_per_tonne < 0
            else " " * width + "|" + "#" * bars + " " * (width - bars)
        )
        lines.append(
            f"  {s.name[:25]:<26}{s.cost_per_tonne:>12,.1f}"
            f"{s.abatement:>12,.0f}{s.cumulative_abatement:>12,.0f}  {bar}"
        )
    lines += [
        "  " + "-" * 74,
        f"  Total abatement          {curve.total_abatement:>12,.0f} t/yr",
        f"  Available at zero cost   {curve.no_regret_abatement:>12,.0f} t/yr",
        f"  Cost of the full curve   {curve.annual_cost():>12,.0f} {currency}/yr",
    ]
    return "\n".join(lines)


# --- exact selection -------------------------------------------------------
#
# feasible_selection above is greedy, and the README walks through a case in
# the example data where greedy loses: it takes a cheap boiler upgrade, which
# excludes a much larger heat pump, and then has to buy expensive abatement to
# make up the shortfall. Documenting that was honest but unsatisfying, so the
# exact solver lives here.

EXHAUSTIVE_LIMIT = 22


def optimal_selection(curve: Curve, tonnes: float) -> list[Step]:
    """Cheapest feasible set of whole measures meeting a target.

    Exhaustive over subsets with pruning, so the answer is exact rather than
    greedy. This is a set-cover-with-conflicts problem and is NP-hard in
    general; the exhaustive route is only viable because real MACCs are small.
    Above ``EXHAUSTIVE_LIMIT`` measures it raises rather than silently
    degrading to greedy, because a caller who asked for the optimum should be
    told when they are not getting it.

    Returns the chosen steps in cost order. Ties are broken toward fewer
    measures, on the view that a plan with fewer moving parts is easier to
    deliver at the same cost.
    """
    if tonnes < 0:
        raise AbatementError("target abatement cannot be negative")
    n = len(curve.steps)
    if n > EXHAUSTIVE_LIMIT:
        raise AbatementError(
            f"exact selection over {n} measures is not tractable here "
            f"(limit {EXHAUSTIVE_LIMIT}); use feasible_selection for a greedy "
            "answer, and note in your write-up that it is approximate"
        )

    steps = list(curve.steps)
    best: tuple[float, int, tuple[int, ...]] | None = None

    # Suffix sums let us abandon a branch as soon as the abatement still
    # available cannot close the remaining gap.
    remaining_available = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        remaining_available[i] = remaining_available[i + 1] + steps[i].abatement

    def recurse(i: int, taken: tuple[int, ...], blocked: frozenset[str],
                abated: float, cost: float) -> None:
        nonlocal best
        if abated >= tonnes - 1e-9:
            candidate = (cost, len(taken), taken)
            if best is None or candidate < best:
                best = candidate
            return
        if i >= n or abated + remaining_available[i] < tonnes - 1e-9:
            return
        # Cost can fall as measures are added (negative-cost measures), so the
        # only sound bound is the one above; no cost-based pruning here.
        if best is not None and cost >= best[0] and all(
            steps[j].cost_per_tonne >= 0 for j in range(i, n)
        ):
            return

        step = steps[i]
        m = step.measure
        if m.name not in blocked and m.requires <= {steps[j].measure.name for j in taken}:
            recurse(
                i + 1,
                taken + (i,),
                blocked | m.excludes,
                abated + step.abatement,
                cost + step.cost_per_tonne * step.abatement,
            )
        recurse(i + 1, taken, blocked, abated, cost)

    recurse(0, (), frozenset(), 0.0, 0.0)

    if best is None:
        raise AbatementError(
            f"cannot reach {tonnes:,.0f} t with any feasible combination of "
            "measures under the stated constraints"
        )
    return [steps[i] for i in best[2]]
