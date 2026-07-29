#!/usr/bin/env python3
"""Validate and summarize VeriSkill runtime/result artifacts.

The report intentionally separates qualitative trajectory artifacts from
same-sample Oracle/D metrics. Legacy audits that compare an old-trajectory D
verdict with a current-G rerun are counted but excluded from confusion metrics.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import importlib.util
import json
from pathlib import Path
import re
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("trajectory_checks", HERE / "trajectory_checks.py")
_tc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_tc)

ROUND_RE = re.compile(r"r(\d+)$")
KINDS = ("TP", "FP", "FN", "TN")


@dataclass
class JsonlRead:
    rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    array_instead_of_jsonl: bool = False


def read_jsonl(path: Path) -> JsonlRead:
    result = JsonlRead()
    if not path.exists():
        return result
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = text.strip()
    if not stripped:
        return result
    if stripped.startswith("["):
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            result.errors.append(f"{path}: 非法 JSON：{exc}")
            return result
        result.array_instead_of_jsonl = True
        result.errors.append(f"{path}: 文件名为 .jsonl，但内容是单个 JSON 数组")
        if isinstance(value, list):
            result.rows.extend(v for v in value if isinstance(v, dict))
        return result
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            result.errors.append(f"{path}:{lineno}: 非法 JSON：{exc}")
            continue
        if not isinstance(value, dict):
            result.errors.append(f"{path}:{lineno}: JSONL 行必须是对象")
            continue
        result.rows.append(value)
    return result


def safe_div(a: int | float, b: int | float) -> float | None:
    return None if not b else a / b


def round_num(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def confusion_metrics(counts: Counter[str]) -> dict[str, Any]:
    tp, fp, fn, tn = (counts[k] for k in KINDS)
    tpr = safe_div(tp, tp + fn)
    tnr = safe_div(tn, tn + fp)
    fpr = safe_div(fp, fp + tn)
    fnr = safe_div(fn, fn + tp)
    bal = None if tpr is None or tnr is None else (tpr + tnr) / 2
    return {
        "counts": {k: counts[k] for k in KINDS},
        "fpr": round_num(fpr),
        "fnr": round_num(fnr),
        "balanced_accuracy": round_num(bal),
        "support": sum(counts[k] for k in KINDS),
    }


def _round_dirs(root: Path) -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for path in (root / "rounds").glob("r*") if (root / "rounds").exists() else []:
        match = ROUND_RE.fullmatch(path.name)
        if match and path.is_dir():
            out.append((int(match.group(1)), path))
    return sorted(out)


def summarize_round(number: int, path: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    verdict_file = read_jsonl(path / "verdicts.jsonl")
    audit_file = read_jsonl(path / "audit.jsonl")
    errors.extend(verdict_file.errors)
    errors.extend(audit_file.errors)

    verdict_counts = Counter(str(row.get("verdict", "unknown")) for row in verdict_file.rows)
    same_rows = [row for row in audit_file.rows if row.get("same_sample") is True]
    legacy_rows = [row for row in audit_file.rows if row.get("same_sample") is not True]
    kinds = Counter(str(row.get("kind", "")) for row in same_rows)
    truth_sources = Counter(str(row.get("truth_source", "unknown")) for row in same_rows)
    skill_hashes = Counter(str(row.get("skill_hash", "missing")) for row in same_rows)
    oracle_passes = sum(1 for row in same_rows if row.get("oracle_pass") is True)

    return {
        "round": number,
        "verdict_rows": len(verdict_file.rows),
        "d_fail_rate": round_num(safe_div(verdict_counts["fail"], len(verdict_file.rows))),
        "verdict_counts": dict(verdict_counts),
        "audit_rows": len(audit_file.rows),
        "same_sample_rows": len(same_rows),
        "legacy_or_misaligned_rows": len(legacy_rows),
        "oracle_pass_rate": round_num(safe_div(oracle_passes, len(same_rows))),
        "d_metrics": confusion_metrics(kinds),
        "truth_sources": dict(truth_sources),
        "skill_hashes": dict(skill_hashes),
        "jsonl_array_files": [
            name for name, parsed in (("verdicts.jsonl", verdict_file), ("audit.jsonl", audit_file))
            if parsed.array_instead_of_jsonl
        ],
    }, errors



def summarize_final_test(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, []
    errors: list[str] = []
    summary, summary_error = load_json(path / "summary.json")
    if summary_error:
        errors.append(summary_error)
    audit_file = read_jsonl(path / "audit.jsonl")
    errors.extend(audit_file.errors)
    same_rows = [row for row in audit_file.rows if row.get("same_sample") is True]
    counts = Counter(str(row.get("kind", "")) for row in same_rows)
    result: dict[str, Any] = {
        "path": str(path),
        "summary": summary if isinstance(summary, dict) else None,
        "same_sample_rows": len(same_rows),
        "d_metrics": confusion_metrics(counts),
    }
    return result, errors

def summarize_trajectories(directory: Path) -> dict[str, Any]:
    files = sorted(directory.glob("*.md")) if directory.exists() else []
    analyses = [_tc.analyze_file(path) for path in files]
    hard_codes: Counter[str] = Counter()
    warning_codes: Counter[str] = Counter()
    flagged: list[dict[str, Any]] = []
    hashes: Counter[str] = Counter()
    no_skill = 0
    for path, analysis in zip(files, analyses):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"(?m)^skill_hash:\s*(\S+)", text[:500])
        hashes[match.group(1) if match else "missing"] += 1
        hard_codes.update(x.get("code", "UNKNOWN") for x in analysis["hard_errors"])
        warning_codes.update(x.get("code", "UNKNOWN") for x in analysis["warnings"])
        if any(x.get("code") == "NO_ACTIVE_SKILL" for x in analysis["warnings"]):
            no_skill += 1
        if analysis["hard_errors"] or analysis["warnings"]:
            flagged.append({
                "item": path.stem,
                "quality_score": analysis["quality_score"],
                "hard_errors": analysis["hard_errors"],
                "warnings": analysis["warnings"],
            })
    flagged.sort(key=lambda row: (row["quality_score"], row["item"]))
    return {
        "directory": str(directory),
        "count": len(files),
        "skill_hashes": dict(hashes),
        "no_active_skill": no_skill,
        "hard_error_counts": dict(hard_codes),
        "warning_counts": dict(warning_codes),
        "flagged_count": len(flagged),
        "flagged": flagged,
        "note": "这些是轨迹内自洽/证据质量信号，不是 Oracle 正确率。",
    }


def load_json(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"{path}: {exc}"


def build_report(root: Path, trajectory_dir: Path | None = None) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    rounds = []
    total_counts: Counter[str] = Counter()
    same_total = 0
    legacy_total = 0
    for number, path in _round_dirs(root):
        summary, round_errors = summarize_round(number, path)
        rounds.append(summary)
        errors.extend(round_errors)
        total_counts.update(summary["d_metrics"]["counts"])
        same_total += summary["same_sample_rows"]
        legacy_total += summary["legacy_or_misaligned_rows"]

    ledger, ledger_error = load_json(root / "ledger.json")
    if ledger_error:
        errors.append(ledger_error)
    test_eval = read_jsonl(root / "stats" / "test_eval.jsonl")
    errors.extend(test_eval.errors)
    final_test, final_errors = summarize_final_test(root / "rounds" / "final_test")
    errors.extend(final_errors)

    traj_path = trajectory_dir if trajectory_dir is not None else root / "pool" / "traj.full"
    report = {
        "schema_version": 1,
        "root": str(root),
        "artifact_status": {
            "round_directories": len(rounds),
            "has_ledger": (root / "ledger.json").exists(),
            "has_report_md": (root / "report.md").exists(),
            "has_test_eval": bool(test_eval.rows),
            "has_final_test": final_test is not None,
            "same_sample_audits": same_total,
            "legacy_or_misaligned_audits": legacy_total,
        },
        "ledger": ledger,
        "rounds": rounds,
        "overall_d_metrics": confusion_metrics(total_counts),
        "test_eval": test_eval.rows,
        "final_test": final_test,
        "trajectories": summarize_trajectories(traj_path),
        "errors": errors,
    }
    return report, errors


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{100 * value:.2f}%"


def render_markdown(report: dict[str, Any]) -> str:
    status = report["artifact_status"]
    overall = report["overall_d_metrics"]
    traj = report["trajectories"]
    lines = [
        "# VeriSkill Result Summary",
        "",
        "## 可用产物",
        "",
        f"- 轮次目录：{status['round_directories']}",
        f"- ledger.json：{'有' if status['has_ledger'] else '无'}",
        f"- report.md：{'有' if status['has_report_md'] else '无'}",
        f"- test_eval 时间序列：{'有' if status['has_test_eval'] else '无'}",
        f"- held-out final test：{'有' if status['has_final_test'] else '无'}",
        f"- 可用于训练期 D 诊断的同样本审计：{status['same_sample_audits']}",
        f"- 被排除的旧式/错位审计：{status['legacy_or_misaligned_audits']}",
        "",
        "## 训练期 D 同样本审计诊断",
        "",
        "> 审计队列按 verdict/confidence 分层，以下数字用于找错与回归门控，不是无偏最终性能。",
        "",
        f"- TP/FP/FN/TN：{overall['counts']}",
        f"- FPR：{_pct(overall['fpr'])}",
        f"- FNR：{_pct(overall['fnr'])}",
        f"- Balanced accuracy：{_pct(overall['balanced_accuracy'])}",
        "",
        "| Round | D fail rate | Same-sample | Legacy/misaligned | Audited Oracle pass* | FPR* | FNR* | Bal. acc.* |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["rounds"]:
        metrics = row["d_metrics"]
        lines.append(
            f"| {row['round']} | {_pct(row['d_fail_rate'])} | {row['same_sample_rows']} | "
            f"{row['legacy_or_misaligned_rows']} | {_pct(row['oracle_pass_rate'])} | "
            f"{_pct(metrics['fpr'])} | {_pct(metrics['fnr'])} | {_pct(metrics['balanced_accuracy'])} |"
        )
    final_test = report.get("final_test")
    if final_test:
        fsummary = final_test.get("summary") or {}
        fmetrics = final_test.get("d_metrics") or {}
        lines.extend([
            "",
            "## Held-out final test（主要性能口径）",
            "",
            f"- G success rate：{_pct(fsummary.get('g_success_rate', fsummary.get('success_rate')))}",
            f"- Oracle judged/sample：{fsummary.get('n_oracle_judged', fsummary.get('n_judged', 0))}/{fsummary.get('n_sampled', 0)}",
            f"- Unscored/environment：{fsummary.get('n_unscored', 0)}/{fsummary.get('n_env_fail', 0)}",
            f"- D TP/FP/FN/TN：{fmetrics.get('counts', {})}",
            f"- D FPR：{_pct(fmetrics.get('fpr'))}",
            f"- D FNR：{_pct(fmetrics.get('fnr'))}",
            f"- D balanced accuracy：{_pct(fmetrics.get('balanced_accuracy'))}",
            "",
            "> 该口径在固定随机 test 样本上先用当前 G 重跑，再让 D 复判同一新轨迹。",
        ])
    else:
        lines.extend([
            "",
            "## Held-out final test（主要性能口径）",
            "",
            "- 尚无 `rounds/final_test/summary.json`；训练轨迹与分层审计不能替代最终性能。",
        ])

    lines.extend([
        "",
        "## 轨迹质量（非正确率）",
        "",
        f"- 完整轨迹数：{traj['count']}",
        f"- 未激活 G 技能：{traj['no_active_skill']}",
        f"- 确定性算术矛盾：{sum(traj['hard_error_counts'].values())}",
        f"- 证据/可识别性警告：{sum(traj['warning_counts'].values())}",
        f"- skill_hash 分布：`{json.dumps(traj['skill_hashes'], ensure_ascii=False)}`",
        "",
        "> 轨迹质量检查只判断文本内自洽与可复核性；真实正确率必须来自 checker/truth Oracle。",
    ])
    if traj["flagged"]:
        lines.extend(["", "### 优先复核", ""])
        for item in traj["flagged"][:20]:
            codes = [x["code"] for x in item["hard_errors"] + item["warnings"]]
            lines.append(f"- `{item['item']}`：{', '.join(codes)}")
    if report["errors"]:
        lines.extend(["", "## 产物格式错误", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--trajectory-dir", type=Path)
    parser.add_argument("--out-json", type=Path, default=Path("results/summary.json"))
    parser.add_argument("--out-md", type=Path, default=Path("results/summary.md"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    trajectory_dir = args.trajectory_dir
    if trajectory_dir is not None and not trajectory_dir.is_absolute():
        trajectory_dir = root / trajectory_dir
    report, errors = build_report(root, trajectory_dir)
    out_json = args.out_json if args.out_json.is_absolute() else root / args.out_json
    out_md = args.out_md if args.out_md.is_absolute() else root / args.out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "json": str(out_json),
        "markdown": str(out_md),
        "rounds": len(report["rounds"]),
        "same_sample_audits": report["artifact_status"]["same_sample_audits"],
        "trajectory_count": report["trajectories"]["count"],
        "errors": len(errors),
    }, ensure_ascii=False))
    if args.strict and errors:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
