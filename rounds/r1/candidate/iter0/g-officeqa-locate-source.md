---
name: g-officeqa-locate-source
description: For U.S. Treasury Bulletin questions, determine which bulletin file(s) contain the data for the requested calendar/fiscal period. Activate when a question asks about Treasury Bulletin data (receipts, expenditures, yields, debt, ownership, savings bonds, customs, reserve assets, TIPS, exchange rates, silver, seigniorage, etc.) and the source bulletin is not already identified. Maps target dates to treasury_bulletin_YYYY_MM.txt files accounting for publication lag.
tags:
  - officeqa
  - treasury-bulletin
  - source-location
  - date-mapping
---

# Locate Treasury Bulletin source file(s)

## When to use

A question references data published in the U.S. Treasury Bulletin (monthly statistical publication). You must identify the exact file(s) under `data/treasury_bulletins/` that contain the values for the requested period before extracting anything.

## Inputs

- The target calendar month(s)/year(s) or fiscal year(s) the question asks about.
- Any explicit bulletin citation in the question (e.g., "Use the bulletin published in June 1970").
- The data directory: `data/treasury_bulletins/` (resolve the absolute workspace path at runtime; files are named `treasury_bulletin_YYYY_MM.txt`).

## Steps

### 1. Identify the target period and whether a specific bulletin is named

- If the question names a bulletin month/year (e.g., "March 1941 bulletin", "June 1970"), use that exact file: `treasury_bulletin_YYYY_MM.txt`. Do not substitute.
- Otherwise, derive the target data period from the question (calendar month/year, calendar year end, fiscal year end, a range of months).

### 2. Map the target data period to a bulletin publication month

The Treasury Bulletin is a monthly publication with a reporting lag: a bulletin published in month M contains data through roughly M-1 (1939-1944 era) or M-2 (1945 onward era). Rules:

- **A specific calendar month T**: look at the bulletin published in T+1 first; if the row for month T is absent, try T+2. Verify by finding a row labeled with month T's abbreviation inside the candidate file.
- **Calendar year end (Dec 31 of year Y)**: use the January (Y+1) bulletin, or the March (Y+1) bulletin which often reproduces the December back-figure. For international/position tables (CM-I-1, IFS-1) the March bulletin of Y+1 typically holds the December-Y preliminary column.
- **Fiscal year end (Sept 30 of year Y)**: use the September or October bulletin of calendar year Y (FY ends Sept 30); later bulletins reproduce the back-figure.
- **A range of months**: assemble per-month values from the corresponding per-month bulletins (each month from its own T+1/T+2 bulletin). Prefer the earliest bulletin that first reported each month, but if cross-consistency matters, pull all months from one late bulletin that reproduces the full range as back-figures (e.g., a December bulletin often contains Jan-Nov of that year).
- **Fiscal year annual row**: a single September bulletin usually lists the fiscal year row directly.

### 3. List available files

Use Glob with pattern `treasury_bulletin_YYYY_*` (or a broader pattern) to confirm which months exist for the target year. Not every month is present; do not assume all 12 exist.

### 4. Confirm the candidate file contains the target period

Grep the candidate file for the target month label (e.g., `"Oct."`, `"July"`, `"1946"`) in the relevant section. If the row is present, the file is confirmed. If absent, fall back.

### 5. Record the source

For each value needed, record: file name, table identifier, and the row label. This record feeds the extraction skill.

## Checks

- The candidate file exists (Glob returned it).
- The target period row/column label is present in the candidate file (Grep confirmed).
- When two different periods are needed, each is mapped to its own file(s); do not assume one file covers both.

## Fallback

- If the expected bulletin file is missing: try the adjacent month (T+2 or T+3) which usually reproduces the earlier month as a back-figure.
- If the target month row is absent in the first candidate: try the next month's bulletin.
- If no single bulletin covers the full requested range: assemble from multiple bulletins, one per month, and note each value's source.
- If the question involves a series over many months/years and per-month lookup is impractical: find one late bulletin that reproduces the entire range as back-figures (common for yield tables and ownership surveys).

## Notes

- Publication lag changed over time; always verify by inspecting the file rather than assuming a fixed offset.
- Some questions deliberately restrict the source (e.g., "using only the reported values for all individual calendar months"). Respect that restriction when choosing sources — do not substitute a pre-aggregated annual total for a required month-by-month sum.
- Never read the whole bulletin file in one call; they routinely exceed 256KB. Use Grep to locate, then Read with offset/limit.
