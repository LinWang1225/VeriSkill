---
name: g-officeqa-extract-verify
description: "Extract numerical data from Treasury Bulletin tables, verify column meanings and row labels, and cross-validate for consistency across multiple sources"
tags: ["data-extraction", "table-reading", "cross-validation", "column-verification", "source-integrity"]
---

# Extract and Verify Table Data

## Problem
You have located a Treasury Bulletin table that contains the needed data. You must extract the correct value(s) and verify they are accurate.

## Steps

### 1. Read and confirm the table header
Before extracting any data, read the table header row(s) to understand the column layout. Identify which column contains the quantity you need (e.g., "Total", "Accrued discount", "Receipts > Total", "Amount of maturities"). If the table has multiple sections, confirm the section label matches the question's scope.

### 2. Locate the correct row
Find the row whose label matches the target period (month, year, or date). Confirm the row is positioned correctly among adjacent rows (e.g., "Sept." comes before "Oct."). If the table has a "Total" or subtotal row, make sure you are reading a data row, not a sum.

### 3. Quote the exact source row
Copy the full row text verbatim and note the line number. This provides a traceable reference in case the data needs to be rechecked. Be precise about which column you extracted the value from.

### 4. Verify the value makes sense
- Check that the value is in the expected unit (millions, thousands, percent).
- If the question has date constraints (e.g., "Thursday", "week ending", "calendar year"), verify that the extracted row satisfies those constraints.
- If the table has footnotes, read them to confirm the column definition (e.g., "Bank discount basis", "nominal dollars").

**Action -> Check -> Recovery**: After extracting a value, check whether it is consistent with the surrounding context (adjacent rows, column totals, expected magnitude). If the value seems off (e.g., an order of magnitude larger or smaller than expected), return to Step 1 to re-read the table header and confirm the column mapping.

### 5. Cross-validate (when possible)
- If a second bulletin edition also contains the same statistic, check both for consistency.
- Verify that the combination of values you use in a calculation makes sense together (e.g., all from the same table, same units, same time period).
- If the trajectory narrative claims a specific source (e.g., "January 1982 Bulletin"), confirm that the tool execution actually read from that file, not a different one.

### 6. Document the extraction
In your final narrative, include:
- The bulletin file name and line number where the data was found.
- The table name and column header you used.
- The exact value extracted.
- Any verification or cross-validation steps performed.

### 7. Verify the final answer format against the question's specification
Before submitting the final answer, re-read the question's output format requirements:
- Does it ask for a "comma separated list", "single number", "array", or something else?
- Does it specify units, commas, precision (decimal places), or symbols (%, $)?
- Does it prohibit extra text, unit labels, or annotations in the output?

**Action -> Check -> Recovery**: After constructing the answer, check whether every element of the output matches the question's format specification (e.g., if the question says "comma separated list of numbers," do not include "$", "million", "dollars", or any text per item — just the numbers). If the format does not match, reformat the output to match exactly before submitting. Do not include "not available", "N/A", or similar text unless the question explicitly asks for it.