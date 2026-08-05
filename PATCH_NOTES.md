# VeriSkill Patch A v3

## Why v2 failed

`git apply --check` showed that all code hunks matched, but two long Markdown prompt files did not:

- `.claude/agents/g-improve.md`
- `.claude/commands/veriskill-loop.md`

These files are now updated by a validated Python installer instead of unified-diff hunks. The installer normalizes CRLF/LF differences and requires every source anchor to appear exactly once before it writes anything.

## Files

- `0001-integrity-code-v3.patch`: all code/test changes plus `d-improve.md`.
- `apply_patch_a_v3.py`: applies the code patch and updates the two problematic Markdown files atomically.

## Apply

Extract the ZIP into the repository root, then run:

```bash
git status --short
git rev-parse HEAD
python3 apply_patch_a_v3.py
```

Expected reviewed HEAD:

```text
63a347017a8dcb73e240f6028eecafc17f75e938
```

The installer permits untracked patch files, but refuses to run when tracked files are modified.
It validates all Markdown anchors and runs `git apply --check` before changing the working tree.
On failure after application begins, it restores both Markdown files and reverses the code patch.

To run the new tests as part of installation:

```bash
python3 apply_patch_a_v3.py --run-tests
```

## Post-apply verification

```bash
git diff --stat
git diff --check
python3 -m py_compile \
  lib/candidate_flow.py \
  lib/fingerprint.py \
  lib/sanitize_feedback.py \
  adapters/make_checkers.py
bash -n oracle_run.sh
python3 -m unittest \
  tests.test_patch_a \
  tests.test_candidate_flow_integrity \
  tests.test_candidate_flow
```

## In-progress round warning

Any Oracle JSONL created before this patch uses the old fingerprint implementation. Archive or remove the unfinished round's generated manifest/review/Oracle/decision products and regenerate them after applying v3. Do not mix old Oracle rows with the new canonical fingerprint.
