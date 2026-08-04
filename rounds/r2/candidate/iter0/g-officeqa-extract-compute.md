---
name: g-officeqa-extract-compute
description: Extract verified data from Treasury Bulletin tables and apply the specific computation required by the question. Each computation type has its own named procedure with an explicit formula and precision check. Never merge multiple computation types into a single generic compute step.
tags: [officeqa, treasury-bulletin, extraction, computation, verification]
---

# Extract, Verify, and Compute from Treasury Bulletin Data

## When to activate
- Source file and table already identified via g-officeqa-locate-source
- You need to extract numerical data and compute a final answer

## Phase 1: Extract and verify data

### Step 1: Confirm table structure
- Read the table header row to identify column names and positions
- Column positions change across eras and formats; always verify with the actual header row
- Note the unit stated in the table bracket (e.g., "[In millions of dollars]", "[In thousands of dollars]")

### Step 2: Extract values
- Read the specific data row(s) and extract the target column value(s)
- Record the exact line number and original text for each extracted value
- Handle special markers: "r" = revised, "p" = preliminary, "*" = less than $500K, "-" or "nan" = not available

### Step 3: Cross-validate
- Monthly-sum check: sum of monthly values should equal the fiscal-year-total row
- Cross-bulletin check: the same data point in a different bulletin should match
- Component-sum check: sub-components should sum to the total column
- If validation fails, re-examine column mapping and re-extract

## Phase 2: Apply the specific computation

CRITICAL: Identify the computation type from the question wording and apply ONLY the matching procedure below. Each procedure is independent with its own formula, precision check, and rounding. Never merge types into a generic step.

### simple_sum
Formula: S = sum(x_i), optionally excluding specified items.
Check: re-sum in Python; compare to manual calculation.

### arithmetic_mean
Formula: mean = sum(x_i) / N.
Check: verify sum and count separately in Python.

### geometric_mean
Formula: GM = exp((1/N) * sum(ln(x_i))); requires all x_i > 0.
Check: re-compute with scipy.stats.gmean or manual log-sum-exp.

### weighted_average
Formula: WA = sum(w_i * x_i) / sum(w_i).
Check: verify numerator and denominator separately.

### linear_regression_ols
Formula: slope = (N*sum(xy) - sum(x)*sum(y)) / (N*sum(x^2) - sum(x)^2); intercept = (sum(y) - slope*sum(x)) / N. Prediction: y_hat = slope * x_new + intercept.
Check: verify with numpy.polyfit(degree=1) or scipy.stats.linregress.

### pearson_correlation
Formula: r = sum((x-x_bar)(y-y_bar)) / sqrt(sum((x-x_bar)^2) * sum((y-y_bar)^2)); R^2 = r^2.
Check: verify with scipy.stats.pearsonr or numpy.corrcoef.

### cagr_geometric_rate
Formula: rate = (end_value / start_value)^(1/n) - 1, where n = number of periods.
Check: verify (1+rate)^n * start_value approximately equals end_value.

### centered_moving_average
Formula: CMA_i = (x_{i-k} + ... + x_i + ... + x_{i+k}) / (2k+1), centered at position i. For 3-period CMA: (x_{i-1} + x_i + x_{i+1}) / 3.
Check: verify each input value and the average independently in Python; confirm the centering position matches the question; do not confuse with trailing or leading moving averages.

### population_std_dev
Formula: sigma = sqrt(sum((x_i - mu)^2) / N). Divide by N, not N-1.
Check: verify with numpy.std(ddof=0) or statistics.pstdev.

### mean_absolute_deviation
Formula: MAD = sum(|x_i - mu|) / N, where mu = arithmetic mean.
Check: verify mean and deviations separately in Python.

### hazen_percentile
Formula: plotting position P_i = (i - 0.5) / N. If target P matches a P_i exactly, return that ranked value; otherwise linearly interpolate between adjacent ranked values.
Check: verify with numpy.percentile(method='hazen').

### box_cox_transform
Formula: T(y) = (y^lambda - 1) / lambda for lambda != 0; T(y) = ln(y) for lambda = 0.
Check: verify with scipy.stats.boxcox or manual exp/ln calculation.

### zipf_exponent
Formula: regress log(size) on log(rank): log(size) = C - alpha * log(rank). alpha is the Zipf exponent.
Check: verify R-squared and slope with scipy.stats.linregress on log-log data.

### arc_elasticity
Formula: E = (delta_Y / avg(Y)) / (delta_X / avg(X)), where avg = midpoint = (a + b) / 2.
Check: verify numerator and denominator separately.

### realized_variance
Formula: RV = sum(ln(r_t / r_{t-1})^2) over consecutive observations. For one-step: RV = (ln(r_2 / r_1))^2.
Check: verify each log ratio in Python.

### annualized_volatility
Formula: sigma_annual = sqrt(T) * |ln(r_t / r_{t-1})|, where T = periods per year (e.g., 52 for weekly, 252 for daily).
Check: verify annualization factor and log return separately.

### parametric_var
Formula: VaR_return = mu - z * sigma, where z = z-score for the tail probability (e.g., 2.326 for 1% upper tail). Loss = -VaR_return * portfolio_value.
Check: verify z-score, mean, and std dev separately.

### percent_contribution
Formula: share = (part / total) * 100; change_in_share = share_new - share_old (in percentage points).
Check: verify each share calculation independently.

### percent_difference
Formula: pd = |a - b| / base * 100.
Check: verify numerator and denominator.

### currency_conversion
Formula: convert amount to USD using the stated exchange rate; mind the direction (e.g., JPY/USD vs USD/JPY) and the unit scale (billions vs millions).
Check: verify conversion direction against the table's stated units.

### simple_difference
Formula: d = a - b. Mind the order specified by the question.
Check: verify sign and magnitude.

### list_extraction
No computation; extract values in the specified order and format as a comma-separated list.
Check: verify each value against source text.

## Phase 3: Rounding and output

### Rounding
- Apply the rounding precision specified in the question (hundredths, thousandths, tenths, whole number, etc.)
- Use Python round() for the final rounding only; keep full precision during all intermediate steps
- Never round intermediate values; only round the final answer

### Output format
- Match the format requested: single number, bracketed list, comma-separated list, signed number, etc.
- Include units only if the question asks for them
- For multi-value answers, follow the exact ordering and separator specified

## Fallback
- If column position is ambiguous, read the full header row and map by column name
- If extracted values fail cross-validation, re-examine the table structure and try adjacent columns
- If the required data is not in the expected bulletin, return to g-officeqa-locate-source
- If a computation type not listed above is needed, derive the formula from first principles and verify with an independent Python calculation
- If the question asks for data that was discontinued or never published, report that the data is unavailable with evidence from the source text

## Completion criteria
- All extracted values have recorded source line numbers
- Cross-validation passed (or failure documented with reason)
- Computation applied using the specific matching procedure (not a generic step)
- Independent Python verification of the final result
- Rounding matches the question's specified precision
- Output format matches the question's specification
