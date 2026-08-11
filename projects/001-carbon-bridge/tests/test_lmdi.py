"""Test suite for carbon-bridge. Standard library only: python -m unittest -v"""

from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carbon_bridge.lmdi import (  # noqa: E402
    DecompositionError,
    Segment,
    decompose,
    decompose_series,
    logarithmic_mean,
)
from carbon_bridge.loader import load_periods  # noqa: E402
from carbon_bridge.report import narrative, segment_table, summary, to_markdown  # noqa: E402


def seg(name, activity, energy, emissions):
    return Segment(name, activity, energy, emissions)


class LogarithmicMeanTests(unittest.TestCase):
    def test_equal_arguments_return_the_value(self):
        self.assertEqual(logarithmic_mean(7.0, 7.0), 7.0)

    def test_sits_between_geometric_and_arithmetic_mean(self):
        a, b = 3.0, 11.0
        self.assertLess(math.sqrt(a * b), logarithmic_mean(a, b))
        self.assertLess(logarithmic_mean(a, b), (a + b) / 2)

    def test_symmetric(self):
        self.assertAlmostEqual(logarithmic_mean(2.0, 9.0), logarithmic_mean(9.0, 2.0))

    def test_zero_argument_collapses_to_zero(self):
        self.assertEqual(logarithmic_mean(0.0, 5.0), 0.0)
        self.assertEqual(logarithmic_mean(5.0, 0.0), 0.0)

    def test_near_equal_values_do_not_blow_up(self):
        a = 1_000_000.0
        b = a * (1 + 1e-15)
        self.assertAlmostEqual(logarithmic_mean(a, b), a, delta=1.0)

    def test_negative_input_rejected(self):
        with self.assertRaises(DecompositionError):
            logarithmic_mean(-1.0, 2.0)


class PerfectDecompositionTests(unittest.TestCase):
    """LMDI-I leaves no residual. This is the property the method is chosen for."""

    def assert_perfect(self, base, target, places=6):
        result = decompose(base, target)
        self.assertAlmostEqual(result.residual, 0.0, places=places)
        self.assertAlmostEqual(
            result.explained_change, result.total_change, places=places
        )
        return result

    def test_simple_two_segment_case(self):
        base = [seg("A", 120_000, 48_000, 15_600), seg("B", 80_000, 26_000, 10_400)]
        target = [seg("A", 131_000, 49_500, 14_200), seg("B", 74_000, 23_000, 8_900)]
        self.assert_perfect(base, target)

    def test_holds_for_many_random_portfolios(self):
        import random

        rng = random.Random(20260811)
        for _ in range(200):
            size = rng.randint(1, 8)
            base, target = [], []
            for i in range(size):
                activity = rng.uniform(1, 10_000)
                energy = activity * rng.uniform(0.05, 2.0)
                base.append(seg(f"s{i}", activity, energy, energy * rng.uniform(0.05, 1.2)))
                activity = rng.uniform(1, 10_000)
                energy = activity * rng.uniform(0.05, 2.0)
                target.append(seg(f"s{i}", activity, energy, energy * rng.uniform(0.05, 1.2)))
            result = decompose(base, target)
            self.assertAlmostEqual(
                result.residual / max(abs(result.total_change), 1.0), 0.0, places=9
            )

    def test_segment_effects_sum_to_portfolio_effects(self):
        base = [seg("A", 100, 50, 25), seg("B", 200, 80, 60), seg("C", 40, 30, 5)]
        target = [seg("A", 130, 55, 22), seg("B", 180, 70, 58), seg("C", 60, 45, 9)]
        result = decompose(base, target)
        for effect in ("activity", "structure", "intensity", "emission_factor"):
            self.assertAlmostEqual(
                sum(getattr(s, effect) for s in result.segments),
                getattr(result, effect),
                places=8,
            )

    PERIODS = {
        "2022": [seg("A", 100, 50, 25), seg("B", 200, 80, 60)],
        "2023": [seg("A", 118, 54, 24), seg("B", 190, 74, 55)],
        "2024": [seg("A", 131, 57, 21), seg("B", 175, 66, 47)],
    }

    def test_chained_total_change_telescopes_to_the_fixed_base_total(self):
        chained = decompose_series(self.PERIODS, chained=True)
        direct = decompose(self.PERIODS["2022"], self.PERIODS["2024"])
        self.assertAlmostEqual(
            sum(step.total_change for step in chained), direct.total_change, places=8
        )

    def test_every_step_of_a_chained_series_is_itself_perfect(self):
        for step in decompose_series(self.PERIODS, chained=True):
            self.assertAlmostEqual(step.residual, 0.0, places=8)

    def test_chained_driver_split_may_differ_from_fixed_base(self):
        # Additive LMDI-I is path dependent: the totals agree but the
        # attribution to individual drivers depends on the route taken.
        # This is documented behaviour, not a defect, so it is pinned here.
        chained = decompose_series(self.PERIODS, chained=True)
        direct = decompose(self.PERIODS["2022"], self.PERIODS["2024"])
        chained_activity = sum(step.activity for step in chained)
        self.assertNotAlmostEqual(chained_activity, direct.activity, places=6)
        # ... but they must stay in the same ballpark and the same direction.
        self.assertEqual(chained_activity > 0, direct.activity > 0)
        self.assertLess(
            abs(chained_activity - direct.activity) / abs(direct.activity), 0.25
        )

    def test_fixed_base_series_compares_everything_to_the_first_period(self):
        results = decompose_series(self.PERIODS, chained=False)
        self.assertEqual([r.base_period for r in results], ["2022", "2022"])
        self.assertEqual([r.target_period for r in results], ["2023", "2024"])


class DriverIsolationTests(unittest.TestCase):
    """Change exactly one driver and check the others stay at zero."""

    BASE = [seg("A", 100.0, 50.0, 25.0), seg("B", 300.0, 90.0, 45.0)]

    def test_pure_activity_growth(self):
        # Everything scaled by 1.5: only the activity effect should move.
        target = [seg(s.name, s.activity * 1.5, s.energy * 1.5, s.emissions * 1.5) for s in self.BASE]
        r = decompose(self.BASE, target)
        self.assertAlmostEqual(r.structure, 0.0, places=8)
        self.assertAlmostEqual(r.intensity, 0.0, places=8)
        self.assertAlmostEqual(r.emission_factor, 0.0, places=8)
        self.assertAlmostEqual(r.activity, r.total_change, places=8)
        self.assertGreater(r.activity, 0)

    def test_pure_emission_factor_improvement(self):
        # Same output, same energy, cleaner energy: only the factor effect moves.
        target = [seg(s.name, s.activity, s.energy, s.emissions * 0.8) for s in self.BASE]
        r = decompose(self.BASE, target)
        self.assertAlmostEqual(r.activity, 0.0, places=8)
        self.assertAlmostEqual(r.structure, 0.0, places=8)
        self.assertAlmostEqual(r.intensity, 0.0, places=8)
        self.assertLess(r.emission_factor, 0)

    def test_pure_efficiency_improvement(self):
        # Same output, less energy, same carbon per unit energy.
        target = [seg(s.name, s.activity, s.energy * 0.9, s.emissions * 0.9) for s in self.BASE]
        r = decompose(self.BASE, target)
        self.assertAlmostEqual(r.activity, 0.0, places=8)
        self.assertAlmostEqual(r.structure, 0.0, places=8)
        self.assertAlmostEqual(r.emission_factor, 0.0, places=8)
        self.assertLess(r.intensity, 0)

    def test_pure_mix_shift(self):
        # Total activity constant, shifted from the dirty to the clean segment.
        base = [seg("clean", 100.0, 40.0, 4.0), seg("dirty", 100.0, 40.0, 40.0)]
        target = [seg("clean", 150.0, 60.0, 6.0), seg("dirty", 50.0, 20.0, 20.0)]
        r = decompose(base, target)
        self.assertAlmostEqual(r.activity, 0.0, places=8)
        self.assertAlmostEqual(r.intensity, 0.0, places=8)
        self.assertAlmostEqual(r.emission_factor, 0.0, places=8)
        self.assertLess(r.structure, 0)  # shifting to the clean segment cuts emissions

    def test_identical_periods_give_zero_everywhere(self):
        r = decompose(self.BASE, list(self.BASE))
        self.assertAlmostEqual(r.total_change, 0.0, places=10)
        for value in r.effects.values():
            self.assertAlmostEqual(value, 0.0, places=8)


class ZeroAndEdgeCaseTests(unittest.TestCase):
    def test_segment_only_in_target_is_treated_as_a_new_entrant(self):
        base = [seg("A", 100, 50, 25)]
        target = [seg("A", 100, 50, 25), seg("B", 40, 20, 12)]
        r = decompose(base, target)
        self.assertAlmostEqual(r.residual, 0.0, places=6)
        self.assertAlmostEqual(r.total_change, 12.0, places=6)
        self.assertEqual({s.name for s in r.segments}, {"A", "B"})

    def test_segment_only_in_base_is_treated_as_a_closure(self):
        base = [seg("A", 100, 50, 25), seg("B", 40, 20, 12)]
        target = [seg("A", 100, 50, 25)]
        r = decompose(base, target)
        self.assertAlmostEqual(r.residual, 0.0, places=6)
        self.assertAlmostEqual(r.total_change, -12.0, places=6)

    def test_segment_with_zero_emissions_contributes_nothing(self):
        base = [seg("A", 100, 50, 25), seg("solar", 50, 20, 0)]
        target = [seg("A", 100, 50, 25), seg("solar", 90, 35, 0)]
        r = decompose(base, target)
        solar = next(s for s in r.segments if s.name == "solar")
        # Not exactly zero: the zero-substitution leaves noise of the order
        # of ZERO_SUBSTITUTE. It must be negligible against the real numbers.
        self.assertLess(abs(solar.total), 1e-9)
        self.assertAlmostEqual(r.residual, 0.0, places=8)

    def test_zero_total_activity_is_rejected(self):
        with self.assertRaises(DecompositionError):
            decompose([seg("A", 0, 0, 0)], [seg("A", 10, 5, 2)])

    def test_negative_values_are_rejected(self):
        with self.assertRaises(DecompositionError):
            seg("A", -1, 5, 2)

    def test_nan_is_rejected(self):
        with self.assertRaises(DecompositionError):
            seg("A", float("nan"), 5, 2)

    def test_series_needs_two_periods(self):
        with self.assertRaises(DecompositionError):
            decompose_series({"2024": [seg("A", 1, 1, 1)]})


class LoaderTests(unittest.TestCase):
    CSV = (
        "period,segment,activity,energy,emissions\n"
        "2023,Plant A,120000,48000,15600\n"
        "2023,Plant B,80000,26000,10400\n"
        "2024,Plant A,131000,49500,14200\n"
        "2024,Plant B,74000,23000,8900\n"
    )

    def _write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        return Path(handle.name)

    def test_round_trip(self):
        periods = load_periods(self._write(self.CSV))
        self.assertEqual(list(periods), ["2023", "2024"])
        self.assertEqual(len(periods["2023"]), 2)
        self.assertEqual(periods["2023"][0].emissions, 15600)

    def test_column_aliases_are_accepted(self):
        text = (
            "Year,Facility,Production,Energy Consumption,tCO2e\n"
            "2023,A,100,50,25\n2024,A,110,52,24\n"
        )
        periods = load_periods(self._write(text))
        self.assertEqual(periods["2024"][0].activity, 110)

    def test_thousands_separators_both_conventions(self):
        text = (
            "period,segment,activity,energy,emissions\n"
            '2023,A,"1,200.5","500.25","120.75"\n'
            '2024,A,"1.300,5","510,25","118,75"\n'
        )
        periods = load_periods(self._write(text))
        self.assertAlmostEqual(periods["2023"][0].activity, 1200.5)
        self.assertAlmostEqual(periods["2024"][0].activity, 1300.5)
        self.assertAlmostEqual(periods["2024"][0].emissions, 118.75)

    def test_duplicate_rows_are_summed_not_overwritten(self):
        text = (
            "period,segment,activity,energy,emissions\n"
            "2023,A,100,50,25\n2023,A,50,20,10\n2024,A,120,60,30\n"
        )
        periods = load_periods(self._write(text))
        self.assertEqual(periods["2023"][0].activity, 150)
        self.assertEqual(periods["2023"][0].emissions, 35)

    def test_blank_rows_are_skipped(self):
        text = self.CSV + ",,,,\n"
        periods = load_periods(self._write(text))
        self.assertEqual(list(periods), ["2023", "2024"])

    def test_missing_column_is_reported_clearly(self):
        text = "period,segment,activity,energy\n2023,A,1,1\n"
        with self.assertRaises(DecompositionError) as ctx:
            load_periods(self._write(text))
        self.assertIn("emissions", str(ctx.exception))

    def test_missing_file(self):
        with self.assertRaises(DecompositionError):
            load_periods(Path("/nonexistent/nowhere.csv"))


class ReportTests(unittest.TestCase):
    def setUp(self):
        base = [seg("A", 120_000, 48_000, 15_600), seg("B", 80_000, 26_000, 10_400)]
        target = [seg("A", 131_000, 49_500, 14_200), seg("B", 74_000, 23_000, 8_900)]
        self.result = decompose(base, target, base_period="2023", target_period="2024")

    def test_summary_mentions_both_periods(self):
        text = summary(self.result)
        self.assertIn("2023", text)
        self.assertIn("2024", text)

    def test_segment_table_lists_every_segment(self):
        text = segment_table(self.result)
        self.assertIn("A", text)
        self.assertIn("B", text)

    def test_narrative_is_a_sentence_about_the_direction(self):
        text = narrative(self.result)
        self.assertTrue(text.endswith("."))
        self.assertIn("fell", text)

    def test_markdown_contains_a_table(self):
        text = to_markdown([self.result])
        self.assertIn("| Driver | Contribution |", text)
        self.assertIn("Residual", text)

    def test_as_dict_is_json_serialisable(self):
        import json

        json.dumps(self.result.as_dict())


if __name__ == "__main__":
    unittest.main(verbosity=2)
