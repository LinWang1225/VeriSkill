---
name: g-officeqa-locate-bulletin
description: Determine which Treasury Bulletin edition contains data for a target reporting period, then verify the selection by searching the file. Use when a question references U.S. Treasury Bulletin data for a specific calendar month, fiscal year, or reporting date and the correct bulletin file must be identified before reading tables.
tags: [officeqa, treasury-bulletin, source-location, routing]
---

# Locate the correct Treasury Bulletin edition

## When to activate
A question references U.S. Treasury Bulletin data for a specific calendar
month, fiscal year, or "as of" date, and the correct bulletin file must be
selected before reading any table.

## The timing rule
Treasury Bulletins are published monthly or quarterly. A bulletin published in
month M typically contains statistical tables covering data through month M-1
(the prior reporting month). Quarterly editions (March, June, September,
December) compile the most data and are the primary editions for recent data.

Concretely:
- For data reported in calendar month X, look at bulletins for month X+1 or
  X+2.
- For a fiscal year ending September 30, use the December edition of that
  calendar year or the March edition of the next year.
- For "as of" a specific date (e.g., "last day of March 1989"), use the next
  available edition after that date.
- Retrospective tables: later bulletins often contain revised historical data
  spanning many prior years, so a single later edition may hold all needed
  years.

## File naming
Files follow the pattern `treasury_bulletin_YYYY_MM.txt` in
`data/treasury_bulletins/`. Use Glob with patterns like
`data/treasury_bulletins/treasury_bulletin_YYYY_*` to enumerate candidate
editions for a given year.

## Mandatory verification (do not skip)
After selecting a candidate bulletin, confirm it actually contains the target
period before extracting data:

1. Grep the candidate file for the target date or period string (e.g.,
   "January 1939", "Mar. 31, 1989", "Dec. 31, 1986", "September 2001").
2. If the date string is not found, also grep for the relevant table name or
   data series label to confirm the table exists in that edition.
3. If neither the date nor the table is found, move to the next later edition
   and repeat steps 1-2.
4. Only proceed to data extraction once the target period and table are
   confirmed present.

## Question-specified edition
If the question explicitly names a bulletin edition (e.g., "according to the
June 1970 bulletin", "using the September 2000 bulletin"), use that exact file
directly. Do not apply the timing rule to override a question-specified
edition. Still run the mandatory verification to confirm the target table
exists within that edition.

## Fallback
If no bulletin in the expected range contains the target date:
- Expand the search to later editions; data may be revised and republished in
  later issues with updated historical tables.
- Check whether the target period appears in a retrospective table within a
  much later bulletin.
- If multiple editions contain the data, prefer the edition whose publication
  date is closest to the question's specified reporting date, and note any
  revised values.

## Completion condition
A single bulletin file has been selected and verified (via grep) to contain
the target reporting period and the relevant table. The file path and the
approximate line range of the relevant table are recorded for the extraction
step.
