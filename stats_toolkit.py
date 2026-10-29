"""
Statistical Analysis Toolkit

"""
import csv
import math
import subprocess
import sys
from pathlib import Path

DATA_PATH = Path("data") / "agent_deposits.csv"
REPORT_PATH = Path("output") / "stats_report.txt"


def rejection_reason(raw_value: str | None) -> str | None:
    """Return why a raw value is unusable, or None if it is a good number."""
    if raw_value is None or not raw_value.strip():
        return "missing"
    try:
        value = float(raw_value.strip())
    except ValueError:
        return "not a number"      
    if not math.isfinite(value):
        return "not finite"
    
    return None


def load_column(path: Path, column: str) -> tuple[list[float], list[tuple[int, str]]]:
    valid_values = []
    rejected = []

    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise ValueError(f"Column '{column}' not found in the CSV file.")

        for row_number, row in enumerate(reader, start=2):
            raw_value = row.get(column)
            if rejection_reason(raw_value) is None:
                valid_values.append(float(raw_value.strip()))
            else:
                rejected.append((row_number, raw_value or ""))

    return valid_values, rejected


def load_labels(path: Path, column: str) -> list[tuple[float, str, str]]:
    """Return (value, date, agent_id) for every valid row, in file order."""
    records = []
    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            raw_value = row.get(column)
            if rejection_reason(raw_value) is None:
                records.append((float(raw_value.strip()), row["date"], row["agent_id"]))
    return records

def median_of_sorted(sorted_values: list[float]) -> float:
    n = len(sorted_values)
    middle = n // 2
    if n % 2 == 1:
        return sorted_values[middle]
    return (sorted_values[middle - 1] + sorted_values[middle]) / 2


def percentile_of_sorted(sorted_values: list[float], p: float) -> float:
    position = (len(sorted_values) - 1) * p
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + fraction * (upper - lower)


def mean(values: list[float]) -> float:
    """Calculate the arithmetic mean."""
    if not values:
        raise ValueError("Cannot calculate mean of an empty list.")

    return sum(values) / len(values)


def median(values):
    if not values:
        raise ValueError("Cannot calculate median of an empty list.")
    return median_of_sorted(sorted(values))


def mode(values: list[float]) -> list[float]:
    """Return all modes, or an empty list if no values repeat."""
    if not values:
        raise ValueError("Cannot calculate mode of an empty list.")

    frequencies = {}

    for value in values:
        frequencies[value] = frequencies.get(value, 0) + 1

    highest_frequency = max(frequencies.values())

    if highest_frequency == 1:
        return []

    return [
        value
        for value, frequency in frequencies.items()
        if frequency == highest_frequency
    ]


def variance(values: list[float], sample: bool = True) -> float:
    """Calculate sample or population variance."""
    n = len(values)

    if n == 0:
        raise ValueError("Cannot calculate variance of an empty list.")

    if sample and n < 2:
        raise ValueError("Sample variance requires at least two values.")

    average = mean(values)

    squared_deviations = [
        (value - average) ** 2
        for value in values
    ]

    denominator = n - 1 if sample else n

    return sum(squared_deviations) / denominator


def std_dev(values: list[float], sample: bool = True) -> float:
    return math.sqrt(variance(values, sample))


def quartiles(values):
    """Return (Q1, Q2, Q3) using linear interpolation
    (Hyndman & Fan type 7, the same as NumPy's default method="linear")."""
    if not values:
        raise ValueError("Cannot calculate quartiles of an empty list.")
    s = sorted(values)
    return (percentile_of_sorted(s, 0.25),
            percentile_of_sorted(s, 0.50),
            percentile_of_sorted(s, 0.75))


def iqr_outliers(
    values: list[float],
    k: float = 1.5
) -> dict:
    """Identify outliers using the IQR method."""
    if not values:
        raise ValueError("Cannot detect outliers in an empty list.")

    if k < 0:
        raise ValueError("k must be non-negative.")

    q1, q2, q3 = quartiles(values)

    iqr = q3 - q1
    lower_fence = q1 - (k * iqr)
    upper_fence = q3 + (k * iqr)

    outliers = [
        value
        for value in values
        if value < lower_fence or value > upper_fence
    ]

    return {
        "q1": q1,
        "median": q2,
        "q3": q3,
        "iqr": iqr,
        "lower_fence": lower_fence,
        "upper_fence": upper_fence,
        "outliers": outliers,
    }


class StatisticsAnalyzer:
    """Wraps one numeric column and exposes every statistic as a method."""

    def __init__(
        self,
        values: list[float],
        name: str = "values",
        records: list[tuple] | None = None,
        rows_read: int | None = None,
        rejected: list[tuple[int, str]] | None = None,
    ) -> None:
        if not values:
            raise ValueError("Cannot analyze an empty dataset.")

        self.name = name
        self.sorted_values = sorted(values)     # sorted ONCE, reused everywhere
        self.records = records or []            
        self.rejected = rejected or []          
        self.rows_read = rows_read if rows_read is not None else len(values) + len(self.rejected)

        self._summary = None            
    @classmethod
    def from_csv(cls, path: Path, column: str) -> "StatisticsAnalyzer":
        values, rejected = load_column(path, column)
        records = load_labels(path, column)
        return cls(values, name=column, records=records, rejected=rejected)

    def summary(self) -> dict:
        if self._summary is None:
            s = self.sorted_values
            q1 = percentile_of_sorted(s, 0.25)
            q2 = percentile_of_sorted(s, 0.50)
            q3 = percentile_of_sorted(s, 0.75)
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr

            self._summary = {
                "count": len(s),
                "total": sum(s),
                "mean": mean(s),
                "median": median_of_sorted(s),
                "mode": mode(s),
                "sample_variance": variance(s),
                "sample_std_dev": std_dev(s),
                "population_variance": variance(s, sample=False),
                "population_std_dev": std_dev(s, sample=False),
                "min": s[0],
                "max": s[-1],
                "q1": q1,
                "q2": q2,
                "q3": q3,
                "iqr": iqr,
                "lower_fence": lower_fence,
                "upper_fence": upper_fence,
                "outliers": [v for v in s if v < lower_fence or v > upper_fence],
            }

        return self._summary.copy()

    def without_outliers(self) -> "StatisticsAnalyzer":
        """Return a NEW analyzer with the IQR outliers removed. This one is unchanged."""
        summary = self.summary()
        low = summary["lower_fence"]
        high = summary["upper_fence"]

        kept_values = [v for v in self.sorted_values if low <= v <= high]
        kept_records = [r for r in self.records if low <= r[0] <= high]

        return StatisticsAnalyzer(
            kept_values,
            name=self.name,
            records=kept_records,
            rows_read=self.rows_read,
            rejected=self.rejected,
        )

    def report(self) -> str:
        all_data = self.summary()
        clean = self.without_outliers().summary()

        def num(x):
            return "n/a" if x is None else f"{x:,.2f}"

        def modes(values):
            return ", ".join(num(v) for v in values) if values else "none"

        def line(label, left, right):
            return f"{label:<20}{left:<22}{right}"

        lines = [
            f"=== Statistics report: {self.name} ===",
            f"Rows read         : {self.rows_read}",
            f"Valid values      : {all_data['count']}",
            f"Rejected values   : {len(self.rejected)}",
        ]
        for row_number, raw_value in self.rejected:
            lines.append(f"  row {row_number}: {raw_value!r} ({rejection_reason(raw_value)})")

        lines += [
            "",
            line("", "all data", "outliers removed"),
            line("count", all_data["count"], clean["count"]),
            line("mean", num(all_data["mean"]), num(clean["mean"])),
            line("median", num(all_data["median"]), num(clean["median"])),
            line("mode", modes(all_data["mode"]), modes(clean["mode"])),
            line("variance (sample)", num(all_data["sample_variance"]), num(clean["sample_variance"])),
            line("std dev (sample)", num(all_data["sample_std_dev"]), num(clean["sample_std_dev"])),
            line("min / max", f"{num(all_data['min'])} / {num(all_data['max'])}",
                 f"{num(clean['min'])} / {num(clean['max'])}"),
            line("Q1 / Q3", f"{num(all_data['q1'])} / {num(all_data['q3'])}",
                 f"{num(clean['q1'])} / {num(clean['q3'])}"),
            line("IQR", num(all_data["iqr"]), num(clean["iqr"])),
            "",
            f"Outlier fences      : lower {num(all_data['lower_fence'])}, "
            f"upper {num(all_data['upper_fence'])}",
        ]

        low, high = all_data["lower_fence"], all_data["upper_fence"]
        names = [f"{num(value)} ({date}, {agent})"
                 for value, date, agent in sorted(self.records)
                 if value < low or value > high]
        if not names:                     
            names = [num(v) for v in all_data["outliers"]]
        lines.append("Outliers            : " + (", ".join(names) if names else "none"))

        return "\n".join(lines)


def compare_with_numpy(analyzer: StatisticsAnalyzer) -> dict[str, bool]:
    """Import numpy HERE, recompute each statistic and return {name: matches}."""
    import numpy as np

    values = analyzer.sorted_values
    results = analyzer.summary()
    numpy_q1, numpy_q3 = np.percentile(values, [25, 75], method="linear")

    def same(ours, theirs):
        return math.isclose(ours, float(theirs), rel_tol=1e-9, abs_tol=1e-9)

    return {
        "mean": same(results["mean"], np.mean(values)),
        "median": same(results["median"], np.median(values)),
        "variance": same(results["sample_variance"], np.var(values, ddof=1)),
        "std dev": same(results["sample_std_dev"], np.std(values, ddof=1)),
        "Q1 / Q3": same(results["q1"], numpy_q1) and same(results["q3"], numpy_q3),
    }


def numpy_section(analyzer: StatisticsAnalyzer) -> str:
    results = compare_with_numpy(analyzer)

    def tag(name):
        return "MATCH" if results[name] else "MISMATCH"

    return "\n".join([
        "=== NumPy verification ===",
        f"mean      {tag('mean')}",
        f"median    {tag('median')}",
        f"variance  {tag('variance')}  (ddof=1)",
        f"std dev   {tag('std dev')}",
        f"Q1 / Q3   {tag('Q1 / Q3')}  (method=linear)",
    ])


def unit_test_section() -> str:
    """Run the unit tests and return their summary lines."""
    folder = Path(__file__).resolve().parent
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "test_stats_toolkit"],
        cwd=folder, capture_output=True, text=True,
    )
    lines = [ln for ln in result.stderr.strip().splitlines() if ln.strip()]
    return "\n".join(["=== Unit tests ===", lines[-2], lines[-1]])


RISK_NOTE = (
       "=== Note for the risk team ===\n"
       "Three of the four outliers belong to AG-104 (Nakuru): the 88,400 and 96,500 KES days are "
       "roughly five times a normal day and could mean fraud, batched deposits or a keying error "
       "with extra digits, while the 1,200 KES day could mean a float shortage or a dropped digit. "
       "The fourth, 29,060.99 KES at AG-101, is only just above the upper fence and is most likely "
       "a genuinely busy day. AG-104 also has missing and entries, so its figures should be "
       "checked against M-Pesa statements before any conclusion is drawn."
   )


def main() -> None:
    analyzer = StatisticsAnalyzer.from_csv(DATA_PATH, "daily_deposits_kes")
    text = "\n\n".join([
        analyzer.report(),
        numpy_section(analyzer),
        unit_test_section(),
        RISK_NOTE,
    ])
    print(text)

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
