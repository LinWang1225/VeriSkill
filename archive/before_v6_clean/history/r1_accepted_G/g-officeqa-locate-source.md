---
name: g-officeqa-locate-source
description: "Determine the correct Treasury Bulletin edition that contains the requested month's or period's data, accounting for the publication lag"
tags: ["treasury-bulletin", "source-location", "date-mapping", "publication-lag"]
---

# Locate the Correct Treasury Bulletin Edition

## Problem
You need to find a Treasury Bulletin that contains data for a specific calendar month or period. Each bulletin edition reports data for prior months, not the month of publication.

## Steps

### 1. Identify the target period
Determine the exact calendar year, month, or date range the question asks about. Note whether the question refers to a specific month (e.g., "October 1961") or a range (e.g., "CY 1982").

### 2. Compute the expected bulletin edition
A Treasury Bulletin issued in month M typically contains data up to month M-1. Some tables have a longer compilation lag (up to M-2).  
**Rule of thumb**: For data in month X, look at bulletins for months X+1 or X+2.

- Example: For September 1953 data, the October 1953 bulletin is the first candidate.
- Example: For October 1961 data, the November 1961 bulletin is the first candidate, but December 1961 may be needed for the full table.

### 3. Search for the bulletin file
Use Glob to find files matching the expected year and month. If the first candidate does not contain the target month's data, try the next edition.

### 4. Locate the table within the file
Search for the table name (e.g., "PDO-1", "Summary of Receipts and Expenditures", "Table 2") using Grep. Read the table header to confirm the table's title and coverage period.

### 5. Verify the table covers the target period
Check that the row labels in the table include the target month. If the table ends before the target month, the data is not yet available in this edition. Try a later edition.

**Action -> Check -> Recovery**: After locating a candidate bulletin, check whether the table contains the target month's row. If the table's last row is earlier than the target, discard this edition and try the next month's bulletin. Repeat until you find a table that includes the target period.

### 6. Confirm the table title matches
Read the table title line (usually near the found row) to verify the table is about the correct concept (e.g., "Maturity Schedule" for maturity questions, "Receipts and Expenditures" for revenue questions). Do not rely on a partial match alone.

## Common Pitfalls
- Do NOT assume that a bulletin issued in month M contains data for month M. It almost never does.
- For December or year-end data, you may need the January or February edition of the following year.
- Some tables only appear in specific editions (e.g., annual summaries). If a table is missing, the question may require a different table or a different edition.