"""Additive LMDI-I decomposition of a change in CO2 emissions.

The identity being decomposed is the Kaya-style factor chain

    E_i = Q * S_i * I_i * F_i

where, for each segment i (facility, product line, country, ...):

    Q    total activity of the portfolio        e.g. tonnes produced
    S_i  structure / mix share, Q_i / Q         dimensionless
    I_i  energy intensity, En_i / Q_i           e.g. MWh per tonne
    F_i  emission factor, E_i / En_i            e.g. tCO2e per MWh

Multiplying the four gives back E_i exactly, so the identity is closed.

The total change between a base period 0 and a target period T,

    dE = E^T - E^0

is split into four additive effects using the Logarithmic Mean Divisia
Index (method I):

    dE_x = sum_i L(E_i^T, E_i^0) * ln(x_i^T / x_i^0)

with L the logarithmic mean

    L(a, b) = (a - b) / (ln a - ln b),   L(a, a) = a.

LMDI-I is *perfect*: the four effects sum back to dE with no residual
term. That property is asserted in the test suite and is the reason this
method is preferred over Laspeyres-style decompositions, which leave an
unexplained interaction residual that has to be arbitrarily allocated.

Reference for the method and for the zero-value handling:
Ang, B.W. (2005), "The LMDI approach to decomposition analysis: a
practical guide", Energy Policy 33(7); Ang & Liu (2007), "Handling zero
values in the logarithmic mean Divisia index decomposition approach",
Energy Policy 35(1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping

# Ang & Liu (2007) show that replacing zeros by a small positive constant
# converges to the analytical limit of the decomposition. Anything in the
# 1e-10 .. 1e-20 range is indistinguishable in practice.
ZERO_SUBSTITUTE = 1e-12

EFFECTS = ("activity", "structure", "intensity", "emission_factor")


class DecompositionError(ValueError):
    """Raised when the input data cannot support a decomposition."""


@dataclass(frozen=True)
class Segment:
    """One reporting segment in one period.

    Attributes
    ----------
    name:      segment label, must match across the two periods
    activity:  physical or economic output (tonnes, units, EUR, ...)
    energy:    energy consumed (MWh, GJ, ...)
    emissions: greenhouse gas emissions (tCO2e)
    """

    name: str
    activity: float
    energy: float
    emissions: float

    def __post_init__(self) -> None:
        for label in ("activity", "energy", "emissions"):
            value = getattr(self, label)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise DecompositionError(
                    f"segment {self.name!r}: {label} must be a number, got {value!r}"
                )
            if math.isnan(value) or math.isinf(value):
                raise DecompositionError(
                    f"segment {self.name!r}: {label} must be finite, got {value!r}"
                )
            if value < 0:
                raise DecompositionError(
                    f"segment {self.name!r}: {label} must be non-negative, got {value}"
                )


@dataclass(frozen=True)
class SegmentEffect:
    """Per-segment contribution of each driver, in emission units."""

    name: str
    base_emissions: float
    target_emissions: float
    activity: float
    structure: float
    intensity: float
    emission_factor: float

    @property
    def total(self) -> float:
        return self.activity + self.structure + self.intensity + self.emission_factor

    @property
    def observed_change(self) -> float:
        return self.target_emissions - self.base_emissions


@dataclass(frozen=True)
class Decomposition:
    """Result of an additive LMDI-I decomposition."""

    base_period: str
    target_period: str
    base_emissions: float
    target_emissions: float
    activity: float
    structure: float
    intensity: float
    emission_factor: float
    segments: tuple[SegmentEffect, ...] = field(default=())

    @property
    def total_change(self) -> float:
        """Observed change, target minus base."""
        return self.target_emissions - self.base_emissions

    @property
    def explained_change(self) -> float:
        """Sum of the four effects. Equals ``total_change`` up to float noise."""
        return self.activity + self.structure + self.intensity + self.emission_factor

    @property
    def residual(self) -> float:
        """Unexplained remainder. Zero by construction for LMDI-I."""
        return self.total_change - self.explained_change

    @property
    def effects(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in EFFECTS}

    def as_dict(self) -> dict[str, object]:
        return {
            "base_period": self.base_period,
            "target_period": self.target_period,
            "base_emissions": self.base_emissions,
            "target_emissions": self.target_emissions,
            "total_change": self.total_change,
            "effects": self.effects,
            "residual": self.residual,
            "segments": [
                {
                    "name": s.name,
                    "base_emissions": s.base_emissions,
                    "target_emissions": s.target_emissions,
                    **{effect: getattr(s, effect) for effect in EFFECTS},
                }
                for s in self.segments
            ],
        }


def logarithmic_mean(a: float, b: float) -> float:
    """Logarithmic mean of two non-negative numbers.

    L(a, b) = (a - b) / (ln a - ln b), with L(a, a) = a and L(x, 0) = 0.

    The logarithmic mean sits between the geometric and arithmetic means,
    which is what makes the LMDI weights add up exactly.
    """
    if a < 0 or b < 0:
        raise DecompositionError(f"logarithmic mean is undefined for negatives: {a}, {b}")
    if a == b:
        return a
    if a == 0.0 or b == 0.0:
        return 0.0
    # Guard against catastrophic cancellation when a and b are very close.
    if abs(a - b) < 1e-12 * max(a, b):
        return 0.5 * (a + b)
    return (a - b) / (math.log(a) - math.log(b))


def _positive(value: float) -> float:
    """Replace an exact zero by a small constant so logs stay defined."""
    return value if value > 0.0 else ZERO_SUBSTITUTE


def _align(
    base: Iterable[Segment], target: Iterable[Segment]
) -> tuple[list[str], dict[str, Segment], dict[str, Segment]]:
    """Index both periods by segment name and take the union of labels.

    A segment that only exists in one period is not an error: it is
    entered with zero values in the other period, which is exactly the
    case the zero-value substitution is designed for (a plant opening or
    closing between the two periods).
    """
    base_map = {s.name: s for s in base}
    target_map = {s.name: s for s in target}
    if len(base_map) != len(list(base_map)) or not base_map:
        raise DecompositionError("base period contains no segments")
    if not target_map:
        raise DecompositionError("target period contains no segments")

    names = list(base_map)
    names.extend(n for n in target_map if n not in base_map)

    zero = lambda name: Segment(name, 0.0, 0.0, 0.0)  # noqa: E731
    for name in names:
        base_map.setdefault(name, zero(name))
        target_map.setdefault(name, zero(name))
    return names, base_map, target_map


def decompose(
    base: Iterable[Segment],
    target: Iterable[Segment],
    *,
    base_period: str = "base",
    target_period: str = "target",
) -> Decomposition:
    """Decompose the emissions change between two periods.

    Parameters
    ----------
    base, target:
        Segment lists for the two periods. Segment names are matched
        across periods; a name present in only one period is treated as
        zero in the other.
    base_period, target_period:
        Labels used in the output only.

    Returns
    -------
    Decomposition
        Portfolio-level and per-segment effects, in the same unit as the
        input emissions.
    """
    names, base_map, target_map = _align(base, target)

    base_activity = sum(base_map[n].activity for n in names)
    target_activity = sum(target_map[n].activity for n in names)
    if base_activity <= 0 or target_activity <= 0:
        raise DecompositionError(
            "total activity must be strictly positive in both periods; "
            f"got {base_activity} and {target_activity}"
        )

    totals = {effect: 0.0 for effect in EFFECTS}
    segment_effects: list[SegmentEffect] = []

    for name in names:
        b, t = base_map[name], target_map[name]

        # Substituting zeros keeps every ratio finite. The substitution has to
        # be applied to the weight as well, not only to the ratios: a segment
        # that appears or disappears between the two periods has a zero on one
        # side, and L(x, 0) = 0 would silently drop its entire contribution and
        # leave it in the residual. With the substitution the four log ratios
        # telescope back to ln(E^T/E^0) exactly, so the decomposition stays
        # perfect and the only error introduced is of the order of the
        # substitute itself.
        b_act, t_act = _positive(b.activity), _positive(t.activity)
        b_energy, t_energy = _positive(b.energy), _positive(t.energy)
        b_emis, t_emis = _positive(b.emissions), _positive(t.emissions)

        weight = logarithmic_mean(t_emis, b_emis)

        contributions = {
            # Q: portfolio-wide activity, identical for every segment.
            "activity": weight * math.log(target_activity / base_activity),
            # S_i = Q_i / Q: how the mix shifted between segments.
            "structure": weight
            * math.log((t_act / target_activity) / (b_act / base_activity)),
            # I_i = En_i / Q_i: energy needed per unit of output.
            "intensity": weight * math.log((t_energy / t_act) / (b_energy / b_act)),
            # F_i = E_i / En_i: carbon content of the energy consumed.
            "emission_factor": weight
            * math.log((t_emis / t_energy) / (b_emis / b_energy)),
        }

        for effect, value in contributions.items():
            totals[effect] += value

        segment_effects.append(
            SegmentEffect(
                name=name,
                base_emissions=b.emissions,
                target_emissions=t.emissions,
                **contributions,
            )
        )

    return Decomposition(
        base_period=base_period,
        target_period=target_period,
        base_emissions=sum(base_map[n].emissions for n in names),
        target_emissions=sum(target_map[n].emissions for n in names),
        segments=tuple(segment_effects),
        **totals,
    )


def decompose_series(
    periods: Mapping[str, Iterable[Segment]],
    *,
    chained: bool = True,
) -> list[Decomposition]:
    """Decompose a multi-period series.

    Parameters
    ----------
    periods:
        Ordered mapping of period label to segment list. Python dicts
        preserve insertion order, so pass them in chronological order.
    chained:
        ``True`` compares each period with the one before it (chained
        decomposition). ``False`` compares every period with the first
        one (fixed-base decomposition).

    Note on chaining: the *total* change telescopes exactly, so chained
    and fixed-base runs always agree on how much emissions moved. The
    split between the four drivers does not. Additive LMDI-I is path
    dependent, so a chained series attributes the change along the route
    actually taken, while a fixed-base run only looks at the endpoints.
    Neither is wrong; chained is the honest choice when the intermediate
    years are real observations rather than interpolation.
    """
    labels = list(periods)
    if len(labels) < 2:
        raise DecompositionError("need at least two periods to decompose a series")

    results = []
    for index in range(1, len(labels)):
        base_label = labels[index - 1] if chained else labels[0]
        target_label = labels[index]
        results.append(
            decompose(
                periods[base_label],
                periods[target_label],
                base_period=base_label,
                target_period=target_label,
            )
        )
    return results
