"""Test suite for marginal-abatement. Standard library only."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marginal_abatement.curve import (  # noqa: E402
    AbatementError,
    Measure,
    annuity_factor,
    build_curve,
    feasible_selection,
    render,
)
from marginal_abatement.loader import load_measures  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "measures.csv"


class AnnuityFactorTests(unittest.TestCase):
    def test_zero_rate_is_the_number_of_years(self):
        # The closed form divides by zero here; the limit is n.
        self.assertEqual(annuity_factor(0.0, 20), 20.0)

    def test_matches_an_explicit_discounted_sum(self):
        rate, years = 0.07, 15
        expected = sum(1 / (1 + rate) ** t for t in range(1, years + 1))
        self.assertAlmostEqual(annuity_factor(rate, years), expected, places=10)

    def test_is_bounded_by_the_perpetuity(self):
        # A perpetuity is the ceiling. Over any lifetime a real asset might
        # have, the bound is strict.
        self.assertLess(annuity_factor(0.08, 50), 1 / 0.08)
        # Past roughly 400 years at this rate, (1+r)^-n underflows to zero in
        # double precision and the factor lands exactly on the perpetuity.
        # The bound is still respected; it just stops being strict, which is a
        # property of floats rather than of the arithmetic.
        self.assertLessEqual(annuity_factor(0.08, 500), 1 / 0.08)

    def test_increases_with_lifetime_and_decreases_with_rate(self):
        self.assertGreater(annuity_factor(0.05, 20), annuity_factor(0.05, 10))
        self.assertLess(annuity_factor(0.10, 20), annuity_factor(0.05, 20))

    def test_invalid_inputs(self):
        with self.assertRaises(AbatementError):
            annuity_factor(0.05, 0)
        with self.assertRaises(AbatementError):
            annuity_factor(-1.5, 10)


class CostPerTonneTests(unittest.TestCase):
    def test_undiscounted_case_reduces_to_capex_over_lifetime_tonnes(self):
        m = Measure("x", capex=100_000, opex=0, abatement=500, lifetime=10)
        # No discounting, no opex: total cost divided by total tonnes.
        self.assertAlmostEqual(m.cost_per_tonne(0.0), 100_000 / 5_000, places=9)

    def test_pure_opex_measure_is_independent_of_the_discount_rate(self):
        # With no capex the annuity factor cancels top and bottom.
        m = Measure("x", capex=0, opex=12_000, abatement=400, lifetime=10)
        self.assertAlmostEqual(m.cost_per_tonne(0.0), 30.0, places=9)
        self.assertAlmostEqual(m.cost_per_tonne(0.12), 30.0, places=9)

    def test_a_higher_discount_rate_makes_capital_heavy_measures_dearer(self):
        m = Measure("x", capex=1_000_000, opex=0, abatement=500, lifetime=20)
        self.assertGreater(m.cost_per_tonne(0.10), m.cost_per_tonne(0.03))

    def test_energy_savings_can_drive_the_cost_negative(self):
        m = Measure("leaks", capex=25_000, opex=-19_000, abatement=140, lifetime=5)
        self.assertLess(m.cost_per_tonne(0.05), 0)

    def test_npv_of_a_no_regret_measure_is_positive(self):
        m = Measure("leaks", capex=25_000, opex=-19_000, abatement=140, lifetime=5)
        self.assertGreater(m.npv(0.05), 0)

    def test_sign_of_cost_per_tonne_agrees_with_sign_of_npv(self):
        for capex, opex in ((25_000, -19_000), (100_000, 5_000), (0, -1_000)):
            m = Measure("m", capex=capex, opex=opex, abatement=100, lifetime=10)
            self.assertEqual(m.cost_per_tonne(0.06) < 0, m.npv(0.06) > 0)

    def test_rejects_measures_that_abate_nothing(self):
        with self.assertRaises(AbatementError):
            Measure("x", capex=1, opex=0, abatement=0, lifetime=10)

    def test_rejects_negative_capex(self):
        with self.assertRaises(AbatementError):
            Measure("x", capex=-1, opex=0, abatement=10, lifetime=10)

    def test_rejects_empty_name_and_bad_lifetime(self):
        with self.assertRaises(AbatementError):
            Measure("  ", capex=1, opex=0, abatement=10, lifetime=10)
        with self.assertRaises(AbatementError):
            Measure("x", capex=1, opex=0, abatement=10, lifetime=0)


class CurveTests(unittest.TestCase):
    def setUp(self):
        self.curve = build_curve(load_measures(EXAMPLES), rate=0.05)

    def test_steps_are_sorted_by_cost_per_tonne(self):
        costs = [s.cost_per_tonne for s in self.curve.steps]
        self.assertEqual(costs, sorted(costs))

    def test_cumulative_abatement_is_monotone_and_ends_at_the_total(self):
        cumulative = [s.cumulative_abatement for s in self.curve.steps]
        self.assertEqual(cumulative, sorted(cumulative))
        self.assertAlmostEqual(
            cumulative[-1], sum(s.abatement for s in self.curve.steps), places=6
        )

    def test_ties_are_broken_by_name_so_output_is_deterministic(self):
        a = Measure("zebra", capex=0, opex=1_000, abatement=100, lifetime=10)
        b = Measure("alpha", capex=0, opex=1_000, abatement=100, lifetime=10)
        curve = build_curve([a, b], rate=0.05)
        self.assertEqual([s.name for s in curve.steps], ["alpha", "zebra"])

    def test_no_regret_block_is_the_negative_cost_prefix(self):
        negative = sum(
            s.abatement for s in self.curve.steps if s.cost_per_tonne <= 0
        )
        self.assertAlmostEqual(self.curve.no_regret_abatement, negative, places=6)
        self.assertGreater(self.curve.no_regret_abatement, 0)

    def test_carbon_price_unlocks_a_monotone_amount(self):
        amounts = [self.curve.carbon_price_unlocking(p) for p in (0, 50, 100, 1e9)]
        self.assertEqual(amounts, sorted(amounts))
        self.assertAlmostEqual(amounts[-1], self.curve.total_abatement, places=6)

    def test_cost_to_abate_uses_the_cheapest_measures_first(self):
        cheap, _ = self.curve.cost_to_abate(100)
        dear, _ = self.curve.cost_to_abate(self.curve.total_abatement)
        self.assertLess(cheap, dear)

    def test_cost_to_abate_zero_is_free(self):
        cost, used = self.curve.cost_to_abate(0)
        self.assertEqual(cost, 0.0)
        self.assertEqual(used, [])

    def test_cost_to_abate_the_whole_curve_equals_the_curve_cost(self):
        cost, _ = self.curve.cost_to_abate(self.curve.total_abatement)
        self.assertAlmostEqual(cost, self.curve.annual_cost(), places=4)

    def test_asking_for_more_than_exists_is_an_error(self):
        with self.assertRaises(AbatementError):
            self.curve.cost_to_abate(self.curve.total_abatement + 1)
        with self.assertRaises(AbatementError):
            self.curve.cost_to_abate(-1)

    def test_empty_and_duplicate_inputs_are_rejected(self):
        with self.assertRaises(AbatementError):
            build_curve([])
        m = Measure("dup", capex=0, opex=1, abatement=1, lifetime=1)
        with self.assertRaises(AbatementError):
            build_curve([m, m])

    def test_unknown_dependency_is_rejected(self):
        m = Measure(
            "x", capex=0, opex=1, abatement=1, lifetime=1,
            requires=frozenset({"nonexistent"}),
        )
        with self.assertRaises(AbatementError):
            build_curve([m])

    def test_self_reference_is_rejected(self):
        m = Measure(
            "x", capex=0, opex=1, abatement=1, lifetime=1,
            excludes=frozenset({"x"}),
        )
        with self.assertRaises(AbatementError):
            build_curve([m])

    def test_render_produces_a_line_per_measure(self):
        text = render(self.curve)
        for step in self.curve.steps:
            self.assertIn(step.name[:25], text)


class FeasibleSelectionTests(unittest.TestCase):
    def setUp(self):
        self.curve = build_curve(load_measures(EXAMPLES), rate=0.05)

    def test_selection_meets_the_target(self):
        chosen = feasible_selection(self.curve, 1_000)
        self.assertGreaterEqual(sum(s.abatement for s in chosen), 1_000)

    def test_mutually_exclusive_measures_are_never_both_chosen(self):
        chosen = {s.name for s in feasible_selection(self.curve, 4_000)}
        self.assertFalse(
            {"Heat pump replacing gas boiler", "Gas boiler efficiency upgrade"}
            <= chosen
        )

    def test_prerequisites_are_satisfied_for_everything_chosen(self):
        chosen = feasible_selection(self.curve, 5_000)
        names = {s.name for s in chosen}
        for step in chosen:
            self.assertTrue(
                step.measure.requires <= names,
                f"{step.name} chosen without {step.measure.requires - names}",
            )

    def test_selection_is_ordered_cheapest_first(self):
        chosen = feasible_selection(self.curve, 3_000)
        costs = [s.cost_per_tonne for s in chosen]
        self.assertEqual(costs, sorted(costs))

    def test_an_unreachable_target_reports_what_is_actually_available(self):
        with self.assertRaises(AbatementError) as ctx:
            feasible_selection(self.curve, 1e9)
        self.assertIn("most available", str(ctx.exception))

    def test_exclusion_can_make_a_target_unreachable(self):
        a = Measure("a", capex=0, opex=1, abatement=100, lifetime=10,
                    excludes=frozenset({"b"}))
        b = Measure("b", capex=0, opex=2, abatement=100, lifetime=10,
                    excludes=frozenset({"a"}))
        curve = build_curve([a, b])
        self.assertEqual(curve.total_abatement, 200)  # on paper
        with self.assertRaises(AbatementError):
            feasible_selection(curve, 150)  # but not jointly available


class LoaderTests(unittest.TestCase):
    def test_reads_the_example_file(self):
        measures = load_measures(EXAMPLES)
        self.assertEqual(len(measures), 10)
        heat_pump = next(m for m in measures if m.name.startswith("Heat pump"))
        self.assertIn("Building envelope insulation", heat_pump.requires)
        self.assertIn("Gas boiler efficiency upgrade", heat_pump.excludes)

    def test_missing_file(self):
        with self.assertRaises(AbatementError):
            load_measures(Path("/nonexistent/x.csv"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
