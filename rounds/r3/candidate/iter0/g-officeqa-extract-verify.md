---
name: g-officeqa-extract-verify
description: >
  Mandatory data extraction, verification, calculation, and formatting protocol
  for U.S. Treasury Bulletin questions. Activate AFTER g-officeqa-locate-source
  has identified the source file(s). This skill governs HOW to read tables,
  verify values, compute results, and format the final answer. Every step is
  mandatory and must be executed in order.
tags:
  - officeqa
  - treasury-bulletin
  - extraction
  - verification
  - calculation
  - formatting
---

# Extract, Verify, Calculate, and Format Treasury Bulletin Data

## When to use

Use this skill AFTER g-officeqa-locate-source has identified the bulletin
file(s). This skill covers table identification, column mapping, value
extraction, cross-validation, calculation, and answer formatting.

## Mandatory procedure

### Step 1 — Identify the table

Search the bulletin for the relevant table by name or number using Grep.
Common table families:
- FFO-3 / FFD-3: Budget Outlays by Agency (on-budget and off-budget)
- FD-1: Summary of Federal Debt
- MY-2 / Table 1: Average Yields of Treasury and Corporate Bonds
- MQ-1: Treasury Bills market quotations
- PDO-3: Public Offerings of Marketable Securities
- SB-4: Savings Bonds redemptions
- OFS-2: Estimated Ownership of U.S. Treasury Securities
- CM-I-1 / CM-I-3: Liabilities by country
- TSO-1: Summary of Federal Securities

Record the table name, the line number where the table header begins, and
the units statement (e.g., "In millions of dollars", "In thousands of
dollars", "Percent").

CHECKPOINT: Confirm the units stated in the table match what the question
expects. If the table is in thousands and the question asks for millions,
note the conversion factor now.

### Step 2 — Read and map column headers

Read the full header row of the table. Map each column to its meaning:
- Which column is which month, year, or agency.
- Which column is the data series the question asks about.
- Note that column order can change across eras (e.g., Homeland Security
  column appears only post-2003; agency column numbering shifts).

For tables with multi-row headers (common in pandas-extracted tables), read
all header rows and reconstruct the full column labels.

### Step 3 — Verify column mapping

Before trusting any extracted value, verify the column mapping using an
internal consistency check:
- For monthly tables with an annual total column: sum the 12 monthly columns
  for a sample row and confirm they equal the annual total column.
- For tables with subtotals: confirm that sub-components sum to the total.
- If the consistency check fails, re-examine the column headers — the
  columns may be shifted or mislabeled.

CHECKPOINT: If the consistency check fails, STOP and re-read the headers.
Do not proceed with incorrect column mapping.

### Step 4 — Extract the target value(s)

Read the specific data row(s) containing the target period. Record:
- The exact line number.
- The raw text of the row as it appears in the file.
- The extracted numeric value.
- The units.

Handle common data quality issues:
- OCR errors in column headers (e.g., "Salee" instead of "Sales") — verify
  against the same table in a different bulletin issue.
- Footnote markers (r, p, 1/, etc.) appended to values — strip them before
  using the numeric value.
- "nan" or "-" entries — these represent missing or zero values.
- Revised values marked with "r" — use the revised value.

### Step 5 — Cross-validate

If the same data appears in another bulletin issue (e.g., a later bulletin
that shows historical data), extract the same value from that bulletin and
confirm it matches. This catches transcription errors and OCR issues.

Cross-validation is especially important when:
- The value is from an older bulletin with known OCR issues.
- The column mapping was difficult to determine.
- The question involves a long time series where a single misread value
  would propagate errors.

### Step 6 — Perform the calculation

Execute the calculation using Python (via Bash tool) for any non-trivial
arithmetic. Do not rely on mental math for:
- Sums of more than 3 values.
- Any regression, geometric mean, logarithm, exponentiation, or statistical
  function.
- Any inflation adjustment, CAGR, or compound growth calculation.
- Any unit conversion.

Write the full calculation as a Python script with all input values
explicitly listed, so the computation is reproducible and auditable.

### Step 7 — Independently verify the calculation

Re-compute the result using a different method or library where possible:
- For OLS regression: use both the manual formula and numpy.polyfit or
  scipy.stats.linregress.
- For geometric mean: use both exp(mean(log(values))) and the product-based
  formula.
- For CAGR: verify by back-computing (apply the rate and confirm you
  recover the end value).

If the two methods disagree, investigate the discrepancy before reporting.

CHECKPOINT: The two methods must agree to at least 6 significant figures.
If they do not, re-examine the input data and the formula.

### Step 8 — Format the answer

Apply the question's formatting requirements exactly:
- Rounding: round to the specified precision (hundredths, thousandths,
  tenths, whole number, etc.). Use proper rounding (round half up).
- Units: report in the units the question requests (millions, billions,
  percent, decimal). Convert if the data is in different units.
- Percent vs decimal: if the question says "decimal value (if 12.34% is
  percent, 0.1234 is decimal)", convert percent to decimal.
- Format: if the question asks for square brackets with comma-separated
  values, output [value1, value2, value3]. If it asks for a single number,
  output just the number.
- Negative values: use a minus sign, not parentheses.

CHECKPOINT: Re-read the question's formatting instruction one final time
and confirm the answer matches it exactly. A mathematically correct answer
in the wrong format is still wrong.

## Failure and fallback

- If the table cannot be found by name, search by content keywords (e.g.,
  the agency name, the data series description).
- If the column mapping cannot be verified by internal consistency (e.g.,
  the table has no annual total column), rely on cross-validation with
  another bulletin issue instead.
- If cross-validation reveals a discrepancy, prefer the value from the
  bulletin closest to the data's original reporting period (revisions can
  change values).
- If the calculation cannot be independently verified by a second method,
  proceed but flag the result as single-method only.
- If the question asks for a calculation method you are unsure about (e.g.,
  "expected shortfall using historical portfolio return approach"),
  implement the standard textbook definition and verify the result is
  economically sensible (e.g., ES should be within the data range).

## Common pitfalls

- Confusing fiscal year with calendar year — FY 1961 is Oct 1960 to Sep
  1961, not January to December 1961.
- Mixing units — a table in thousands of dollars when the question asks for
  millions requires dividing by 1000.
- Forgetting that some tables report negative values (e.g., offsetting
  receipts) — do not take absolute values unless the question asks for it.
- Using the published annual total instead of summing monthly values when
  the question explicitly says "using the reported monthly values" — the
  annual total may differ due to rounding.
- Rounding intermediate results — keep full precision throughout the
  calculation and round only the final answer.
