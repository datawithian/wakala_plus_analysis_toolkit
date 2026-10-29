# Wakala Plus Analysis Toolkit (Statistical Analysis Toolkit)

A descriptive-statistics toolkit written in plain Python for the Wakala Plus risk team.
It calculates the mean, median, mode, variance, standard deviation, quartiles and IQR
outliers for the daily deposits of M-Pesa agents (Nairobi, Thika, Machakos and Nakuru),
cleans messy input, and produces a report. NumPy is used in one place only, to prove
the hand-written calculations are right.

The risk team wants a tool they understand line by line, not a black box, so every
calculation is implemented from first principles.

## Project structure

```
wakala_plus_analysis_toolkit/
├── stats_toolkit.py          # functions, StatisticsAnalyzer class, report and main()
├── test_stats_toolkit.py     # 21 unit tests (unittest)
├── data/agent_deposits.csv   # 40 daily deposit records from 4 agents
├── output/stats_report.txt   # generated report
├── requirements.txt          # numpy (verification only), pytest (optional)
└── README.md
```

## Setup

From the project folder (Git Bash on Windows shown first):

```bash
python -m venv .venv                 # or: py -m venv .venv
source .venv/Scripts/activate        # Git Bash on Windows
# source .venv/bin/activate          # macOS / Linux
pip install -r requirements.txt
```

The prompt should start with `(.venv)`. `which python` should point inside `.venv`.
If the project lives in OneDrive, consider excluding `.venv` from syncing, as it
contains thousands of small files.

## How to run

Run both commands from the project folder with the virtual environment active. The data
and output paths in the code are relative to this folder.

```bash
python -m unittest -v        # run the unit tests (pytest also works)
python stats_toolkit.py      # print the report and save output/stats_report.txt
```

Run the tests first. `python stats_toolkit.py` also runs the test suite in a separate
process and copies its summary ("Ran 21 tests ... OK") into the report, so a failing
test shows up as `FAILED` in the saved report.

## What the project required and how it was done

### 1. Mean, median and mode
**Required:** implement `mean`, `median` and `mode` in plain Python (no `statistics`
module, no NumPy). `mode` returns a list, and the treatment of "every value appears once"
must be documented.

**Done:** `mean` sums and divides. `median` sorts and takes the middle value, or the
average of the two middle values for an even count. `mode` counts occurrences in a
dictionary and returns every value with the highest count, so ties return several values.
**If every value appears exactly once, `mode` returns an empty list `[]`**, because no
value is "most common". The report prints this as `none`. Empty input raises `ValueError`.
For this dataset the mode is `none`, which is expected, because deposits are
continuous amounts with cents.

### 2. Variance and standard deviation
**Required:** `variance(values, sample)` and `std_dev(values, sample)` supporting both the
sample (n - 1) and population (n) formulas, and a README explanation of which suits the
dataset.

**Done:** both formulas are supported, and `sample=True` is the default. Each squared
deviation from the mean is summed, then divided by `n - 1` (sample) or `n` (population).
`std_dev` is the square root of the variance.

**Which one suits this dataset: the sample formulas.** The 35 valid deposit days are a
sample of how these agents behave, not every day they could ever trade, and the risk team
wants to judge what is typical. Dividing by `n - 1` (Bessel's correction) corrects the
tendency of a sample to understate the true spread. Sample variance needs at least two
values and raises `ValueError` for one, because `n - 1` would be zero. Population
variance of a single value is `0`.

### 3. Handling invalid and missing values
**Required:** `load_column(path, column)` returns the valid floats and a list of rejected
`(row_number, raw_value)` pairs. Do not guess at untrustworthy values. Every rejection
must appear in the report with a reason.

**Done:** `rejection_reason(raw_value)` decides whether a value is usable and why not.
Values are rejected, never repaired, if they are:

| Reason | Example in this dataset |
|---|---|
| missing (empty) | rows 7 and 29 |
| not a number | `-` (row 10), `n/a` (row 14), `12,40O` (row 25) |
| not finite (`nan`, `inf`) | none present |

- **Row 25 (`12,40O`)** contains the letter **O** where a zero was meant, and a comma.
  It was deliberately *not* corrected to 12,400, because guessing could hide a real
  error. A figure typed wrongly cannot be trusted.
- **Row numbers are CSV line numbers**, with the header as line 1, so they match what you
  see when you open the file in an editor.
- `load_column` reads with `utf-8-sig`, so a byte-order mark added by Excel cannot break
  the first column name. A missing column raises a clear `ValueError`.
- The report prints each rejection as `row N: 'raw value' (reason)`. "Rows read" is
  valid plus rejected: 35 + 5 = 40.

### 4. Detecting outliers with the IQR
**Required:** `quartiles(values)` and `iqr_outliers(values, k)` returning the IQR, both
fences and the outlying values. Choose a quartile method, name it, and make the NumPy
comparison use the same one.

**Done:**
- **Quartile method: linear interpolation between closest ranks (Hyndman and Fan type 7).**
  The position of a quartile is `p * (n - 1)` on the sorted data (counting from 0). If it
  falls between two values they are blended. This is NumPy's default `method="linear"`,
  so the comparison is like for like. Example: for `[10, 20, 30, 40]`, Q1 sits at position
  0.75, giving 17.5.
- **IQR** = Q3 - Q1. **Fences** are `Q1 - k * IQR` and `Q3 + k * IQR`, with `k = 1.5` by
  default. A value strictly outside the fences is an outlier. A negative `k` raises
  `ValueError`.
- `iqr_outliers` returns `q1`, `median`, `q3`, `iqr`, `lower_fence`, `upper_fence` and
  `outliers`.
- **Zero IQR:** if more than half of the values are identical, the IQR is 0 and both
  fences collapse onto that value, so any different value counts as an outlier. This is how
  the method behaves, not a bug.

### 5. The StatisticsAnalyzer class
**Required:** a `from_csv` class method, a `summary()` dict, a `without_outliers()` method
returning a new analyzer, and `report()`. Methods must not recalculate the sorted data on
every call.

**Done:**
- The data is **sorted once** in `__init__` and kept as `sorted_values`. The analyzer uses
  helpers that work on already-sorted data (`median_of_sorted`, `percentile_of_sorted`), so
  nothing is sorted again.
- `summary()` computes everything once, caches the result in `_summary`, and returns a
  copy, so callers cannot change the cached values.
- `from_csv` uses `load_column` for the values and rejections and `load_labels` for the
  date and agent of each valid row, so outliers can be named in the report.
- `without_outliers()` returns a **new** analyzer holding only the values inside the fences.
  The original analyzer is unchanged.
- `rows_read`, `rejected` and `name` are carried through so the report header is complete.
- Constructing an analyzer from an empty list raises `ValueError`.

### 6. Comparing with NumPy
**Required:** `compare_with_numpy(analyzer)` is the only place NumPy is imported. It reports
MATCH or MISMATCH per statistic using a tolerance, not `==`, and any mismatch must be
explained.

**Done:** `compare_with_numpy` returns `{name: bool}` for mean, median, variance, standard
deviation and Q1 / Q3, using `math.isclose` with a tolerance of `1e-9`. Settings chosen to
mirror the hand-written code:
- variance and standard deviation use **`ddof=1`** (sample formulas)
- quartiles use **`method="linear"`** (the same interpolation)

**Result: all five statistics MATCH.** If a mismatch ever appears, check these two settings
first. They are the usual cause: NumPy's default for `var` and `std` is `ddof=0` (population),
and `np.percentile` has several quartile methods that give different Q1 and Q3 on small
data. The mode is not compared with NumPy, because NumPy has no mode function.

### 7. The statistical summary report
**Required:** print and save `output/stats_report.txt` following the expected layout, with
statistics for all data and with outliers removed side by side, plus three sentences for the
risk team on what the outliers might mean.

**Done:** `report()` produces the layout from `expected_report.txt`: the header with rows
read, valid and rejected values (each rejection listed with its reason), the side-by-side
table (count, mean, median, mode, sample variance, sample standard deviation, min / max,
Q1 / Q3, IQR), the fences and the outliers with date and agent. `main()` then appends the
NumPy verification, the unit test result and the note for the risk team, prints everything
and saves it to `output/stats_report.txt`.

### 8. Unit tests
**Required:** at least eight passing tests using `unittest` or `pytest`, covering empty input,
even and odd lengths, ties in mode, sample vs population variance, outlier detection and
rejected values. Use small hand-checkable inputs, not the dataset.

**Done:** 21 tests in `test_stats_toolkit.py`, all passing.

| Area | What is tested |
|---|---|
| Central tendency | mean; median for even and odd lengths; mode with ties; mode with no repeats; empty input raises |
| Spread | sample vs population variance (`[2,4,6,8,10]` gives 10 and 8); sample variance needs two values; single-value standard deviation; std dev equals the square root of variance |
| Quartiles | hand-checked values for `[10,20,30,40]`; empty input raises |
| Outliers | none in uniform data; an obvious outlier (1000) is found; required result keys; negative `k` rejected; empty input rejected |
| Loading | invalid, missing and placeholder values rejected with exact row numbers and raw text; missing column raises |
| Analyzer | summary of a small list; empty dataset rejected; `without_outliers()` returns a new analyzer and leaves the original unchanged |

The loading tests write a small temporary CSV, so they never depend on or change
`agent_deposits.csv`.

## Results on this dataset

| | All data | Outliers removed |
|---|---|---|
| Count | 35 | 31 |
| Mean | 22,400.00 | 18,349.65 |
| Median | 18,805.47 | 18,506.72 |
| Variance (sample) | 328,019,873.36 | 10,116,378.52 |
| Std dev (sample) | 18,111.32 | 3,180.63 |
| Min / Max | 1,200.00 / 96,500.00 | 12,772.70 / 26,725.69 |
| Q1 / Q3 | 15,998.40 / 20,977.21 | 15,998.40 / 20,730.60 |
| IQR | 4,978.81 | 4,732.20 |

- 40 rows read, 35 valid, 5 rejected (2 missing, 3 not a number).
- Fences are 8,530.19 and 28,445.41, giving **four outliers**:
  1,200.00 (2026-10-02, AG-104), 29,060.99 (2026-10-07, AG-101),
  88,400.00 (2026-10-06, AG-104) and 96,500.00 (2026-09-20, AG-104).
- Removing them cuts the mean by about 18% and the standard deviation by about 82%, while
  the median barely moves (18,805.47 to 18,506.72). The median is far more robust to
  extreme days, which is why it is a better "typical day" for this data.
- NumPy verification: all five statistics MATCH. Unit tests: 21 run, all OK.

### Note for the risk team (also at the end of the report)
Three of the four outliers belong to AG-104 (Nakuru). The 88,400 and 96,500 KES days are
roughly five times a normal day and could mean fraud, batched deposits or a keying error
with extra digits, while the 1,200 KES day could mean a float shortage or a dropped digit.
The fourth, 29,060.99 KES at AG-101, is only just above the upper fence and is most likely a
genuinely busy day. AG-104 also has missing and garbled entries, so its figures should be
checked against M-Pesa statements before any conclusion is drawn. Outliers are flagged for
investigation, not automatically classified as errors or fraud.

## Assumptions and limitations

- **Negative deposits are not rejected.** The loader treats any finite number as valid.
  There are none in this dataset. A deposit total cannot really be negative, so a stricter
  rule could be added if one ever appears.
- **Values are pooled across all four agents.** The brief asks for one column, so agents are
  treated as one population. Agent-level analysis (for example AG-104 alone) would be a
  natural next step, and the pooled spread is partly inflated by AG-104's extreme days.
- **Thousands separators are not interpreted.** A value such as `12,400` would be rejected as
  "not a number". `12,40O` in this file is rejected for the additional reason that it
  contains a letter.
- **`-` and `n/a` are reported as "not a number"**, not as a separate "placeholder" reason.
- **The `transactions` column is not analysed.** It also contains a typo (`abc`, line 17),
  which does not affect the results because the column is never read.
- **Outliers are recalculated on the cleaned data.** `without_outliers()` removes one round
  of outliers. If the cleaned analyzer is analysed again, new fences are computed from the
  smaller data set and could flag further values. The report shows only the first round.
- **Minimum sizes.** The analyzer needs at least one value, and `summary()` also needs at
  least two, because sample variance divides by `n - 1`.
- **Run from the project folder**, because the data and output paths are relative.
- Mode ties are returned in the order they first appear in the data.

## Rules followed

- Every calculation is implemented in plain Python: no `statistics` module, and NumPy is
  imported only inside `compare_with_numpy()`.
- Function names and signatures follow the provided starter file.
- No value that cannot be trusted is guessed or repaired.
