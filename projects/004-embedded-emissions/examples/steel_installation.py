"""A simplified integrated steel plant: coke -> sinter -> pig iron -> crude steel.

Figures are illustrative and are not drawn from any published dataset. They
exist to exercise the precursor chain, not to represent a real installation.
Replace them with your own verified installation data.
"""

from cbam_embedded import (
    EmissionPair,
    PrecursorInput,
    ProductionProcess,
    render,
    render_attribution,
    resolve,
)

PROCESSES = [
    ProductionProcess(
        name="coke-oven",
        good="coke",
        activity_level=480_000,
        attributed=EmissionPair(direct=312_000),
        electricity_mwh=54_000,
        electricity_factor=0.31,
    ),
    ProductionProcess(
        name="sinter-plant",
        good="sintered ore",
        activity_level=1_250_000,
        attributed=EmissionPair(direct=241_000),
        electricity_mwh=88_000,
        electricity_factor=0.31,
        precursors=(
            # Iron ore is not a CBAM good and is bought in; its embedded
            # emissions still have to be stated rather than assumed away.
            PrecursorInput("iron ore", 1_180_000, purchased_see=EmissionPair(0.031, 0.008)),
        ),
    ),
    ProductionProcess(
        name="blast-furnace",
        good="pig iron",
        activity_level=900_000,
        attributed=EmissionPair(direct=1_046_000),
        electricity_mwh=126_000,
        electricity_factor=0.31,
        precursors=(
            PrecursorInput("coke", 372_000, source="coke-oven"),
            PrecursorInput("sintered ore", 1_190_000, source="sinter-plant"),
        ),
    ),
    ProductionProcess(
        name="bof-steelmaking",
        good="crude steel",
        activity_level=1_010_000,
        attributed=EmissionPair(direct=118_000),
        electricity_mwh=97_000,
        electricity_factor=0.31,
        precursors=(
            PrecursorInput("pig iron", 880_000, source="blast-furnace"),
            PrecursorInput("scrap", 190_000, purchased_see=EmissionPair(0.012, 0.004)),
        ),
    ),
]

if __name__ == "__main__":
    installation = resolve(PROCESSES, "Illustrative integrated steel plant")
    print(render(installation))
    print()
    # The SEE of crude steel says how much carbon a tonne carries. This says
    # where it was released, which is the number an abatement decision needs.
    print(render_attribution(installation.by_name("bof-steelmaking")))
