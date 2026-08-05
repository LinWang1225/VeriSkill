---
name: g-officeqa-locate-source
description: Locate the correct U.S. Treasury Bulletin issue file and table for an OfficeQA question by reasoning about publication lag, fiscal/calendar year-end conventions, and maturity-driven snapshots. Use when the question references a Treasury Bulletin table by date, month, fiscal year, calendar year, or security maturity and the source issue is not directly named.
tags:
  - officeqa
  - treasury-bulletin
  - source-location
  - publication-lag
  - table-identification
---

# Locate Treasury Bulletin source and table

## When to activate
- The question asks about data published in the U.S. Treasury Bulletin (bulletin files named `treasury_bulletin_YYYY_MM.txt`).
- The target issue is identified by a calendar month, calendar year, fiscal year, or security maturity date rather than by an explicit filename.
- You need to map a requested reporting period to the single bulletin issue that contains the complete, authoritative snapshot for that period.

## Step 1 — Parse the requested reporting period
Identify from the question:
- The kind of period: calendar month, calendar year, fiscal year (Oct 1–Sep 30), or security maturity date.
- The "as of" date (end of period) the data must reflect.
- Whether the question names a specific bulletin publication month; if so, use that directly and skip Step 2.

## Step 2 — Map reporting period to bulletin issue via publication lag
Treasury Bulletin monthly issues publish with a lag, and each issue carries data "as of" a recent past date. Use these conventions to pick the issue:

- **Monthly data for calendar month M**: appears in the issue published roughly M+1 or M+2. July month-end data is typically in the September issue. When unsure, grep across the few candidate issues and confirm the month label appears in the target table.
- **Fiscal year-end (September 30)**: use the September issue of that same calendar year (it carries the end-of-fiscal-year snapshot).
- **Calendar year-end (December 31), preliminary**: the final December-column figure is first reported as preliminary in the March issue of the following year. For a December 2002 value, use the March 2003 issue; for December 2012, use March 2013.
- **Full-year maturity schedule for calendar year Y**: use the January issue of year Y (its tables are "as of December 31, Y-1"), which contains the complete list of securities maturing in Y. Later issues in year Y only show remaining maturities and are incomplete for a full-year total.
- **Multi-year range**: locate one issue per year following the same rule; do not assume a single issue covers the whole range.

## Step 3 — Identify the table by code and title
- Match the table code referenced or implied by the question (e.g., PDO-1, PDO-2, PDO-3, AY-1, IFS-1, CM-I-1, OFS-1).
- Read the table title line to confirm it matches the question's subject (e.g., "Maturity Schedule of Interest-Bearing Marketable Public Debt Securities Other than Regular Weekly and 52-Week Treasury Bills" confirms exclusion of 52-week bills).
- Confirm the "as of" date in the table title matches the requested snapshot date.

## Step 4 — Confirm with a grep and record evidence
- Grep the chosen file for the table code and a distinctive row label from the question.
- Record the file name, line number of the table title, and the "as of" date as evidence before extracting values.

## Step 5 — Cross-bulletin confirmation (when available)
- The same snapshot often reappears in a later bulletin's historical column. When a later issue is readily available, grep it for the same row label and confirm the value matches.
- If the primary issue is missing or ambiguous, fall back to the later issue's historical column, but record that you did so.

## Failure fallback
- If grep finds no matching table in the chosen issue, re-derive the publication lag: try the adjacent issue (M+2 instead of M+1, or the December issue instead of September) and re-grep.
- If two issues contain conflicting values for the same period, prefer the issue whose table title "as of" date exactly equals the requested period, and note the discrepancy.

## Completion condition
- Exactly one bulletin file and one table are selected, with the table title and "as of" date recorded as evidence, and (when available) a cross-bulletin confirmation noted.
