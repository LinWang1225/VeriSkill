---
name: g-officeqa-extract-verify
description: Extract numeric values from a located Treasury Bulletin table, verify column/header mapping and unit scale, compute the requested aggregate, cross-validate, round per the question spec, and format the final answer. Use after the source issue and table have been identified by g-officeqa-locate-source.
tags:
  - officeqa
  - treasury-bulletin
  - data-extraction
  - column-mapping
  - computation
  - cross-validation
  - rounding
  - output-formatting
---

# Extract, verify, compute, and format Treasury Bulletin answers

## When to activate
- The source bulletin file and table have been identified (by g-officeqa-locate-source or equivalent).
- The question requires reading specific numeric cells, mapping columns to periods or categories, computing an aggregate, and returning a rounded, formatted answer.

## Step 1 — Read and lock the table structure
- Read the table header rows (column labels and any multi-row super-headers) and the unit declaration line (e.g., "in thousands of dollars", "In millions of dollars").
- Record the unit scale stated in the table. Do not assume a unit; mismatched units are a top error source.
- For multi-block tables where several years share one row block distinguished by column groups (suffixes like `.1`, `.2`, `.3`), build an explicit year-to-column-group map. Confirm the map by reading a nearby legend or by checking that a known year's label aligns with its column group.

## Step 2 — Verify column mapping before extracting
- When the table has monthly columns, confirm the mapping by summing all monthly columns for one row and checking the sum equals the stated annual total column. If they match, the column order is confirmed; if not, re-examine the header.
- When columns are grouped by year across blocks, pick one row whose value you can independently identify and confirm it lands in the expected column group.
- Record the verification arithmetic as evidence.

## Step 3 — Extract the target cells
- For each requested row (identified by its row label, e.g., a commodity name, a security series, a liability type) and each requested column, read the exact numeric value from the located line.
- Record file, line number, row label, and the raw value as evidence for every cell.
- If a value is marked `nan` or missing, note it explicitly and determine whether the question expects it to be treated as zero or excluded.

## Step 4 — Unit conversion
- Convert all extracted values to the unit the question requests before computing.
- Common conversions: thousands to millions (divide by 1000), millions to nominal dollars (multiply by 1,000,000). Keep the conversion factor recorded with the work.
- Never mix units inside one computation.

## Step 5 — Compute the requested aggregate
Apply the operation the question specifies. Common operations and their precise definitions:
- **Sum / absolute difference**: straightforward; preserve sign only if asked.
- **Percentage / ratio**: compute `part / total * 100`; confirm which value is the denominator from the question wording.
- **Geometric mean**: use the product raised to `1/n` (or the log-sum-exp method for numerical stability); verify with an independent method (e.g., `statistics.geometric_mean` and a manual log method).
- **Logarithmic growth rate**: `ln(end / start)`, then convert to a percentage per the question's format instruction.
- **Population standard deviation**: divide squared deviations by `n` (not `n-1`); confirm the question says "population".
- **Average spread / average of differences**: compute the per-period difference first, then average, unless the question equivalently asks for the difference of averages.
- Use a calculator or Python for non-trivial arithmetic; do not rely on mental math.

## Step 6 — Cross-validation
- Where the table provides a published total for the selected rows, compare your computed sum to it; a small difference (rounding of individual cells) is acceptable, record both.
- Where an independent bulletin issue contains the same snapshot, repeat the extraction there and confirm the result matches.
- If the two sources disagree by more than rounding, prefer the issue whose "as of" date exactly matches the requested period and flag the discrepancy.

## Step 7 — Rounding
- Apply the rounding instruction exactly: "nearest hundredths" = 2 decimal places; "6 decimal places" = 6; "5 significant digits" = 5 sig figs (not decimal places).
- When the question defines a percent format (e.g., "0.1234 → 12.34"), multiply by 100 and round to the stated decimal places of the percent value.
- Round only the final reported value, not intermediate inputs, unless the question says otherwise.

## Step 8 — Output formatting
- If the question asks for comma-separated values in enclosed brackets, output `[value1,value2]` in the requested order, with no units inside the brackets unless explicitly required.
- If the question says "only report the value with no percent sign", omit the `%` symbol.
- If units are requested (e.g., "in millions of dollars"), include them only if the question asks for them in the answer text.
- Return the final answer via the structured output tool.

## Failure fallback
- If column verification fails (monthly sum ≠ annual total), re-read the header super-rows and rebuild the column map; do not extract values against an unverified map.
- If a required row label is not found by grep, try case-insensitive search and partial-label match; if still absent, confirm the table is the right one via g-officeqa-locate-source before concluding the data is missing.
- If cross-validation disagrees by more than rounding, re-check unit conversion first, then column mapping, then the chosen source issue, in that order.

## Completion condition
- Every extracted cell has recorded evidence (file, line, value); column mapping is verified; the computation uses a single consistent unit; the result is cross-validated; rounding matches the question spec; and the final answer is returned in the requested format.
