---
name: g-officeqa-locate-source
description: Locate the correct Treasury Bulletin file and table for a given data query. Handles publication lag, file naming convention, fiscal-year mapping, and table catalog routing.
tags: [officeqa, treasury-bulletin, source-location, routing]
---

# Locate Treasury Bulletin Source

## When to activate
- The question asks for data published in U.S. Treasury Bulletins
- You need to identify which bulletin file(s) and table(s) contain the required data

## File naming convention
Files are named `treasury_bulletin_YYYY_MM.txt` under `data/treasury_bulletins/`.
- YYYY = publication year, MM = publication month (01-12)
- Use Glob with patterns like `data/treasury_bulletins/*YYYY*` to find candidates

## Publication lag
The bulletin published in month M contains data for approximately month M-1 or M-2:
- 1940s era: lag ~1 month (M month bulletin contains M-1 month data)
- Post-1945: lag ~2 months (M month bulletin contains M-2 month data)
- To find data for calendar month X, search bulletins X+1 and X+2
- When the question specifies a bulletin by date (e.g., "June 1980 bulletin"), use that exact file

## Fiscal year mapping
- U.S. federal fiscal year FY YYYY runs October 1 (YYYY-1) through September 30 (YYYY)
- December bulletin of calendar year YYYY contains complete FY YYYY data
- March bulletin of YYYY+1 contains data through February, covering the prior FY
- Some tables (e.g., FFO-3) cover 5 fiscal years; use the latest bulletin covering the full range
- For revised data (marked "r"), prefer the latest available bulletin

## Table catalog
| Table | Content |
|-------|---------|
| FFO-1 | Summary of Fiscal Operations (total receipts/outlays) |
| FFO-2 | On-Budget and Off-Budget Receipts by Source |
| FFO-3 | On-Budget and Off-Budget Outlays by Agency |
| FFO-4 | Summary by Source and Agency |
| FFO-5 | Internal Revenue Receipts by State / Outlays by Function |
| FFO-6 | Investment Transactions of Government Accounts |
| FD-1 | Summary of Federal Debt (total, public, agency securities) |
| USCC-1/2 | U.S. Currency and Coin Outstanding and in Circulation |
| PDO-1 | Maturity Schedule of Interest-Bearing Marketable Public Debt Securities |
| PDO-2/3 | Public Offerings (auction amounts, TIPS adjusted prices) |
| SBN-1/2/3 | Savings Bonds Sales and Redemptions by series and period |
| TSO-1 | Summary of Federal Securities (total outstanding) |
| OFS-1/2 | Distribution / Estimated Ownership of Federal Securities |
| CM-I-2 | International Claims and Liabilities by Type |
| AY-1 | Average Yields of Long-Term Treasury, Corporate, Municipal Bonds |
| MY-2 | Monthly Yield Averages (Treasury, corporate, municipal) |
| FCP-II-1 | Japanese Yen Positions and exchange rates |
| FCP-IV-1 | British Pound Positions and exchange rates |

## Steps
1. Parse the question's time reference (calendar month/year, fiscal year, "as of" date, or named bulletin)
2. If a specific bulletin is named, use it directly; otherwise apply publication lag to determine the issue
3. Identify the relevant table from the catalog above based on the data category
4. Use Grep to confirm the table exists in the target file and find its line range
5. For multi-period data, identify all required bulletin files

## Fallback
- If the expected table is not in the target file, search adjacent months (±1 or ±2)
- If the table name varies across eras, Grep with partial patterns (e.g., "FFO-3" or "Outlays by Agency")
- If data spans multiple bulletins, locate each file and combine
- If the question references a bureau or organizational unit, search for its name in the bulletin text to confirm authorship

## Completion criteria
- Specific file path(s) identified with confidence
- Table name and approximate line range confirmed via Grep
- Publication lag reasoning documented
