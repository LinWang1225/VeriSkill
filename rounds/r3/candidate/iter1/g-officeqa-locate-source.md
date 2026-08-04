---
name: g-officeqa-locate-source
description: >
  Mandatory source-location protocol for U.S. Treasury Bulletin questions.
  Activate whenever a question asks about data reported in, or published by,
  the U.S. Treasury Bulletin (treasury_bulletin_YYYY_MM.txt files). This skill
  governs WHICH bulletin issue(s) to read. It must be executed BEFORE any data
  extraction or calculation. Do not skip steps.
tags:
  - officeqa
  - treasury-bulletin
  - source-location
  - routing
---

# Locate Treasury Bulletin Source

## When to use

Use this skill FIRST, before any table reading or calculation, whenever the
question references U.S. Treasury Bulletin data, federal receipts/expenditures,
public debt, bond yields, treasury bills, savings bonds, trust fund balances,
foreign holdings, or any fiscal data sourced from Treasury Bulletins.

## Mandatory procedure

Execute every step in order. Do not proceed to data extraction until the
source file(s) are confirmed.

### Step 1 — Identify the temporal scope

From the question, determine:
- Which calendar months, fiscal years, or calendar years are needed.
- Whether the question says "reported in <bulletin issue>" (explicit source)
  or asks for data "for <period>" (implicit — you must find the source).
- Whether data spans a single period or multiple periods (e.g., 1990-1998).

If the question names a specific bulletin issue (e.g., "the September 2000
bulletin"), use that issue directly and skip to Step 4.

### Step 2 — Apply the bulletin-data-lag rule

THIS IS THE CRITICAL RULE. Getting this wrong is the most common source of
errors.

- A Treasury Bulletin published in month M reports data through month M-1
  (the prior month) or earlier.
- To obtain data for calendar month X, read the bulletin published in month
  X+1 or later. The bulletin from month X contains data through month X-1
  and will NOT have month X data.
- For fiscal year data (fiscal year ends September 30), the FY-end value
  appears in bulletins from October onward.
- In the modern era (post-1996 approximately), bulletins are quarterly:
  March, June, September, December. A March bulletin covers data through
  February. A June bulletin covers through May. September through August.
  December through November.
- In earlier eras (pre-1996), bulletins were monthly.

CHECKPOINT: Write down the mapping "target period -> earliest bulletin that
contains it" for every period the question requires. If any mapping is
uncertain, list the next 1-2 later bulletins as fallback candidates.

### Step 3 — Enumerate candidate files

For each needed bulletin, form the file name pattern:
`treasury_bulletin_YYYY_MM.txt`

List all candidate files. Confirm each file exists by listing the directory
or globbing. If the preferred bulletin does not exist (e.g., no bulletin was
published that month), fall back to the next available later issue.

When data spans multiple years or months, you may need multiple bulletin
files. Enumerate ALL of them before starting extraction.

### Step 4 — Verify the bulletin covers the target period

Before extracting data, open the candidate file (using Grep for the table
name or period label, or Read with offset/limit for large files) and confirm
the target period appears in the data. If it does not, fall back to a later
bulletin issue and re-verify.

### Step 5 — Record the source

For each extracted value, record:
- The bulletin file name.
- The table name or number.
- The line number of the data row.

This provenance record is required for cross-validation in the extraction
skill.

## Failure and fallback

- If the preferred bulletin file does not exist, try the next later issue.
- If the target period is not found in the opened bulletin, try a later issue.
- If multiple bulletins are needed and one is missing, check whether a later
  bulletin contains historical data covering that period (many tables show
  multiple months or years of history).
- If the question references a table that moved or was renamed across eras
  (e.g., FFO-3 vs FFD-3, Table 2 vs Table 4), search by content keywords
  rather than table number alone.

## Common pitfalls

- Reading the bulletin FROM the same month as the target data month and
  finding nothing — the data lag rule means you need the NEXT month.
- Assuming quarterly publication for pre-1996 data — earlier bulletins were
  monthly.
- Forgetting that fiscal year 1961 means Oct 1960 through Sep 1961, so
  FY-end data appears in October 1961 or later bulletins.
- Using a single bulletin when the question spans periods covered by
  different bulletins (e.g., 1990-1998 where 1990-1993 and 1994-1998 are
  in different tables with different column layouts).
