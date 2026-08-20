"""Embedded emissions of CBAM goods, from installation-level data.

The quantity a CBAM declarant has to report is the **specific embedded
emissions** (SEE) of each good: the emissions attributable to one tonne of it,
counted from the production process that made it plus everything carried in
through its precursors.

    SEE = attributed emissions / activity level

where the activity level is the tonnage produced in the reporting period and
the attributed emissions include the embedded emissions of the precursors
consumed. Direct and indirect are carried separately end to end, because they
are reported separately and are treated differently in the certificate
calculation — collapsing them into one number early is the most common way to
lose information that cannot be recovered later.

**Precursors make this a graph, not a formula.** Steel is made from sinter and
pig iron, which are made from ore and coke, each with its own process and its
own emissions. Embedded emissions propagate along that graph, and the graph
must be resolved in dependency order. This module resolves it topologically and
refuses to proceed on a cycle rather than silently iterating to a fixed point,
because a cycle in a bill of materials is a data error, not a physical fact
about the plant.

**Accounting identity.** For any process, what leaves equals what was attributed
plus what came in:

    SEE_total x activity_level  ==  attributed emissions + embedded emissions of precursors

This holds exactly and separately for the direct and indirect streams. The test
suite asserts it on every process of every fixture, and `Installation.verify()`
asserts it at runtime, because a violation means the arithmetic has drifted and
no downstream number can be trusted.

**Regulatory scope and what is deliberately absent.** The structure follows
Regulation (EU) 2023/956 establishing the CBAM and Implementing Regulation (EU)
2023/1773 on reporting obligations during the transitional period. No default
values are bundled. Default values, the goods scope, and the free allocation
adjustment are set by implementing acts, have been revised, and this module does
not track those releases. Supply them yourself, from the version of the rules
you are actually working to, with its date. A tool that ships stale regulatory
constants is worse than one that ships none, because the stale ones look
authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

TOLERANCE = 1e-6


class CbamError(ValueError):
    """Raised when embedded emissions cannot be computed from the data given."""


@dataclass(frozen=True)
class EmissionPair:
    """Direct and indirect emissions kept apart.

    CBAM reports the two separately and the certificate calculation treats them
    differently, so they never collapse into a single figure inside this module.
    """

    direct: float = 0.0
    indirect: float = 0.0

    def __post_init__(self) -> None:
        for label in ("direct", "indirect"):
            value = getattr(self, label)
            if value < 0:
                raise CbamError(f"{label} emissions cannot be negative, got {value}")

    @property
    def total(self) -> float:
        return self.direct + self.indirect

    def __add__(self, other: "EmissionPair") -> "EmissionPair":
        return EmissionPair(self.direct + other.direct, self.indirect + other.indirect)

    def scaled(self, factor: float) -> "EmissionPair":
        return EmissionPair(self.direct * factor, self.indirect * factor)


@dataclass(frozen=True)
class PrecursorInput:
    """A quantity of a precursor good consumed by a process.

    ``source`` names the process that produced it, if that process is part of
    this installation. If it is empty the precursor was purchased, and
    ``purchased_see`` must carry its specific embedded emissions — supplier
    data, or a default value from the current implementing act.
    """

    good: str
    quantity: float
    source: str = ""
    purchased_see: EmissionPair | None = None

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise CbamError(f"{self.good}: quantity cannot be negative")
        if not self.source and self.purchased_see is None:
            raise CbamError(
                f"{self.good}: a precursor with no source process must carry "
                "purchased_see. Refusing to assume it is emission-free — an "
                "unstated precursor is the single most common way embedded "
                "emissions get understated."
            )


@dataclass(frozen=True)
class ProductionProcess:
    """One production process within an installation.

    Attributes
    ----------
    name:            process identifier, referenced by downstream precursors
    good:            the CBAM good produced
    activity_level:  tonnes produced in the reporting period
    attributed:      emissions attributed to this process, excluding precursors
    electricity_mwh: electricity consumed
    electricity_factor: tCO2e per MWh applied to that electricity
    precursors:      what the process consumed
    """

    name: str
    good: str
    activity_level: float
    attributed: EmissionPair = field(default_factory=EmissionPair)
    electricity_mwh: float = 0.0
    electricity_factor: float = 0.0
    precursors: tuple[PrecursorInput, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise CbamError("process needs a name")
        if self.activity_level <= 0:
            raise CbamError(
                f"{self.name}: activity level must be positive, got "
                f"{self.activity_level}. Specific emissions are undefined for a "
                "process that produced nothing."
            )
        if self.electricity_mwh < 0 or self.electricity_factor < 0:
            raise CbamError(f"{self.name}: electricity figures cannot be negative")

    def electricity_emissions(self) -> EmissionPair:
        """Indirect emissions from purchased electricity."""
        return EmissionPair(0.0, self.electricity_mwh * self.electricity_factor)

    def own_emissions(self) -> EmissionPair:
        """Everything attributed to this process before precursors."""
        return self.attributed + self.electricity_emissions()


PURCHASED = "purchased: "


@dataclass(frozen=True)
class ProcessResult:
    """Resolved embedded emissions for one process.

    ``origins`` answers the question the SEE figure cannot: of the emissions in
    one tonne of this good, how much was released *here* and how much arrived
    from each upstream process. It is held as a tuple of pairs rather than a
    dict so the result stays frozen; use :attr:`origin_map` for the mapping.
    """

    process: ProductionProcess
    see: EmissionPair
    inherited: EmissionPair
    origins: tuple[tuple[str, EmissionPair], ...] = ()

    @property
    def origin_map(self) -> dict[str, EmissionPair]:
        return dict(self.origins)

    def origin_total(self) -> EmissionPair:
        """Sum of the per-origin contributions. Must equal :attr:`see`."""
        out = EmissionPair()
        for _, pair in self.origins:
            out = out + pair
        return out

    def origin_residual(self) -> tuple[float, float]:
        """Conservation check on the attribution, per stream. Both should be ~0."""
        total = self.origin_total()
        return (total.direct - self.see.direct, total.indirect - self.see.indirect)

    @property
    def name(self) -> str:
        return self.process.name

    @property
    def good(self) -> str:
        return self.process.good

    @property
    def embedded_total(self) -> EmissionPair:
        """Embedded emissions of the whole output, not per tonne."""
        return self.see.scaled(self.process.activity_level)

    def residual(self) -> tuple[float, float]:
        """Accounting identity check, per stream. Both should be ~0."""
        own = self.process.own_emissions()
        out = self.embedded_total
        return (
            out.direct - (own.direct + self.inherited.direct),
            out.indirect - (own.indirect + self.inherited.indirect),
        )


def _resolution_order(processes: Mapping[str, ProductionProcess]) -> list[str]:
    """Topological order, so a process is resolved after its precursors.

    Depth-first with an explicit stack. A back edge is a cycle and raises,
    naming the loop: iterating a cyclic bill of materials to a fixed point would
    produce a number, and that number would be meaningless.
    """
    order: list[str] = []
    state: dict[str, int] = {}  # 0 = visiting, 1 = done

    def visit(name: str, path: list[str]) -> None:
        if state.get(name) == 1:
            return
        if state.get(name) == 0:
            loop = path[path.index(name):] + [name]
            raise CbamError(
                "circular precursor chain: " + " -> ".join(loop) + ". "
                "A good cannot be its own precursor; check the bill of materials."
            )
        state[name] = 0
        for precursor in processes[name].precursors:
            if precursor.source:
                if precursor.source not in processes:
                    raise CbamError(
                        f"{name}: precursor {precursor.good!r} names source process "
                        f"{precursor.source!r}, which is not in this installation"
                    )
                visit(precursor.source, path + [name])
        state[name] = 1
        order.append(name)

    for name in processes:
        visit(name, [])
    return order


@dataclass(frozen=True)
class Installation:
    """An installation and the resolved embedded emissions of its processes."""

    name: str
    results: tuple[ProcessResult, ...]

    def by_name(self, name: str) -> ProcessResult:
        for result in self.results:
            if result.name == name:
                return result
        raise CbamError(f"no process named {name!r} in installation {self.name!r}")

    def by_good(self, good: str) -> list[ProcessResult]:
        return [r for r in self.results if r.good == good]

    def verify(self, tolerance: float = TOLERANCE) -> None:
        """Assert the accounting identity on every process.

        Called automatically by ``resolve``. A failure means the arithmetic has
        drifted, and every downstream figure is suspect.
        """
        for result in self.results:
            direct, indirect = result.residual()
            scale = max(result.embedded_total.total, 1.0)
            if abs(direct) > tolerance * scale or abs(indirect) > tolerance * scale:
                raise CbamError(
                    f"{result.name}: embedded emissions do not balance "
                    f"(direct residual {direct:+.6g}, indirect {indirect:+.6g})"
                )
            if not result.origins:
                continue
            # The attribution is a partition of the SEE, so it has its own
            # conservation law. Checking it here means a shared precursor that
            # got counted down two paths is caught at resolve time rather than
            # discovered in a report.
            direct, indirect = result.origin_residual()
            scale = max(result.see.total, 1.0)
            if abs(direct) > tolerance * scale or abs(indirect) > tolerance * scale:
                raise CbamError(
                    f"{result.name}: origin attribution does not sum to the SEE "
                    f"(direct residual {direct:+.6g}, indirect {indirect:+.6g})"
                )


def resolve(
    processes: Iterable[ProductionProcess], installation_name: str = "installation"
) -> Installation:
    """Compute specific embedded emissions for every process, in dependency order."""
    indexed: dict[str, ProductionProcess] = {}
    for process in processes:
        if process.name in indexed:
            raise CbamError(f"duplicate process name: {process.name}")
        indexed[process.name] = process
    if not indexed:
        raise CbamError("no processes supplied")

    resolved: dict[str, ProcessResult] = {}
    for name in _resolution_order(indexed):
        process = indexed[name]

        inherited = EmissionPair()
        # Per-tonne-of-this-good contributions, keyed by the process that
        # actually released the emissions. Accumulated in the same pass as the
        # SEE, because the topological order is already established here and
        # recovering it afterwards would mean walking the graph twice.
        origins: dict[str, EmissionPair] = {}
        for precursor in process.precursors:
            if precursor.source:
                upstream = resolved[precursor.source]
                unit = upstream.see
                # Flatten the upstream attribution rather than crediting the
                # immediate supplier. A shared precursor reached down two paths
                # therefore accumulates into one entry instead of appearing
                # twice under different intermediates.
                for origin, pair in upstream.origins:
                    origins[origin] = origins.get(origin, EmissionPair()) + \
                        pair.scaled(precursor.quantity)
            else:
                unit = precursor.purchased_see  # guaranteed present by validation
                key = PURCHASED + precursor.good
                origins[key] = origins.get(key, EmissionPair()) + \
                    unit.scaled(precursor.quantity)
            inherited = inherited + unit.scaled(precursor.quantity)

        own = process.own_emissions()
        origins[name] = origins.get(name, EmissionPair()) + own

        attributed = own + inherited
        scale = 1.0 / process.activity_level
        see = attributed.scaled(scale)
        resolved[name] = ProcessResult(
            process, see, inherited,
            tuple((k, v.scaled(scale)) for k, v in origins.items()),
        )

    installation = Installation(
        installation_name, tuple(resolved[n] for n in indexed)
    )
    installation.verify()
    return installation


def render(installation: Installation, unit: str = "tCO2e") -> str:
    """Text report of specific embedded emissions per process."""
    lines = [
        f"Embedded emissions — {installation.name}",
        "=" * 88,
        f"  {'Process':<22}{'Good':<18}{'Output t':>10}"
        f"{'SEE direct':>12}{'SEE indir.':>12}{'From prec.':>12}",
        "  " + "-" * 84,
    ]
    for r in installation.results:
        lines.append(
            f"  {r.name[:21]:<22}{r.good[:17]:<18}{r.process.activity_level:>10,.0f}"
            f"{r.see.direct:>12,.4f}{r.see.indirect:>12,.4f}"
            f"{r.inherited.total:>12,.1f}"
        )
    lines += [
        "  " + "-" * 84,
        f"  SEE is {unit} per tonne of good. Direct and indirect are reported",
        "  separately and are not summed here.",
    ]
    return "\n".join(lines)


def render_attribution(result: ProcessResult, unit: str = "tCO2e") -> str:
    """Where the carbon in one tonne of this good was actually released."""
    lines = [
        f"Origin of embedded emissions — {result.good} ({result.name})",
        "=" * 72,
        f"  {'Released at':<32}{'Direct':>12}{'Indirect':>12}{'Share':>10}",
        "  " + "-" * 68,
    ]
    ordered = sorted(result.origins, key=lambda kv: -kv[1].total)
    grand = result.see.total
    for origin, pair in ordered:
        share = (pair.total / grand * 100.0) if grand else 0.0
        lines.append(
            f"  {origin[:31]:<32}{pair.direct:>12,.4f}{pair.indirect:>12,.4f}"
            f"{share:>9.1f}%"
        )
    total = result.origin_total()
    lines += [
        "  " + "-" * 68,
        f"  {'Total (= SEE)':<32}{total.direct:>12,.4f}{total.indirect:>12,.4f}"
        f"{100.0 if grand else 0.0:>9.1f}%",
        f"  {unit} per tonne of {result.good}. Direct and indirect are not summed.",
    ]
    return "\n".join(lines)
