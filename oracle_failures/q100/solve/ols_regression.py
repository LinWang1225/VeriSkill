#!/usr/bin/env python3
"""
Extract 'Taxable Treasury bonds, due or callable 20 years and after' column
from Treasury Bulletin Table 1, and run OLS regression.
"""

# Data from treasury_bulletin_1956_08.txt lines 3176-3195
# Header: Period | 10-20 years | 20+ years | Moody's
# Three panels: left (1953-Apr to 1954-Jun), middle (1954-Jul to 1955-Sep),
#               right (1955-Oct to 1956-Jun)

# Extract the 20+ years column (third column, 1-indexed) for each month
# Months from 1953-Jul to 1956-Jun (t=1 to t=36)

y = [
    # 1953: Jul-Dec (t=1..6)
    3.25, 3.22, 3.19, 3.06, 3.04, 2.96,
    # 1954: Jan-Jun (t=7..12)
    2.90, 2.85, 2.73, 2.70, 2.72, 2.70,
    # 1954: Jul-Dec (t=13..18)
    2.62, 2.60, 2.64, 2.65, 2.68, 2.68,
    # 1955: Jan-Jun (t=19..24)
    2.77, 2.92, 2.92, 2.92, 2.91, 2.91,
    # 1955: Jul-Dec (t=25..30)
    2.96, 3.02, 3.00, 2.96, 2.96, 2.97,
    # 1956: Jan-Jun (t=31..36)
    2.94, 2.93, 2.98, 3.10, 3.03, 2.98
]

months = [
    "1953-Jul", "1953-Aug", "1953-Sep", "1953-Oct", "1953-Nov", "1953-Dec",
    "1954-Jan", "1954-Feb", "1954-Mar", "1954-Apr", "1954-May", "1954-Jun",
    "1954-Jul", "1954-Aug", "1954-Sep", "1954-Oct", "1954-Nov", "1954-Dec",
    "1955-Jan", "1955-Feb", "1955-Mar", "1955-Apr", "1955-May", "1955-Jun",
    "1955-Jul", "1955-Aug", "1955-Sep", "1955-Oct", "1955-Nov", "1955-Dec",
    "1956-Jan", "1956-Feb", "1956-Mar", "1956-Apr", "1956-May", "1956-Jun"
]

print("=== Data verification ===")
for i, (m, val) in enumerate(zip(months, y)):
    print(f"  t={i+1:2d}  {m}: {val}")

print(f"\n=== Summary statistics ===")
n = len(y)
t = list(range(1, n+1))
print(f"n = {n}")

sum_t = sum(t)
sum_y = sum(y)
sum_ty = sum(ti * yi for ti, yi in zip(t, y))
sum_t2 = sum(ti**2 for ti in t)
sum_y2 = sum(yi**2 for yi in y)

print(f"Σt = {sum_t}")
print(f"Σy = {sum_y}")
print(f"Σty = {sum_ty}")
print(f"Σt² = {sum_t2}")
print(f"Σy² = {sum_y2}")

# OLS regression
b = (n * sum_ty - sum_t * sum_y) / (n * sum_t2 - sum_t**2)
a = sum_y / n - b * sum_t / n

print(f"\n=== OLS regression ===")
print(f"b (slope) = ({n}×{sum_ty} - {sum_t}×{sum_y}) / ({n}×{sum_t2} - {sum_t}²)")
print(f"b = {n*sum_ty} - {sum_t*sum_y} / {n*sum_t2} - {sum_t**2}")
print(f"b = {n*sum_ty - sum_t*sum_y} / {n*sum_t2 - sum_t**2}")
print(f"b = {(n*sum_ty - sum_t*sum_y) / (n*sum_t2 - sum_t**2)}")
print(f"b = {b}")

print(f"\na (intercept) = {sum_y}/{n} - {b}×{sum_t}/{n}")
print(f"a = {sum_y/n} - {b}×{sum_t/n}")
print(f"a = {sum_y/n - b * sum_t/n}")
print(f"a = {a}")

print(f"\nEquation: y = {a} + {b}·t")

# Predict for t=37 (1956-Jul)
t_pred = 37
y_pred = a + b * t_pred
print(f"\n=== Prediction for t=37 (1956-Jul) ===")
print(f"y = {a} + {b}×{t_pred}")
print(f"y = {y_pred}")
print(f"Rounded to 3 decimal places: {round(y_pred, 3)}")

# Verify with scipy
try:
    from scipy import stats
    slope, intercept, r_value, p_value, std_err = stats.linregress(t, y)
    print(f"\n=== scipy.stats.linregress verification ===")
    print(f"slope = {slope}")
    print(f"intercept = {intercept}")
    print(f"y_pred (t=37) = {intercept + slope * 37}")
    print(f"Rounded = {round(intercept + slope * 37, 3)}")
    print(f"R² = {r_value**2}")
except ImportError:
    print("\nscipy not available, skipping verification")
