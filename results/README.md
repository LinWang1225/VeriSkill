# Result artifacts

`pool/traj.full/` contains qualitative execution trajectories. Those files are
useful for inspecting skill usage, reasoning and evidence quality, but they do
not by themselves provide Oracle accuracy or D precision/recall.

Run the held-out same-sample final evaluation after training:

```bash
bash eval_final_same_sample.sh --meta pool/meta.json \
  --out-dir rounds/final_test --max 50 --seed 0 \
  --round "$(python3 -c 'import json; print(json.load(open("ledger.json"))["round"])')" \
  --g-version "$(python3 -c 'import json; print(json.load(open("ledger.json"))["g_version"])')" \
  --series stats/test_eval.jsonl
```

Then generate a reproducible summary:

```bash
python3 lib/result_report.py --root . \
  --out-json results/summary.json \
  --out-md results/summary.md --strict
```

The exporter:

- validates that `.jsonl` files really contain one JSON object per line;
- computes D metrics only from `same_sample=true` audit rows;
- excludes legacy rows that compare an old-trajectory D verdict with a new
  current-skill Oracle rerun;
- treats stratified training audits as diagnostics, not unbiased performance;
- reports held-out G success plus same-sample D FPR, FNR and balanced accuracy;
- statically checks full trajectories for visible arithmetic contradictions,
  opaque aggregate evidence, unsupported assumptions and missing skill hashes.

Trajectory warnings are not ground truth. Checker/truth-backed Oracle results
remain the only source for task correctness.
