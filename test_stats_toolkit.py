"""Unit tests for the Statistical Analysis Toolkit.

Run using:
    python -m unittest -v
"""

import csv
import unittest
import tempfile
from pathlib import Path

from stats_toolkit import (
    load_column,
    mean,
    median,
    mode,
    variance,
    std_dev,
    quartiles,
    iqr_outliers,
    StatisticsAnalyzer,
)


class TestCentralTendency(unittest.TestCase):

    def test_mean_of_known_values(self):
        self.assertEqual(mean([10, 20, 30, 40]), 25)

    def test_median_even_and_odd_lengths(self):
        # Even number of values: average the two middle values.
        self.assertEqual(median([10, 20, 30, 40]), 25)

        # Odd number of values: return the middle value.
        self.assertEqual(median([10, 20, 30]), 20)

    def test_mode_with_ties(self):
        # Both 2 and 3 occur twice, so both should be returned.
        result = mode([1, 2, 2, 3, 3, 4])

        self.assertEqual(set(result), {2, 3})

    def test_mode_with_no_repeated_values(self):
        self.assertEqual(mode([1, 2, 3, 4]), [])

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            mean([])

        with self.assertRaises(ValueError):
            median([])

        with self.assertRaises(ValueError):
            mode([])


class TestSpread(unittest.TestCase):

    def test_sample_vs_population_variance(self):
        values = [2, 4, 6, 8, 10]

        # Sample variance divides by n - 1.
        self.assertAlmostEqual(variance(values), 10)

        # Population variance divides by n.
        self.assertAlmostEqual(
            variance(values, sample=False),
            8
        )

    def test_sample_variance_requires_two_values(self):
        with self.assertRaises(ValueError):
            variance([5])

    def test_std_dev_single_value(self):
        # Population standard deviation of one value is zero.
        self.assertEqual(std_dev([5], sample=False), 0)

    def test_standard_deviation_is_square_root_of_variance(self):
        values = [2, 4, 6, 8, 10]

        self.assertAlmostEqual(
            std_dev(values),
            variance(values) ** 0.5
        )


class TestQuartiles(unittest.TestCase):

    def test_quartiles_of_known_values(self):
        # Uses linear interpolation between sorted values.
        q1, q2, q3 = quartiles([10, 20, 30, 40])

        self.assertAlmostEqual(q1, 17.5)
        self.assertAlmostEqual(q2, 25)
        self.assertAlmostEqual(q3, 32.5)

    def test_quartiles_reject_empty_input(self):
        with self.assertRaises(ValueError):
            quartiles([])


class TestOutliers(unittest.TestCase):

    def test_no_outliers_in_uniform_data(self):
        result = iqr_outliers([10, 10, 10, 10, 10])

        self.assertEqual(result["outliers"], [])
        self.assertEqual(result["iqr"], 0)

    def test_detects_obvious_outlier(self):
        values = [10, 11, 12, 13, 14, 15, 1000]

        result = iqr_outliers(values)

        self.assertIn(1000, result["outliers"])

    def test_outlier_result_contains_required_keys(self):
        result = iqr_outliers([10, 20, 30, 40, 50])

        required_keys = {
            "q1",
            "median",
            "q3",
            "iqr",
            "lower_fence",
            "upper_fence",
            "outliers",
        }

        self.assertTrue(required_keys.issubset(result.keys()))

    def test_negative_k_is_rejected(self):
        with self.assertRaises(ValueError):
            iqr_outliers([10, 20, 30], k=-1)

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            iqr_outliers([])


class TestLoading(unittest.TestCase):

    def test_invalid_and_missing_values_are_rejected(self):
        # Create a temporary CSV so the test does not change
        # your actual dataset.
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "test_deposits.csv"

            with open(
                csv_path,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["daily_deposits_kes"]
                )

                writer.writeheader()
                writer.writerow({"daily_deposits_kes": "1000"})     # line 2: valid
                writer.writerow({"daily_deposits_kes": "invalid"})  # line 3: rejected
                writer.writerow({"daily_deposits_kes": ""})         # line 4: rejected
                writer.writerow({"daily_deposits_kes": "2500"})     # line 5: valid
                writer.writerow({"daily_deposits_kes": "-"})        # line 6: rejected
                writer.writerow({"daily_deposits_kes": "n/a"})      # line 7: rejected

            valid_values, rejected = load_column(
                csv_path,
                "daily_deposits_kes"
            )

            self.assertEqual(valid_values, [1000.0, 2500.0])

            # Row numbers are CSV line numbers (the header is line 1),
            # and the raw text is kept exactly as it was written.
            self.assertEqual(
                rejected,
                [(3, "invalid"), (4, ""), (6, "-"), (7, "n/a")]
            )

    def test_missing_column_raises_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "test_deposits.csv"

            with open(
                csv_path,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["daily_deposits_kes"]
                )
                writer.writeheader()
                writer.writerow({"daily_deposits_kes": "1000"})

            with self.assertRaises(ValueError):
                load_column(csv_path, "unknown_column")


class TestStatisticsAnalyzer(unittest.TestCase):

    def test_analyzer_summary(self):
        analyzer = StatisticsAnalyzer([10, 20, 30, 40])

        results = analyzer.summary()

        self.assertEqual(results["count"], 4)
        self.assertEqual(results["total"], 100)
        self.assertEqual(results["mean"], 25)
        self.assertEqual(results["median"], 25)

    def test_analyzer_rejects_empty_dataset(self):
        with self.assertRaises(ValueError):
            StatisticsAnalyzer([])

    def test_without_outliers_returns_new_analyzer(self):
        original = StatisticsAnalyzer([1, 2, 3, 4, 5, 100])
        cleaned = original.without_outliers()

        # A different object, and the original is left unchanged.
        self.assertIsNot(original, cleaned)
        self.assertEqual(len(original.sorted_values), 6)
        self.assertEqual(original.summary()["count"], 6)

        # The outlier (100) is gone from the new analyzer.
        self.assertEqual(len(cleaned.sorted_values), 5)
        self.assertEqual(cleaned.summary()["count"], 5)
        self.assertNotIn(100, cleaned.sorted_values)


if __name__ == "__main__":
    unittest.main(verbosity=2)