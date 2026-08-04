---
name: g-officeqa-verify-extraction
description: Verify extracted Treasury Bulletin table values by confirming column mapping, cross-validating against a second source, and checking units before computation. Use after locating a table and before computing the final answer. Focuses exclusively on data correctness, not on computation method.
tags: [officeqa, treasury-bulletin, extraction, verification, column-mapping]
---

# Verify extracted table values

## When to activate
After locating a table in a Treasury Bulletin and reading one or more data
cells, before using those values in any computation. Especially needed when
table headers are ambiguous, use repeated column names with suffixes, or
appear misaligned with data cells.

## Step 1: Confirm column mapping
1. Read the full header row of the table. Count the pipe-delimited columns
   from left to right.
2. If the header uses suffixes like `.1`, `.2`, `.3` for repeated column names
   (common in yield tables and monthly data tables), these suffixes represent
   distinct time periods or year blocks. Do not assume the mapping. Cross
   reference with an adjacent bulletin edition that carries explicit year or
   period labels to confirm which suffix maps to which period.
3. Match the target data series to the correct column by name AND position.
   Verify the data cell you read falls under the intended header column by
   counting pipe-delimited fields from the start of the row.
4. If a footnote marker (e.g., "2/", "p", "r") is attached to the value, read
   the footnote text to understand whether it indicates a preliminary figure,
   a revised figure, or a definitional scope change. Prefer revised ("r")
   figures over preliminary ("p") figures when both exist for the same period.

## Step 2: Cross-validate the value
Confirm the extracted value against at least one independent source:
- The same table in a different bulletin edition (later editions often
  contain revised values; earlier editions may show the original).
- A related table in the same bulletin (e.g., verify a subtotal by summing its
  component columns; verify a total by checking a summary table).
- A total, per-capita, or ratio row that independently confirms the magnitude
  of the extracted value.

If the cross-check disagrees, determine which source is authoritative for the
question's specified reporting date and use that value. Record the
discrepancy.

## Step 3: Confirm units
1. Read the unit annotation immediately below the table title (e.g., "In
   millions of dollars", "In thousands of dollars", "In billions of Japanese
   yen", "Par values - in millions of dollars").
2. Compare with the unit requested by the question. Convert if needed:
   - thousands to millions: divide by 1,000
   - millions to billions: divide by 1,000
   - millions to nominal dollars: multiply by 1,000,000
3. Record the source unit and the target unit alongside the extracted value.
   A common error is extracting a value in thousands but treating it as
   millions, or vice versa.

## Step 4: Verify the data series matches the question
Before computing, confirm the extracted data series is the one the question
actually asks for:
- If the question specifies a reporting structure (e.g., "including both
  budgetary and trust-fund flows", "revised figures", "excluding certain
  wartime spending"), verify the table or column definition matches that
  scope by reading the relevant footnote.
- If the question specifies a sub-category within a broader table, confirm
  the column header names that sub-category, not a parent total.

## Fallback
- If column mapping cannot be resolved confidently, try a different bulletin
  edition with a clearer table layout or explicit labels.
- If cross-validation fails and no authoritative source can be identified,
  flag the value as uncertain and try the next most relevant table or
  edition.
- Do not proceed to computation with an unverified column mapping or unit.

## Completion condition
Each extracted value has: a confirmed column mapping (by name and position),
at least one cross-validation check, a verified unit, and a confirmed match
to the question's requested data series. Any unresolved ambiguities are
explicitly noted before computation proceeds.
