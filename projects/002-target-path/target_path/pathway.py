"""Science-based target pathways and progress assessment.

Two pathway shapes are implemented.

**Absolute contraction.** Emissions fall by a fixed percentage *of the base
year* every year, so the path is a straight line rather than a decaying
exponential:

    E(t) = E_base · (1 − r · (t − t_base))

This is the shape the SBTi's Absolute Contraction Approach uses. A linear
path is strictly more demanding than a compounding one at the same headline
rate, because a compounding path shrinks its own annual cut every year.

**Intensity convergence.** A physical or economic intensity falls linearly
while activity follows its own trajectory, so absolute emissions are the
product of the two:

    I(t) = I_base · (1 − r · (t − t_base))
    E(t) = I(t) · A(t)

An intensity target can be met while absolute emissions rise. That is not a
flaw in the arithmetic, it is the reason intensity targets are contested, and
``assess`` reports both numbers so the difference cannot hide.

On the reduction rates: the SBTi has published a minimum linear annual
reduction of 4.2% for 1.5°C-aligned Scope 1 and 2 near-term targets, with a
lower rate applied to Scope 3. Those criteria are versioned and have been
revised, so this module takes the rate as an explicit argument and treats the
constants in ``REFERENCE_RATES`` as a starting point to be checked against the
current criteria, not as an authority. Sources and vintage are in the README.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

# Indicative only. Check the current SBTi criteria version before using these
# for anything that matters; see README for sources and retrieval date.
REFERENCE_RATES: dict[str, float] = {
    "1.5C": 0.042,
    "well-below-2C": 0.025,
}


class TargetError(ValueError):
    """Raised when a pathway or assessment cannot be constructed."""


@dataclass(frozen=True)
class Point:
    """One year on a pathway."""

    year: int
    emissions: float
    intensity: float | None = None
    activity: float | None = None


@dataclass(frozen=True)
class Pathway:
    """A target trajectory between a base year and a target year."""

    kind: str
    base_year: int
    target_year: int
    rate: float
    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if not self.points:
            raise TargetError("pathway has no points")

    @property
    def base_emissions(self) -> float:
        return self.points[0].emissions

    @property
    def target_emissions(self) -> float:
        return self.points[-1].emissions

    @property
    def total_reduction(self) -> float:
        """Fraction of base-year emissions removed by the target year."""
        if self.base_emissions == 0:
            raise TargetError("base-year emissions are zero")
        return 1.0 - self.target_emissions / self.base_emissions

    def at(self, year: int) -> Point:
        for point in self.points:
            if point.year == year:
                return point
        raise TargetError(
            f"year {year} is outside the pathway "
            f"({self.base_year}-{self.target_year})"
        )

    def budget(self) -> float:
        """Cumulative emissions allowed under the pathway.

        Integrated with the trapezoidal rule over annual points, which is
        exact for a straight line. Two companies can share an endpoint and
        still differ here, and it is the cumulative figure that the
        atmosphere responds to.
        """
        values = [p.emissions for p in self.points]
        return sum(values) - 0.5 * (values[0] + values[-1])


def _validate(base_year: int, target_year: int, rate: float) -> int:
    if target_year <= base_year:
        raise TargetError(
            f"target year {target_year} must be after base year {base_year}"
        )
    if not 0 < rate < 1:
        raise TargetError(f"annual reduction rate must be in (0, 1), got {rate}")
    span = target_year - base_year
    if rate * span >= 1:
        raise TargetError(
            f"a {rate:.1%} linear cut over {span} years reaches zero or below; "
            "shorten the horizon or lower the rate"
        )
    return span


def absolute_contraction(
    base_emissions: float,
    base_year: int,
    target_year: int,
    rate: float,
) -> Pathway:
    """Linear absolute-contraction pathway.

    ``rate`` is expressed as a fraction of *base-year* emissions removed each
    year, so 0.042 means 4.2 percentage points of the base year annually, not
    4.2% of the previous year.
    """
    if base_emissions <= 0:
        raise TargetError(f"base emissions must be positive, got {base_emissions}")
    span = _validate(base_year, target_year, rate)

    points = tuple(
        Point(year=base_year + n, emissions=base_emissions * (1 - rate * n))
        for n in range(span + 1)
    )
    return Pathway("absolute_contraction", base_year, target_year, rate, points)


def intensity_convergence(
    base_intensity: float,
    activity: Mapping[int, float],
    base_year: int,
    target_year: int,
    rate: float,
) -> Pathway:
    """Linear intensity pathway multiplied by a given activity trajectory.

    ``activity`` must cover every year from base to target inclusive. The
    activity forecast is the user's, not the model's: this function will not
    interpolate a missing year, because a silently interpolated activity
    projection is exactly the kind of assumption that later gets quoted as a
    result.
    """
    if base_intensity <= 0:
        raise TargetError(f"base intensity must be positive, got {base_intensity}")
    span = _validate(base_year, target_year, rate)

    missing = [y for y in range(base_year, target_year + 1) if y not in activity]
    if missing:
        raise TargetError(
            f"activity is missing for {len(missing)} year(s): "
            f"{', '.join(str(y) for y in missing[:5])}"
            + (" ..." if len(missing) > 5 else "")
        )

    points = []
    for n in range(span + 1):
        year = base_year + n
        intensity = base_intensity * (1 - rate * n)
        points.append(
            Point(
                year=year,
                emissions=intensity * activity[year],
                intensity=intensity,
                activity=activity[year],
            )
        )
    return Pathway("intensity_convergence", base_year, target_year, rate, tuple(points))


@dataclass(frozen=True)
class Assessment:
    """Actual performance measured against a pathway in a given year."""

    year: int
    actual: float
    required: float
    pathway: Pathway

    @property
    def gap(self) -> float:
        """Actual minus required. Positive means behind the pathway."""
        return self.actual - self.required

    @property
    def on_track(self) -> bool:
        return self.gap <= 0

    @property
    def achieved_reduction(self) -> float:
        """Fraction of base-year emissions actually removed so far."""
        return 1.0 - self.actual / self.pathway.base_emissions

    def required_rate_from_here(self) -> float:
        """Linear rate, as a fraction of *current* emissions, still needed.

        Rebasing on today rather than on the original base year answers the
        question that actually matters once a company is off track: what does
        it now have to do every year to still land on the endpoint.
        """
        years_left = self.pathway.target_year - self.year
        if years_left <= 0:
            raise TargetError("the target year has already been reached")
        if self.actual <= 0:
            raise TargetError("current emissions must be positive")
        return (self.actual - self.pathway.target_emissions) / (self.actual * years_left)

    def cumulative_overshoot(self, actuals: Mapping[int, float]) -> float:
        """Cumulative emissions above the pathway across the years supplied.

        Endpoint compliance says nothing about the area under the curve. A
        company can hit its target year exactly and still have emitted well
        above its budget getting there.
        """
        overshoot = 0.0
        for year, value in sorted(actuals.items()):
            if year < self.pathway.base_year or year > self.pathway.target_year:
                raise TargetError(f"year {year} is outside the pathway")
            overshoot += value - self.pathway.at(year).emissions
        return overshoot


    def spent(self, actuals: Mapping[int, float]) -> float:
        """Cumulative emissions actually released from the base year to now.

        Integrated the same way as :meth:`Pathway.budget`, so the two are
        directly comparable. Every year from the base year to the assessment
        year must be present: a gap would silently shrink the integral and make
        the overspend look smaller than it was, which is the one direction this
        number must never err in.
        """
        wanted = list(range(self.pathway.base_year, self.year + 1))
        missing = [y for y in wanted if y not in actuals]
        if missing:
            raise TargetError(
                "cannot integrate actual emissions: missing "
                f"{', '.join(str(y) for y in missing)}. A missing year would "
                "understate the carbon already spent."
            )
        values = [float(actuals[y]) for y in wanted]
        if len(values) == 1:
            return 0.0
        return sum(values) - 0.5 * (values[0] + values[-1])

    def remaining_budget(self, actuals: Mapping[int, float]) -> float:
        """Original cumulative budget less what has already been spent.

        The trapezoidal rule is additive across a shared node, so the original
        budget splits exactly into the part before this year and the part
        after. That is what makes this subtraction meaningful rather than
        approximate.
        """
        return self.pathway.budget() - self.spent(actuals)

    def budget_preserving_rate(self, actuals: Mapping[int, float]) -> float:
        """Linear rate, on today's emissions, that stays inside the original budget.

        :meth:`required_rate_from_here` rebases on the *endpoint*: it asks what
        it takes to still arrive at the target number. That question ignores
        the carbon already overspent, and the atmosphere responds to the area
        under the curve, not to the last point on it. A company can land on its
        target year exactly and have emitted far more than the pathway allowed.

        This asks the other question: what rate keeps *cumulative* emissions
        within the budget the original pathway implied. Closing the integral of
        a linear path over the remaining ``n`` years gives

            future budget = E_now · n · (1 − r·n/2)

        so setting that equal to the remaining allowance ``R`` yields a closed
        form, with no search:

            r = (2/n) · (1 − R / (E_now · n))

        A rate at or below zero is returned as-is and means the budget has room
        for emissions to stay flat or rise; it is a real answer, not an error,
        and callers that need a constructible pathway should use
        :meth:`budget_preserving_pathway` instead.
        """
        years_left = self.pathway.target_year - self.year
        if years_left <= 0:
            raise TargetError("the target year has already been reached")
        if self.actual <= 0:
            raise TargetError("current emissions must be positive")
        remaining = self.remaining_budget(actuals)
        return (2.0 / years_left) * (1.0 - remaining / (self.actual * years_left))

    def budget_preserving_pathway(self, actuals: Mapping[int, float]) -> Pathway:
        """The budget-preserving path itself, rebased on today.

        Raises rather than clamping when the budget cannot be preserved: if the
        allowance is already spent, no future trajectory recovers it, and
        saying so is more useful than returning a path to zero.
        """
        rate = self.budget_preserving_rate(actuals)
        years_left = self.pathway.target_year - self.year
        if rate <= 0:
            raise TargetError(
                f"cumulative emissions are inside the budget with room to spare: "
                f"the budget-preserving rate is {rate:.2%}, i.e. emissions could "
                "hold flat or rise. There is no contraction pathway to build."
            )
        if rate * years_left >= 1:
            raise TargetError(
                f"the budget cannot be preserved: it would take a {rate:.1%} "
                f"annual cut over {years_left} years, which reaches zero or "
                "below. The remaining allowance is "
                f"{self.remaining_budget(actuals):,.1f} against current "
                f"emissions of {self.actual:,.1f}."
            )
        return absolute_contraction(
            self.actual, self.year, self.pathway.target_year, rate
        )


def assess(pathway: Pathway, year: int, actual: float) -> Assessment:
    """Compare actual emissions in ``year`` against the pathway."""
    if actual < 0:
        raise TargetError(f"actual emissions must be non-negative, got {actual}")
    return Assessment(year, actual, pathway.at(year).emissions, pathway)


def required_rate(
    base_emissions: float,
    target_emissions: float,
    base_year: int,
    target_year: int,
) -> float:
    """The linear rate that connects a starting point to a required endpoint."""
    if base_emissions <= 0:
        raise TargetError("base emissions must be positive")
    span = target_year - base_year
    if span <= 0:
        raise TargetError("target year must be after base year")
    return (base_emissions - target_emissions) / (base_emissions * span)


def compare(pathways: Sequence[Pathway]) -> list[tuple[str, float, float, float]]:
    """Rows of (label, endpoint, total reduction, cumulative budget)."""
    rows = []
    for p in pathways:
        label = f"{p.kind} @ {p.rate:.1%}"
        rows.append((label, p.target_emissions, p.total_reduction, p.budget()))
    return rows


def to_rows(pathway: Pathway) -> Iterable[tuple[int, float, float | None]]:
    for point in pathway.points:
        yield point.year, point.emissions, point.intensity
