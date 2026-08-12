"""Test suite for target-path. Standard library only: python3 -m unittest discover -s tests -t ."""

from __future__ import annotations

import sys
import random
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from target_path.pathway import (  # noqa: E402
    REFERENCE_RATES,
    TargetError,
    absolute_contraction,
    assess,
    compare,
    intensity_convergence,
    required_rate,
)


class AbsoluteContractionTests(unittest.TestCase):
    def setUp(self):
        self.p = absolute_contraction(100_000.0, 2020, 2030, 0.042)

    def test_starts_at_the_base_year_value(self):
        self.assertEqual(self.p.at(2020).emissions, 100_000.0)

    def test_endpoint_matches_the_closed_form(self):
        # 10 years at 4.2 points of the base year each = 42% removed.
        self.assertAlmostEqual(self.p.target_emissions, 58_000.0, places=6)
        self.assertAlmostEqual(self.p.total_reduction, 0.42, places=10)

    def test_the_path_is_a_straight_line(self):
        steps = [
            self.p.points[i + 1].emissions - self.p.points[i].emissions
            for i in range(len(self.p.points) - 1)
        ]
        for step in steps:
            self.assertAlmostEqual(step, steps[0], places=6)
        self.assertAlmostEqual(steps[0], -4_200.0, places=6)

    def test_linear_is_stricter_than_compounding_at_the_same_headline_rate(self):
        compounding = 100_000.0 * (1 - 0.042) ** 10
        self.assertLess(self.p.target_emissions, compounding)

    def test_budget_matches_the_trapezoid_of_a_straight_line(self):
        # For a line, the trapezoidal integral is the mean of the endpoints
        # times the span.
        expected = 0.5 * (100_000.0 + 58_000.0) * 10
        self.assertAlmostEqual(self.p.budget(), expected, places=4)

    def test_one_point_per_year_inclusive(self):
        self.assertEqual(len(self.p.points), 11)

    def test_rate_that_would_cross_zero_is_rejected(self):
        with self.assertRaises(TargetError):
            absolute_contraction(100.0, 2020, 2050, 0.042)  # 30 x 4.2% > 100%

    def test_invalid_inputs(self):
        with self.assertRaises(TargetError):
            absolute_contraction(0.0, 2020, 2030, 0.042)
        with self.assertRaises(TargetError):
            absolute_contraction(100.0, 2030, 2020, 0.042)
        with self.assertRaises(TargetError):
            absolute_contraction(100.0, 2020, 2030, 1.5)
        with self.assertRaises(TargetError):
            absolute_contraction(100.0, 2020, 2030, 0.0)

    def test_year_outside_the_pathway(self):
        with self.assertRaises(TargetError):
            self.p.at(2035)

    def test_reference_rates_are_plausible(self):
        # Pinned so a typo in the constants cannot pass silently. These are
        # indicative values, not an authority; see the README.
        self.assertEqual(REFERENCE_RATES["1.5C"], 0.042)
        self.assertLess(REFERENCE_RATES["well-below-2C"], REFERENCE_RATES["1.5C"])


class IntensityConvergenceTests(unittest.TestCase):
    ACTIVITY = {y: 1_000.0 for y in range(2020, 2031)}

    def test_with_flat_activity_it_reduces_to_absolute_contraction(self):
        intensity = intensity_convergence(10.0, self.ACTIVITY, 2020, 2030, 0.042)
        absolute = absolute_contraction(10_000.0, 2020, 2030, 0.042)
        for a, b in zip(intensity.points, absolute.points):
            self.assertAlmostEqual(a.emissions, b.emissions, places=6)

    def test_absolute_emissions_can_rise_while_intensity_falls(self):
        # Activity doubles over the decade against a 4.2% intensity path.
        growing = {2020 + n: 1_000.0 * (1 + 0.1 * n) for n in range(11)}
        p = intensity_convergence(10.0, growing, 2020, 2030, 0.042)
        self.assertLess(p.points[-1].intensity, p.points[0].intensity)
        self.assertGreater(p.target_emissions, p.base_emissions)
        # ... and the tool must not report that as a reduction.
        self.assertLess(p.total_reduction, 0)

    def test_missing_activity_year_is_rejected_rather_than_interpolated(self):
        incomplete = dict(self.ACTIVITY)
        del incomplete[2025]
        with self.assertRaises(TargetError) as ctx:
            intensity_convergence(10.0, incomplete, 2020, 2030, 0.042)
        self.assertIn("2025", str(ctx.exception))

    def test_negative_base_intensity_rejected(self):
        with self.assertRaises(TargetError):
            intensity_convergence(-1.0, self.ACTIVITY, 2020, 2030, 0.042)


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.p = absolute_contraction(100_000.0, 2020, 2030, 0.042)

    def test_exactly_on_the_pathway_is_on_track_with_zero_gap(self):
        a = assess(self.p, 2025, self.p.at(2025).emissions)
        self.assertAlmostEqual(a.gap, 0.0, places=6)
        self.assertTrue(a.on_track)

    def test_behind_the_pathway(self):
        a = assess(self.p, 2025, 85_000.0)
        self.assertGreater(a.gap, 0)
        self.assertFalse(a.on_track)

    def test_being_on_track_leaves_the_original_rate_intact(self):
        # If actuals sit exactly on the line, the rate still needed from here,
        # expressed against today's level, must reproduce the same straight
        # line to the same endpoint.
        year = 2025
        actual = self.p.at(year).emissions
        a = assess(self.p, year, actual)
        rate_now = a.required_rate_from_here()
        rebuilt = absolute_contraction(actual, year, 2030, rate_now)
        self.assertAlmostEqual(
            rebuilt.target_emissions, self.p.target_emissions, places=6
        )

    def test_falling_behind_raises_the_rate_needed(self):
        on_track = assess(self.p, 2025, self.p.at(2025).emissions)
        behind = assess(self.p, 2025, 90_000.0)
        self.assertGreater(
            behind.required_rate_from_here(), on_track.required_rate_from_here()
        )

    def test_required_rate_after_the_target_year_is_an_error(self):
        a = assess(self.p, 2030, 58_000.0)
        with self.assertRaises(TargetError):
            a.required_rate_from_here()

    def test_cumulative_overshoot_is_zero_on_the_pathway(self):
        actuals = {p.year: p.emissions for p in self.p.points}
        a = assess(self.p, 2030, actuals[2030])
        self.assertAlmostEqual(a.cumulative_overshoot(actuals), 0.0, places=6)

    def test_endpoint_compliance_can_hide_a_cumulative_overshoot(self):
        # Flat until the last year, then a cliff straight onto the endpoint.
        actuals = {y: 100_000.0 for y in range(2020, 2030)}
        actuals[2030] = self.p.target_emissions
        a = assess(self.p, 2030, actuals[2030])
        self.assertAlmostEqual(a.gap, 0.0, places=6)  # hits the target exactly
        self.assertGreater(a.cumulative_overshoot(actuals), 0)  # but blew the budget

    def test_overshoot_outside_the_pathway_is_rejected(self):
        a = assess(self.p, 2025, 80_000.0)
        with self.assertRaises(TargetError):
            a.cumulative_overshoot({2019: 100_000.0})

    def test_negative_actual_rejected(self):
        with self.assertRaises(TargetError):
            assess(self.p, 2025, -1.0)


class RequiredRateTests(unittest.TestCase):
    def test_round_trips_with_absolute_contraction(self):
        rate = required_rate(100_000.0, 58_000.0, 2020, 2030)
        self.assertAlmostEqual(rate, 0.042, places=10)

    def test_rejects_a_non_positive_span(self):
        with self.assertRaises(TargetError):
            required_rate(100.0, 50.0, 2030, 2030)

    def test_rejects_zero_base(self):
        with self.assertRaises(TargetError):
            required_rate(0.0, 50.0, 2020, 2030)


class CompareTests(unittest.TestCase):
    def test_a_higher_rate_gives_a_lower_endpoint_and_a_smaller_budget(self):
        low = absolute_contraction(100_000.0, 2020, 2030, 0.025)
        high = absolute_contraction(100_000.0, 2020, 2030, 0.042)
        rows = compare([low, high])
        self.assertEqual(len(rows), 2)
        self.assertGreater(rows[0][1], rows[1][1])  # endpoint
        self.assertGreater(rows[0][3], rows[1][3])  # budget


class BudgetPreservingRebase(unittest.TestCase):
    """Landing on the endpoint is not the same as staying inside the budget.

    ``required_rate_from_here`` answers "what gets me to the target number".
    ``budget_preserving_rate`` answers "what keeps cumulative emissions inside
    what the pathway allowed". After an overshoot those are different numbers,
    and the second is the one the atmosphere responds to.
    """

    def setUp(self):
        self.pathway = absolute_contraction(100_000.0, 2020, 2030, 0.042)

    def on_track_actuals(self, through=2025):
        return {y: self.pathway.at(y).emissions for y in range(2020, through + 1)}

    def test_spent_plus_remaining_reconstructs_the_budget(self):
        # The trapezoidal rule is additive across a shared node, which is the
        # only reason subtracting one from the other is meaningful.
        for year in range(2021, 2030):
            actuals = self.on_track_actuals(year)
            a = assess(self.pathway, year, self.pathway.at(year).emissions)
            self.assertAlmostEqual(
                a.spent(actuals) + a.remaining_budget(actuals),
                self.pathway.budget(), places=6, msg=str(year),
            )

    def test_on_track_the_two_rebasings_agree_exactly(self):
        # If nothing has been overspent there is nothing to claw back, so the
        # budget-preserving rate must collapse onto the endpoint rate.
        for year in range(2021, 2030):
            actuals = self.on_track_actuals(year)
            a = assess(self.pathway, year, self.pathway.at(year).emissions)
            self.assertAlmostEqual(
                a.budget_preserving_rate(actuals),
                a.required_rate_from_here(), places=9, msg=str(year),
            )

    def test_the_rebased_pathway_spends_exactly_the_remaining_budget(self):
        # The conservation law: build the path the rate implies, integrate it,
        # and it must come to the allowance that was left.
        rng = random.Random(2026)
        for _ in range(200):
            year = rng.randint(2021, 2028)
            actuals = self.on_track_actuals(year)
            # Overspend by a random amount in one random year.
            slipped = rng.randint(2021, year)
            actuals[slipped] *= 1.0 + rng.uniform(0.0, 0.15)
            a = assess(self.pathway, year, actuals[year])
            try:
                rebased = a.budget_preserving_pathway(actuals)
            except TargetError:
                continue          # infeasible cases are asserted separately
            self.assertAlmostEqual(
                rebased.budget(), a.remaining_budget(actuals), places=4,
                msg=f"year {year}",
            )

    def test_an_overshoot_makes_the_budget_rate_strictly_stricter(self):
        actuals = self.on_track_actuals(2025)
        actuals[2023] *= 1.10
        a = assess(self.pathway, 2025, actuals[2025])
        self.assertGreater(
            a.budget_preserving_rate(actuals), a.required_rate_from_here()
        )

    def test_undershooting_makes_it_looser(self):
        actuals = self.on_track_actuals(2025)
        actuals[2023] *= 0.90
        a = assess(self.pathway, 2025, actuals[2025])
        self.assertLess(
            a.budget_preserving_rate(actuals), a.required_rate_from_here()
        )

    def test_the_rate_increases_monotonically_with_the_overshoot(self):
        previous = None
        for excess in (0.0, 0.02, 0.05, 0.10, 0.20):
            actuals = self.on_track_actuals(2025)
            actuals[2023] *= 1.0 + excess
            a = assess(self.pathway, 2025, actuals[2025])
            rate = a.budget_preserving_rate(actuals)
            if previous is not None:
                self.assertGreater(rate, previous, msg=str(excess))
            previous = rate

    def test_after_an_overshoot_the_endpoint_drops_below_the_original_target(self):
        # Paying back the overspend means finishing lower than promised.
        actuals = self.on_track_actuals(2025)
        actuals[2023] *= 1.10
        a = assess(self.pathway, 2025, actuals[2025])
        rebased = a.budget_preserving_pathway(actuals)
        self.assertLess(rebased.target_emissions, self.pathway.target_emissions)
        self.assertEqual(rebased.target_year, self.pathway.target_year)

    def test_a_spent_budget_is_reported_as_unrecoverable(self):
        # Massive early overshoot: no future path claws it back.
        actuals = self.on_track_actuals(2025)
        for year in range(2021, 2026):
            actuals[year] *= 3.0
        a = assess(self.pathway, 2025, actuals[2025])
        with self.assertRaises(TargetError) as ctx:
            a.budget_preserving_pathway(actuals)
        self.assertIn("cannot be preserved", str(ctx.exception))

    def test_being_far_ahead_is_reported_rather_than_returned_as_a_pathway(self):
        actuals = {y: self.pathway.at(y).emissions * 0.2 for y in range(2020, 2026)}
        a = assess(self.pathway, 2025, actuals[2025])
        self.assertLessEqual(a.budget_preserving_rate(actuals), 0.0)
        with self.assertRaises(TargetError) as ctx:
            a.budget_preserving_pathway(actuals)
        self.assertIn("room to spare", str(ctx.exception))

    def test_a_missing_year_is_refused_rather_than_skipped(self):
        # Skipping a year would shrink the integral and understate the
        # overspend -- the one direction this number must never err in.
        actuals = self.on_track_actuals(2025)
        del actuals[2023]
        a = assess(self.pathway, 2025, actuals[2025])
        with self.assertRaises(TargetError) as ctx:
            a.spent(actuals)
        self.assertIn("2023", str(ctx.exception))

    def test_the_base_year_alone_has_spent_nothing(self):
        a = assess(self.pathway, 2020, 100_000.0)
        self.assertEqual(a.spent({2020: 100_000.0}), 0.0)

    def test_rebasing_in_the_target_year_is_refused(self):
        actuals = self.on_track_actuals(2030)
        a = assess(self.pathway, 2030, actuals[2030])
        with self.assertRaises(TargetError):
            a.budget_preserving_rate(actuals)


if __name__ == "__main__":
    unittest.main(verbosity=2)
