---
name: g-officeqa-extract-verify
description: Within a located Treasury Bulletin file, find the target table, parse its multi-level column headers, extract and cross-verify numeric values, then compute the requested statistic and round/format the answer. Activate after the source bulletin file(s) are identified (g-officeqa-locate-source) and whenever a Treasury Bulletin table must be read for a numeric answer. Covers table location, column-mapping verification, value extraction with unit/marker handling, cross-bulletin verification, computation, rounding, and output formatting.
tags:
  - officeqa
  - treasury-bulletin
  - table-extraction
  - column-mapping
  - cross-verification
  - computation
  - rounding
  - output-format
---

# Extract, verify, compute, and format from a Treasury Bulletin table

## When to use

The source bulletin file(s) are identified and you must pull specific numeric values from a table, possibly compute a statistic, and produce a rounded, formatted answer.

## Steps

### 1. Locate the table inside the bulletin

- Tables are identified by a number/title string (e.g., "Table AY-1", "TABLE FFO-2", "Table PDO-1", "TABLE IFS-1", "Table SBN-2", "Table CM-I-1", "Table OFS-1", "Table 5.- Federal Old-Age...").
- Grep the file for the table identifier and the section heading. Use `-n` to get line numbers.
- Read the header rows with `Read(offset, limit)` starting just before the match line. Capture the full multi-level header row and the unit line (e.g., "(In millions of dollars)", "(in thousands of dollars)").

### 2. Parse the column layout

- Headers are pandas-style multi-level: `Parent > Child` separated by ` > `, with suffix annotations like `.1`, `.2`, `.3` for repeated column groups.
- Map each column index to its meaning from the header. **Do not assume a fixed column position** — column order shifts across eras (e.g., "Total expenditures" is col8 in 1942-1947, col11 in Jan-May 1948, col8 again in Table 2 from June 1948).
- Some tables pack several years into one row-block with repeated column groups (e.g., Average Yields table AY-1 packs 4 years per block with `.1/.2/.3` suffixes). Decode the year-to-column-group mapping by cross-referencing a bulletin that carries explicit year labels, or by matching a known value.

### 3. Verify the column mapping before extracting

Confirm the mapping with at least one of:
- **Sum check**: monthly values sum to the annual/total column.
- **Cross-bulletin label check**: a different bulletin (often the adjacent month) shows explicit year/period labels that disambiguate the same table layout.
- **Subtotal check**: subitem columns sum to the published subtotal column.
- **Footnote check**: read the footnote definitions (e.g., "Public works 2/") to confirm a column's definition matches the question's wording (inclusive/exclusive scope).

If the mapping cannot be confirmed, do not guess — fall back.

### 4. Extract the values

- Locate the data row by matching the period label (month abbreviation, fiscal year integer, calendar year).
- Read the numeric token at the confirmed column index. Strip markers: `r` (revised), `p` (preliminary), `*` (less than $500K), `-` (no transactions), `nan`/blank (not available). Keep a note of revised vs preliminary if the question restricts to a specific vintage.
- Respect the table's stated unit. Convert if the question asks for a different unit (e.g., table in thousands of dollars, question in millions: divide by 1000).
- If the question restricts to "reported values for all individual calendar months", extract each month separately and sum them; do not substitute a pre-published annual total even if it differs only by rounding.

### 5. Cross-verify the extracted values

- Re-extract the same value from a different bulletin that reproduces the back-figure (later bulletins carry earlier months). The two must match.
- For multi-bulletin assembly, confirm each month's value is stable across the bulletins that overlap.
- If a discrepancy appears, prefer the bulletin that is internally consistent (subitems sum to subtotal) and matches the question's required definition/vintage.

### 6. Compute the requested statistic

Use Python/Bash for arithmetic to avoid manual errors. Common operations seen in this domain:
- Sum, absolute difference, absolute change.
- Geometric mean: use the log method `exp(mean(log(values)))` or `statistics.geometric_mean` to avoid overflow.
- Compound annual growth rate: `(Vt/V0)^(1/t) - 1`.
- Continuously compounded growth: `ln(Vt/V0) / t`.
- Percent contribution / share: `part/total * 100`; change in share = difference of two shares in percentage points.
- Arc elasticity: `(dY/avg(Y)) / (dX/avg(X))`.
- OLS linear regression: compute slope/intercept, then forecast.
- R-squared: square the Pearson correlation.
- Centered moving average, population standard deviation.
- Inflation correction via external CPI (e.g., BLS CPI-U from Minneapolis Fed): multiply by `CPI_base/CPI_target`.

### 7. Round and format the answer

- Apply the question's rounding instruction exactly: hundredths (2 dp), thousandths (3 dp), tenths (1 dp), whole number, or N significant digits.
- Distinguish "percent value" (decimal 0.1234 reported as 12.34) from "decimal value" (reported as 0.1234). If the question says "report as a percent value", multiply by 100.
- Match the output container: single number, bracketed comma-separated list `[v1, v2]`, signed number (preserve negative sign), with or without units, with or without a percent sign.
- If the question encodes the answer as a derived integer (e.g., month*100 + year), apply that encoding.

## Checks

- Column mapping confirmed by an independent check (sum, cross-bulletin, subtotal, or footnote).
- Each extracted value traced to a file + table + row + column.
- Computation reproduced via Python (not purely mental arithmetic).
- Rounding matches the question's stated precision and unit convention.
- Output format matches the question's container exactly.

## Fallback

- If the target table is not found in the identified bulletin: search adjacent bulletins for the same table number; the table may have moved or the bulletin may be the wrong month.
- If column mapping is ambiguous and no disambiguating label exists: extract both candidate interpretations and use the sum/subtotal check to pick the consistent one.
- If a value is missing (nan/-) in the primary source: check a later bulletin that may have revised the figure, or an earlier one with a different vintage.
- If the computed result fails a sanity check (wrong sign, implausible magnitude): re-verify the column mapping and units before submitting.

## Notes

- Never read an entire bulletin file in one call (most exceed 256KB). Always Grep then Read with offset/limit.
- When a question spans many months/years, build a small script that iterates over the per-month bulletins rather than reading each by hand.
- Preserve the distinction between "calendar year" and "fiscal year" rows; they are different rows in the same table.
- "Revised" figures (footnoted) may differ from originally published figures; follow the question's wording about which vintage to use.
