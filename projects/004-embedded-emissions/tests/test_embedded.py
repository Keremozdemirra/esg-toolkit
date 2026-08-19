"""Test suite for cbam-embedded. Standard library only."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cbam_embedded.embedded import (  # noqa: E402
    PURCHASED,
    CbamError,
    EmissionPair,
    PrecursorInput,
    ProcessResult,
    ProductionProcess,
    render,
    render_attribution,
    resolve,
)


def simple(name="p", good="g", activity=100.0, direct=250.0, **kw):
    return ProductionProcess(
        name=name, good=good, activity_level=activity,
        attributed=EmissionPair(direct=direct), **kw
    )


class EmissionPairTests(unittest.TestCase):
    def test_addition_keeps_the_streams_apart(self):
        a = EmissionPair(10, 3) + EmissionPair(5, 7)
        self.assertEqual((a.direct, a.indirect), (15, 10))

    def test_scaling_is_linear_in_both_streams(self):
        s = EmissionPair(10, 4).scaled(2.5)
        self.assertEqual((s.direct, s.indirect), (25, 10))

    def test_total_is_available_but_never_forced(self):
        self.assertEqual(EmissionPair(10, 4).total, 14)

    def test_negative_emissions_rejected(self):
        with self.assertRaises(CbamError):
            EmissionPair(-1, 0)
        with self.assertRaises(CbamError):
            EmissionPair(0, -1)


class SingleProcessTests(unittest.TestCase):
    def test_see_is_attributed_over_activity(self):
        result = resolve([simple(activity=100, direct=250)]).by_name("p")
        self.assertAlmostEqual(result.see.direct, 2.5, places=9)
        self.assertAlmostEqual(result.see.indirect, 0.0, places=9)

    def test_electricity_lands_in_the_indirect_stream_only(self):
        p = simple(activity=100, direct=250, electricity_mwh=400, electricity_factor=0.5)
        result = resolve([p]).by_name("p")
        self.assertAlmostEqual(result.see.direct, 2.5, places=9)
        self.assertAlmostEqual(result.see.indirect, 2.0, places=9)

    def test_direct_and_indirect_are_never_silently_summed(self):
        p = simple(activity=100, direct=250, electricity_mwh=400, electricity_factor=0.5)
        see = resolve([p]).by_name("p").see
        self.assertNotEqual(see.direct, see.total)

    def test_zero_activity_level_is_rejected(self):
        with self.assertRaises(CbamError):
            simple(activity=0)

    def test_unnamed_process_rejected(self):
        with self.assertRaises(CbamError):
            simple(name="   ")

    def test_duplicate_process_names_rejected(self):
        with self.assertRaises(CbamError):
            resolve([simple(name="a"), simple(name="a")])

    def test_empty_installation_rejected(self):
        with self.assertRaises(CbamError):
            resolve([])


class PrecursorTests(unittest.TestCase):
    def test_purchased_precursor_carries_its_emissions_through(self):
        p = ProductionProcess(
            name="p", good="g", activity_level=100,
            attributed=EmissionPair(direct=250),
            precursors=(PrecursorInput("ore", 50, purchased_see=EmissionPair(2.0, 0.5)),),
        )
        r = resolve([p]).by_name("p")
        # 250 attributed + 50 t x 2.0 = 350 direct over 100 t of output
        self.assertAlmostEqual(r.see.direct, 3.5, places=9)
        self.assertAlmostEqual(r.see.indirect, 0.25, places=9)
        self.assertAlmostEqual(r.inherited.direct, 100.0, places=9)

    def test_precursor_without_source_or_figures_is_refused(self):
        # Assuming an unstated precursor is emission-free understates the good.
        with self.assertRaises(CbamError):
            PrecursorInput("ore", 50)

    def test_chain_propagates_through_two_stages(self):
        upstream = simple(name="up", good="intermediate", activity=200, direct=400)
        downstream = ProductionProcess(
            name="down", good="final", activity_level=100,
            attributed=EmissionPair(direct=100),
            precursors=(PrecursorInput("intermediate", 150, source="up"),),
        )
        inst = resolve([downstream, upstream])  # deliberately out of order
        self.assertAlmostEqual(inst.by_name("up").see.direct, 2.0, places=9)
        # 100 + 150 x 2.0 = 400 over 100 t
        self.assertAlmostEqual(inst.by_name("down").see.direct, 4.0, places=9)

    def test_resolution_is_independent_of_input_order(self):
        up = simple(name="up", good="i", activity=200, direct=400)
        down = ProductionProcess(
            name="down", good="f", activity_level=100,
            attributed=EmissionPair(direct=100),
            precursors=(PrecursorInput("i", 150, source="up"),),
        )
        a = resolve([up, down]).by_name("down").see.direct
        b = resolve([down, up]).by_name("down").see.direct
        self.assertAlmostEqual(a, b, places=12)

    def test_unknown_source_process_is_reported(self):
        p = ProductionProcess(
            name="p", good="g", activity_level=100,
            attributed=EmissionPair(direct=1),
            precursors=(PrecursorInput("x", 1, source="nowhere"),),
        )
        with self.assertRaises(CbamError) as ctx:
            resolve([p])
        self.assertIn("nowhere", str(ctx.exception))

    def test_circular_chain_raises_and_names_the_loop(self):
        a = ProductionProcess(
            name="a", good="ga", activity_level=100,
            attributed=EmissionPair(direct=1),
            precursors=(PrecursorInput("gb", 1, source="b"),),
        )
        b = ProductionProcess(
            name="b", good="gb", activity_level=100,
            attributed=EmissionPair(direct=1),
            precursors=(PrecursorInput("ga", 1, source="a"),),
        )
        with self.assertRaises(CbamError) as ctx:
            resolve([a, b])
        message = str(ctx.exception)
        self.assertIn("circular", message)
        self.assertIn("->", message)

    def test_self_referencing_process_is_a_cycle(self):
        p = ProductionProcess(
            name="p", good="g", activity_level=100,
            attributed=EmissionPair(direct=1),
            precursors=(PrecursorInput("g", 1, source="p"),),
        )
        with self.assertRaises(CbamError):
            resolve([p])

    def test_a_shared_precursor_is_counted_by_each_consumer(self):
        # Two processes drawing on the same upstream process each inherit in
        # proportion to what they consumed; nothing is double counted within a
        # single consumer, and nothing is lost across them.
        up = simple(name="up", good="i", activity=300, direct=600)
        c1 = ProductionProcess(
            name="c1", good="f1", activity_level=100,
            attributed=EmissionPair(direct=0),
            precursors=(PrecursorInput("i", 100, source="up"),),
        )
        c2 = ProductionProcess(
            name="c2", good="f2", activity_level=100,
            attributed=EmissionPair(direct=0),
            precursors=(PrecursorInput("i", 200, source="up"),),
        )
        inst = resolve([up, c1, c2])
        self.assertAlmostEqual(inst.by_name("c1").see.direct, 2.0, places=9)
        self.assertAlmostEqual(inst.by_name("c2").see.direct, 4.0, places=9)
        # The upstream process emitted 600 t and its output was fully consumed.
        inherited = (
            inst.by_name("c1").inherited.direct + inst.by_name("c2").inherited.direct
        )
        self.assertAlmostEqual(inherited, 600.0, places=6)


class ConservationTests(unittest.TestCase):
    """The identity the whole module rests on."""

    def build(self):
        return [
            simple(name="coke", good="coke", activity=480, direct=312,
                   electricity_mwh=54, electricity_factor=0.31),
            ProductionProcess(
                name="sinter", good="sinter", activity_level=1250,
                attributed=EmissionPair(direct=241),
                electricity_mwh=88, electricity_factor=0.31,
                precursors=(PrecursorInput("ore", 1180,
                                           purchased_see=EmissionPair(0.031, 0.008)),),
            ),
            ProductionProcess(
                name="bf", good="pig iron", activity_level=900,
                attributed=EmissionPair(direct=1046),
                electricity_mwh=126, electricity_factor=0.31,
                precursors=(
                    PrecursorInput("coke", 372, source="coke"),
                    PrecursorInput("sinter", 1190, source="sinter"),
                ),
            ),
        ]

    def test_every_process_balances(self):
        for result in resolve(self.build()).results:
            direct, indirect = result.residual()
            self.assertAlmostEqual(direct, 0.0, places=6, msg=result.name)
            self.assertAlmostEqual(indirect, 0.0, places=6, msg=result.name)

    def test_verify_passes_on_a_consistent_installation(self):
        resolve(self.build()).verify()  # must not raise

    def test_holds_on_randomly_generated_chains(self):
        import random

        rng = random.Random(20260811)
        for _ in range(150):
            processes = []
            for i in range(rng.randint(1, 6)):
                precursors = []
                for j in range(i):
                    if rng.random() < 0.5:
                        precursors.append(
                            PrecursorInput(f"g{j}", rng.uniform(1, 500), source=f"p{j}")
                        )
                processes.append(
                    ProductionProcess(
                        name=f"p{i}", good=f"g{i}",
                        activity_level=rng.uniform(10, 2000),
                        attributed=EmissionPair(direct=rng.uniform(0, 5000)),
                        electricity_mwh=rng.uniform(0, 900),
                        electricity_factor=rng.uniform(0, 0.9),
                        precursors=tuple(precursors),
                    )
                )
            for result in resolve(processes).results:
                direct, indirect = result.residual()
                scale = max(result.embedded_total.total, 1.0)
                self.assertLess(abs(direct) / scale, 1e-9)
                self.assertLess(abs(indirect) / scale, 1e-9)

    def test_embedded_total_scales_with_activity_level(self):
        r = resolve([simple(activity=100, direct=250)]).by_name("p")
        self.assertAlmostEqual(r.embedded_total.direct, 250.0, places=9)


class LookupAndRenderTests(unittest.TestCase):
    def setUp(self):
        self.inst = resolve(
            [simple(name="a", good="steel"), simple(name="b", good="steel")],
            "plant",
        )

    def test_by_good_returns_every_matching_process(self):
        self.assertEqual(len(self.inst.by_good("steel")), 2)
        self.assertEqual(self.inst.by_good("aluminium"), [])

    def test_by_name_raises_on_an_unknown_process(self):
        with self.assertRaises(CbamError):
            self.inst.by_name("missing")

    def test_render_lists_every_process_and_labels_the_streams(self):
        text = render(self.inst)
        self.assertIn("plant", text)
        self.assertIn("SEE direct", text)
        self.assertIn("not summed", text)


class OriginAttributionTests(unittest.TestCase):
    """Where in the chain the carbon was actually released.

    The SEE of crude steel says how much carbon a tonne carries. It does not
    say whether that carbon came out of the coke oven or the blast furnace,
    which is the question an abatement decision turns on. The attribution
    answers it, and it is a partition of the SEE -- so it has a conservation
    law of its own, and that law is what these tests assert.
    """

    def chain(self):
        return [
            simple(name="coke", good="coke", activity=480, direct=312,
                   electricity_mwh=54, electricity_factor=0.31),
            ProductionProcess(
                name="sinter", good="sinter", activity_level=1250,
                attributed=EmissionPair(direct=241),
                precursors=(PrecursorInput("ore", 1180,
                                           purchased_see=EmissionPair(0.031, 0.008)),),
            ),
            ProductionProcess(
                name="bf", good="pig iron", activity_level=900,
                attributed=EmissionPair(direct=1046),
                electricity_mwh=126, electricity_factor=0.31,
                precursors=(
                    PrecursorInput("coke", 372, source="coke"),
                    PrecursorInput("sinter", 1190, source="sinter"),
                ),
            ),
        ]

    def test_the_attribution_sums_to_the_see(self):
        for result in resolve(self.chain()).results:
            direct, indirect = result.origin_residual()
            self.assertAlmostEqual(direct, 0.0, places=9, msg=result.name)
            self.assertAlmostEqual(indirect, 0.0, places=9, msg=result.name)

    def test_a_process_with_no_precursors_attributes_everything_to_itself(self):
        r = resolve([simple(activity=100, direct=250)]).by_name("p")
        self.assertEqual(list(r.origin_map), ["p"])
        self.assertAlmostEqual(r.origin_map["p"].direct, 2.5, places=9)

    def test_own_emissions_appear_at_their_own_per_tonne_rate(self):
        inst = resolve(self.chain())
        bf = inst.by_name("bf")
        own = inst.by_name("bf").process.own_emissions()
        self.assertAlmostEqual(bf.origin_map["bf"].direct, own.direct / 900, places=9)
        self.assertAlmostEqual(bf.origin_map["bf"].indirect, own.indirect / 900, places=9)

    def test_purchased_precursors_are_keyed_apart_from_processes(self):
        inst = resolve(self.chain())
        keys = inst.by_name("sinter").origin_map
        self.assertIn(PURCHASED + "ore", keys)
        self.assertIn("sinter", keys)
        # A purchased good and a process could share a name; they must not merge.
        self.assertNotEqual(PURCHASED + "ore", "ore")

    def test_no_contribution_is_negative(self):
        for result in resolve(self.chain()).results:
            for origin, pair in result.origins:
                self.assertGreaterEqual(pair.direct, 0.0, origin)
                self.assertGreaterEqual(pair.indirect, 0.0, origin)

    def test_a_shared_precursor_accumulates_into_one_entry(self):
        # Diamond: u feeds both a and b, and both feed c. If the attribution
        # credited the immediate supplier instead of flattening, u would appear
        # twice in c -- or once, at the wrong magnitude.
        processes = [
            simple(name="u", good="gu", activity=100, direct=1000),
            ProductionProcess(
                name="a", good="ga", activity_level=50,
                attributed=EmissionPair(direct=100),
                precursors=(PrecursorInput("gu", 40, source="u"),),
            ),
            ProductionProcess(
                name="b", good="gb", activity_level=50,
                attributed=EmissionPair(direct=200),
                precursors=(PrecursorInput("gu", 60, source="u"),),
            ),
            ProductionProcess(
                name="c", good="gc", activity_level=25,
                attributed=EmissionPair(direct=50),
                precursors=(
                    PrecursorInput("ga", 20, source="a"),
                    PrecursorInput("gb", 30, source="b"),
                ),
            ),
        ]
        c = resolve(processes).by_name("c")
        self.assertEqual(sorted(c.origin_map), ["a", "b", "c", "u"])
        # u emits 10 tCO2e per tonne of gu. c consumes 20 t of ga (carrying
        # 40/50 t of gu per tonne) and 30 t of gb (carrying 60/50), so it pulls
        # 20*0.8 + 30*1.2 = 52 t of gu, i.e. 520 tCO2e over 25 t of gc.
        self.assertAlmostEqual(c.origin_map["u"].direct, 520.0 / 25.0, places=9)
        direct, _ = c.origin_residual()
        self.assertAlmostEqual(direct, 0.0, places=9)

    def test_scaling_one_process_own_emissions_scales_only_its_own_share(self):
        base = resolve(self.chain())
        louder = list(self.chain())
        louder[0] = simple(name="coke", good="coke", activity=480, direct=624,
                           electricity_mwh=54, electricity_factor=0.31)
        after = resolve(louder)
        before_bf, after_bf = base.by_name("bf").origin_map, after.by_name("bf").origin_map
        # sinter did not move; coke's direct contribution rose by exactly the
        # extra 312 t spread over 480 t of coke and 372 t of it into 900 t of iron.
        self.assertAlmostEqual(before_bf["sinter"].direct, after_bf["sinter"].direct, places=9)
        delta = after_bf["coke"].direct - before_bf["coke"].direct
        self.assertAlmostEqual(delta, (312.0 / 480.0) * 372.0 / 900.0, places=9)

    def test_conservation_holds_on_randomly_generated_chains(self):
        import random

        rng = random.Random(1102026)
        for _ in range(150):
            processes = []
            for i in range(rng.randint(1, 6)):
                precursors = []
                for j in range(i):
                    if rng.random() < 0.5:
                        precursors.append(
                            PrecursorInput(f"g{j}", rng.uniform(1, 500), source=f"p{j}")
                        )
                if rng.random() < 0.4:
                    precursors.append(
                        PrecursorInput(
                            f"bought{i}", rng.uniform(1, 500),
                            purchased_see=EmissionPair(rng.uniform(0, 3), rng.uniform(0, 1)),
                        )
                    )
                processes.append(
                    ProductionProcess(
                        name=f"p{i}", good=f"g{i}",
                        activity_level=rng.uniform(10, 2000),
                        attributed=EmissionPair(direct=rng.uniform(0, 5000)),
                        electricity_mwh=rng.uniform(0, 900),
                        electricity_factor=rng.uniform(0, 0.9),
                        precursors=tuple(precursors),
                    )
                )
            for result in resolve(processes).results:
                direct, indirect = result.origin_residual()
                scale = max(result.see.total, 1.0)
                self.assertLess(abs(direct) / scale, 1e-9, result.name)
                self.assertLess(abs(indirect) / scale, 1e-9, result.name)

    def test_verify_rejects_an_attribution_that_does_not_add_up(self):
        # Tampering with the partition must be caught, not carried into a report.
        inst = resolve(self.chain())
        good = inst.by_name("bf")
        broken = ProcessResult(
            good.process, good.see, good.inherited,
            tuple((k, v.scaled(0.5)) for k, v in good.origins),
        )
        with self.assertRaises(CbamError):
            type(inst)(inst.name, (broken,)).verify()

    def test_render_attribution_orders_by_size_and_states_the_total(self):
        text = render_attribution(resolve(self.chain()).by_name("bf"))
        self.assertIn("pig iron", text)
        self.assertIn("Total (= SEE)", text)
        self.assertIn("not summed", text)
        shares = [
            float(line.rsplit("%", 1)[0].rsplit(None, 1)[-1])
            for line in text.splitlines()
            if line.strip().endswith("%") and "Total" not in line
        ]
        self.assertEqual(shares, sorted(shares, reverse=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
