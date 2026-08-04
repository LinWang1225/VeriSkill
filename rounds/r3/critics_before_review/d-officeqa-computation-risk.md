# D critic: computation precision and regression risk for officeqa

Used by D in review_candidate mode to detect when a candidate skill
introduces computation-precision risk that cannot be resolved by static
review alone.

## Rules

- R-officeqa-computation-001 [abstain] Numeric computation precision (formula selection, rounding boundary, floating-point intermediate, unit conversion) is not verifiable from skill text. When a candidate skill's compute step covers items requiring exact numeric answers with tol=0, and the skill does not pin a specific formula + rounding rule per computation type, D should return ABSTAIN and let Oracle judge, rather than PASS. 依据:r1 false_accept: q048 candidate produced 0.377 vs gold 0.388; q030 candidate produced 0.0 vs baseline 0.1 — both are precision outcomes only Oracle can detect.

- R-officeqa-computation-002 [hard] If a candidate skill changes the computation step for a computation type that appears in a baseline-passing item, and the change is not a targeted fix with a stated before/after formula, treat the retained-pass item as regression-risk (partial). Do not mark it covered. 依据:r1 false_accept: q048 centered moving average regressed because the candidate's generic compute step altered the working baseline path without a targeted justification.

- R-officeqa-computation-003 [soft] A candidate that simultaneously fixes one item (improvement) and breaks another (regression) via the same broad skill change indicates the change is not a clean generalization. D should note this mixed-signal risk in soft_concerns and lower confidence below the PASS threshold. 依据:r1 false_accept: q030 improved and q048 regressed from the same g-officeqa-extract-verify change; net_gain=0, candidate rejected.

- R-officeqa-computation-004 [abstain] When the candidate contains a "Checks" section asserting "Computation reproduced via Python (not purely mental arithmetic)" but the skill text does not enforce a concrete verification step (e.g., re-derive with an independent method, or sanity-check magnitude), the check is aspirational. D should not count it as a completion condition for numeric items. 依据:r1 false_accept: the skill's Checks section listed Python reproduction but q048 still produced a wrong value, showing the check was not enforceable from text.

- R-officeqa-computation-005 [soft] A candidate that addresses a prior D criticism by adding structural separation (distinct named procedures for each formula) but does not add enforceable routing or execution triggers may produce no behavioral change at all. D should not raise confidence or issue PASS solely because the candidate's structure matches prior feedback; the relevant question is whether the structure changes what the actor does, not whether it looks correct on paper. When the only change from baseline is adding reference material without mandatory invocation, lower confidence below the PASS threshold. 依据:r2 false_accept: candidate fixed r1's merging anti-pattern with 20+ separate procedures, but Oracle showed identical results to baseline (0 improvement, 0 regression, 2 retained_pass, 4 unresolved_fail) — the structural fix did not translate to behavioral improvement.
