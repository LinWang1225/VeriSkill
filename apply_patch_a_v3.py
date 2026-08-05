#!/usr/bin/env python3
"""Apply VeriSkill Patch A v3 against main@63a3470.

The code changes are applied with git-apply. Two long Markdown prompt files are
updated with validated text anchors so CRLF checkout differences do not break
patch application.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_HEAD = "63a347017a8dcb73e240f6028eecafc17f75e938"
CODE_PATCH_NAME = "0001-integrity-code-v3.patch"


class ApplyError(RuntimeError):
    pass


def run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise ApplyError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{detail}")
    return proc


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def replace_once(text: str, old: str, new: str, label: str) -> tuple[str, bool]:
    old = normalize(old)
    new = normalize(new)
    if new in text:
        return text, False
    count = text.count(old)
    if count != 1:
        raise ApplyError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1), True


def build_prompt_updates(repo: Path) -> dict[Path, str]:
    updates: dict[Path, str] = {}

    g_path = repo / ".claude/agents/g-improve.md"
    g_original = g_path.read_text(encoding="utf-8-sig")
    g = normalize(g_original)
    g, _ = replace_once(
        g,
        """- `oracle_memory.jsonl`：此前 train 候选被 Oracle 证明为 regression 或 unresolved failure 的经验，可能为空。""",
        """- `oracle_memory.jsonl`：此前 train 候选的匿名化 improvement、regression 或 unresolved failure 经验，
  使用 `case_id` 而不是题目 ID，不含具体答案，可能为空。""",
        "g-improve oracle_memory description",
    )
    g, _ = replace_once(
        g,
        """- `regression` 优先级最高，必须避免候选再次破坏 baseline 已通过的能力；
- `unresolved_fail` 可支持新增检查或回退，但仍需归纳共同根因；
- 不得复制 Oracle 给出的具体答案，只提炼失败机制。""",
        """- `regression` 优先级最高，必须避免候选再次破坏 baseline 已通过的能力；
- `improvement` 表示已有机制被真实执行验证有效，后续候选应保留该机制，除非有新的 regression 证据；
- `unresolved_fail` 可支持新增检查或回退，但仍需归纳共同根因；
- 不得尝试从匿名 case 反推原题，不得在 manifest/skill 中写 `case_id`、题目 ID、gold/pred 或具体答案；
  只提炼成功或失败机制。""",
        "g-improve Oracle experience rules",
    )
    updates[g_path] = g

    loop_path = repo / ".claude/commands/veriskill-loop.md"
    loop_original = loop_path.read_text(encoding="utf-8-sig")
    loop = normalize(loop_original)

    replacements = [
        (
            "loop preflight files",
            """- `lib/pool.py`
- `lib/candidate_flow.py`
- `tools/start_v6_experiment.py`""",
            """- `lib/pool.py`
- `lib/candidate_flow.py`
- `lib/fingerprint.py`
- `lib/sanitize_feedback.py`
- `tools/start_v6_experiment.py`""",
        ),
        (
            "loop compile checks",
            """```bash
python3 -m py_compile lib/candidate_flow.py
bash -n oracle_run.sh""",
            """```bash
python3 -m py_compile \\
  lib/candidate_flow.py lib/fingerprint.py lib/sanitize_feedback.py \\
  adapters/make_checkers.py
bash -n oracle_run.sh""",
        ),
        (
            "loop initial manifest state",
            """  --candidate-dir \"$R/candidate/iter0\" \\
  --base-fingerprint \"<baseline_fingerprint>\" \\
  --out \"$R/manifests/iter0.validated.json\"""",
            """  --candidate-dir \"$R/candidate/iter0\" \\
  --base-fingerprint \"<baseline_fingerprint>\" \\
  --state \"$R/candidate_state.json\" \\
  --out \"$R/manifests/iter0.validated.json\"""",
        ),
        (
            "loop revision manifest state",
            """验证新 manifest，再让 D review。最多修订 `max_gd_revisions` 次。""",
            """验证新 manifest 时同样传 `--state \"$R/candidate_state.json\"`，确保 state 中的
candidate fingerprint 与实际 iterK、manifest 同步，再让 D review。最多修订 `max_gd_revisions` 次。""",
        ),
        (
            "loop baseline Oracle labels",
            """```bash
VERISKILL_ACTOR_SKILLS=\"$R/baseline_skills\" \\
  bash oracle_run.sh \"pool/traj/$id.md\"""",
            """```bash
VERISKILL_ORACLE_RUN_LABEL=\"r$r-i$k\" \\
VERISKILL_ORACLE_SIDE=\"baseline\" \\
VERISKILL_ACTOR_SKILLS=\"$R/baseline_skills\" \\
  bash oracle_run.sh \"pool/traj/$id.md\"""",
        ),
        (
            "loop candidate Oracle labels",
            """```bash
VERISKILL_ACTOR_SKILLS=\"$R/candidate/iter$k\" \\
  bash oracle_run.sh \"pool/traj/$id.md\"""",
            """```bash
VERISKILL_ORACLE_RUN_LABEL=\"r$r-i$k\" \\
VERISKILL_ORACLE_SIDE=\"candidate\" \\
VERISKILL_ACTOR_SKILLS=\"$R/candidate/iter$k\" \\
  bash oracle_run.sh \"pool/traj/$id.md\"""",
        ),
        (
            "loop canonical fingerprint rule",
            """- Oracle 前后重新计算 candidate 目录内容指纹，必须保持不变；同一批 candidate Oracle 结果中的 `skill_hash` 必须唯一。该 `skill_hash` 是原脚本运行指纹，不要求与 `candidate_flow.py` 的内容指纹字符串相等；""",
            """- Oracle 前后重新计算 candidate 目录内容指纹，必须保持不变；baseline/candidate 每条
  Oracle 结果的 `skill_hash` 必须分别等于 `candidate_flow.py fingerprint` 对对应目录的结果；""",
        ),
        (
            "loop raw feedback options",
            """  --out-to-d \"$R/feedback/oracle_to_d.jsonl\" \\
  --out-to-g \"$R/feedback/oracle_to_g.jsonl\" \\
  --metrics stats/candidate_eval.jsonl
```""",
            """  --out-to-d \"$R/feedback/oracle_to_d.jsonl\" \\
  --out-to-g \"$R/feedback/oracle_to_g.jsonl\" \\
  --out-to-d-raw \"$R/feedback/oracle_to_d.raw.jsonl\" \\
  --out-to-g-raw \"$R/feedback/oracle_to_g.raw.jsonl\" \\
  --metrics stats/candidate_eval.jsonl
```

`*.raw.jsonl` 仅留在本轮目录供人工调试；G/D 和跨轮 experience 只能读取不含题目 ID、答案、gold/pred 文本的非 raw 文件。""",
        ),
        (
            "loop D learn scored only",
            """只要有可靠配对，就派发 `d-improve mode=learn_from_oracle`，给出：""",
            """只有 `decision.json.decision_status=scored` 且有可靠配对时，才派发
`d-improve mode=learn_from_oracle`，给出：""",
        ),
        (
            "loop critic lint",
            """失败则整体回滚 critics。通过则：

- `d_version += 1`；""",
            """失败则整体回滚 critics。通过则先执行：

```bash
python3 lib/sanitize_feedback.py lint-tree \\
  --root workspace/critics \\
  --meta pool/meta.json
```

该检查失败也必须整体回滚 critics，不得仅删除命中的一行后继续。

- `d_version += 1`；""",
        ),
        (
            "loop G experience policy",
            """该文件只来自 train 条目，只保存 regression 与 unresolved failure。下一轮 G 可读取；本轮不在 Oracle 后再次无限修订，避免重复烧预算和选择性过拟合。""",
            """该文件只来自 train 条目，保存匿名化的 improvement、regression 与 unresolved failure，
用于保留已验证有效机制并避免重复回归。下一轮 G 可读取；本轮不在 Oracle 后再次无限修订，避免重复烧预算和选择性过拟合。""",
        ),
    ]
    for label, old, new in replacements:
        loop, _ = replace_once(loop, old, new, label)
    updates[loop_path] = loop
    return updates


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-tests", action="store_true", help="run Patch A unit tests after applying")
    parser.add_argument("--allow-head-mismatch", action="store_true")
    args = parser.parse_args(argv)

    bundle_dir = Path(__file__).resolve().parent
    patch_path = bundle_dir / CODE_PATCH_NAME
    if not patch_path.is_file():
        raise ApplyError(f"missing code patch beside installer: {patch_path}")

    repo_text = run(["git", "rev-parse", "--show-toplevel"], cwd=Path.cwd()).stdout.strip()
    repo = Path(repo_text)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    if head != EXPECTED_HEAD and not args.allow_head_mismatch:
        raise ApplyError(
            f"HEAD is {head}, expected {EXPECTED_HEAD}. Pull/reset to the reviewed main snapshot, "
            "or inspect changes and rerun with --allow-head-mismatch."
        )

    tracked_status = run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo
    ).stdout.strip()
    if tracked_status:
        raise ApplyError(f"tracked working tree is not clean:\n{tracked_status}")

    # Validate every Markdown anchor and the code patch before writing anything.
    updates = build_prompt_updates(repo)
    run(["git", "apply", "--check", str(patch_path)], cwd=repo)

    originals = {path: path.read_bytes() for path in updates}
    code_applied = False
    try:
        run(["git", "apply", str(patch_path)], cwd=repo)
        code_applied = True
        for path, text in updates.items():
            atomic_write(path, text)
        run(["git", "diff", "--check"], cwd=repo)

        run(
            [
                sys.executable,
                "-m",
                "py_compile",
                "lib/candidate_flow.py",
                "lib/fingerprint.py",
                "lib/sanitize_feedback.py",
                "adapters/make_checkers.py",
            ],
            cwd=repo,
        )
        run(["bash", "-n", "oracle_run.sh"], cwd=repo)
        if args.run_tests:
            run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "tests.test_patch_a",
                    "tests.test_candidate_flow_integrity",
                    "tests.test_candidate_flow",
                ],
                cwd=repo,
            )
    except Exception:
        for path, data in originals.items():
            path.write_bytes(data)
        if code_applied:
            run(["git", "apply", "-R", str(patch_path)], cwd=repo, check=False)
        raise

    print("Patch A v3 applied successfully.")
    print("Review with: git diff --stat && git diff --check")
    print("Then run: python3 -m unittest tests.test_patch_a tests.test_candidate_flow_integrity tests.test_candidate_flow")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApplyError as exc:
        print(f"apply_patch_a_v3: {exc}", file=sys.stderr)
        raise SystemExit(2)
