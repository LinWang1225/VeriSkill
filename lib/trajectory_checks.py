#!/usr/bin/env python3
"""Cheap, deterministic trajectory checks for VeriSkill.

These checks do not replace Oracle truth. They only catch contradictions that are
fully visible in the trajectory and surface evidence-quality risks for audit.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

NUMBER = r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
DIV_RE = re.compile(rf"(?P<a>{NUMBER})\s*(?:/|÷)\s*(?P<b>{NUMBER})\s*=\s*(?P<c>{NUMBER})")
MUL_RE = re.compile(rf"(?P<a>{NUMBER})\s*(?:×|\*)\s*(?P<b>{NUMBER})\s*=\s*(?P<c>{NUMBER})")
EXP_RE = re.compile(rf"(?:e|exp)\s*\^?\s*\(?\s*(?P<a>{NUMBER})\s*\)?\s*=\s*(?P<c>{NUMBER})", re.I)
SUM_RE = re.compile(rf"(?P<expr>{NUMBER}(?:\s*\+\s*{NUMBER}){{2,}})\s*=\s*(?P<c>{NUMBER})")
CLAIMED_COUNT_RE = re.compile(
    r"(?:共|全部|所有|all)\s*(?P<n>\d{2,4})\s*(?:个|条|月|months?|values?)",
    re.I,
)
MONTH_TOKEN_RE = re.compile(
    r"(?:\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*=)"
    r"|(?:\b\d{4}\s*年\s*\d{1,2}\s*月)",
    re.I,
)


def _num(value: str) -> float:
    return float(value.replace(",", ""))


def _close(actual: float, expected: float) -> bool:
    tolerance = max(0.015, abs(expected) * 5e-4)
    return math.isfinite(actual) and math.isfinite(expected) and abs(actual - expected) <= tolerance


def _issue(code: str, severity: str, message: str, line: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code, "severity": severity, "message": message}
    if line is not None:
        out["line"] = line
    return out


def _iter_matches(pattern: re.Pattern[str], lines: Iterable[str]):
    for lineno, line in enumerate(lines, 1):
        for match in pattern.finditer(line):
            yield lineno, line, match


def _arithmetic_issues(lines: list[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()

    for lineno, line, match in _iter_matches(DIV_RE, lines):
        a, b, c = (_num(match.group(k)) for k in ("a", "b", "c"))
        if b == 0:
            continue
        expected = a / b
        if not _close(c, expected):
            key = ("ARITH_DIV", lineno, match.group(0))
            if key not in seen:
                seen.add(key)
                issues.append(_issue(
                    "ARITH_DIV", "error",
                    f"可见算式不一致：{match.group(0)}，左侧实际约为 {expected:.8g}", lineno,
                ))

    for lineno, line, match in _iter_matches(MUL_RE, lines):
        a, b, c = (_num(match.group(k)) for k in ("a", "b", "c"))
        expected = a * b
        if not _close(c, expected):
            key = ("ARITH_MUL", lineno, match.group(0))
            if key not in seen:
                seen.add(key)
                issues.append(_issue(
                    "ARITH_MUL", "error",
                    f"可见算式不一致：{match.group(0)}，左侧实际约为 {expected:.8g}", lineno,
                ))

    for lineno, line, match in _iter_matches(EXP_RE, lines):
        exponent, c = _num(match.group("a")), _num(match.group("c"))
        if abs(exponent) > 50:
            continue
        expected = math.exp(exponent)
        if not _close(c, expected):
            key = ("ARITH_EXP", lineno, match.group(0))
            if key not in seen:
                seen.add(key)
                issues.append(_issue(
                    "ARITH_EXP", "error",
                    f"可见指数算式不一致：{match.group(0)}，左侧实际约为 {expected:.8g}", lineno,
                ))

    for lineno, line, match in _iter_matches(SUM_RE, lines):
        values = [_num(v) for v in re.findall(NUMBER, match.group("expr"))]
        c = _num(match.group("c"))
        expected = sum(values)
        if not _close(c, expected):
            key = ("ARITH_SUM", lineno, match.group(0))
            if key not in seen:
                seen.add(key)
                issues.append(_issue(
                    "ARITH_SUM", "error",
                    f"可见求和不一致：声明 {c:g}，逐项相加约为 {expected:.8g}", lineno,
                ))
    return issues


def _structural_sections(text: str) -> dict[str, str]:
    """Extract the four canonical sections while tolerating ## step headings inside process."""
    lines = text.splitlines()
    markers: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if not match:
            continue
        title = match.group(1).strip().lower()
        if "题目" in title or title == "task":
            markers.append((index, "task"))
        elif "激活技能" in title or title in ("skills", "active skills"):
            markers.append((index, "skills"))
        elif title in ("过程", "process", "reasoning", "execution"):
            markers.append((index, "process"))
        elif "最终答案" in title or title in ("final answer", "answer"):
            markers.append((index, "final"))
    out = {"task": "", "skills": "", "process": "", "final": ""}
    for position, (start, name) in enumerate(markers):
        end = markers[position + 1][0] if position + 1 < len(markers) else len(lines)
        out[name] = "\n".join(lines[start + 1:end]).strip()
    return out


def analyze_text(text: str, path: str = "") -> dict[str, Any]:
    lines = text.splitlines()
    sections = _structural_sections(text)
    hard_errors = _arithmetic_issues(lines)
    warnings: list[dict[str, Any]] = []

    task = sections["task"]
    process = sections["process"]
    final = sections["final"]
    skills = sections["skills"]

    if not task:
        warnings.append(_issue("MISSING_TASK", "warning", "缺少可解析的题目节"))
    if not final:
        warnings.append(_issue("MISSING_FINAL", "warning", "缺少可解析的最终答案节"))
    if re.search(r"未使用技能|no skills? used", skills, re.I):
        warnings.append(_issue("NO_ACTIVE_SKILL", "warning", "轨迹未使用任何 G 技能，无法体现技能改进效果"))

    claimed = [int(m.group("n")) for m in CLAIMED_COUNT_RE.finditer(process)]
    observed_months = len(MONTH_TOKEN_RE.findall(process))
    for n in claimed:
        if n >= 12 and observed_months < min(12, max(4, math.ceil(n * 0.25))):
            warnings.append(_issue(
                "EVIDENCE_AGGREGATE_OPAQUE", "warning",
                f"过程声称处理 {n} 个值，但轨迹只显式展示约 {observed_months} 个按月值；D 无法独立复算",
            ))
            break

    if re.search(r"Python\s*脚本|script\s+(?:extracted|computed)|通过.*脚本", process, re.I):
        if not re.search(r"```(?:python)?|stdout|输出[:：]|\[[^\]]{20,}\]", process, re.I):
            warnings.append(_issue(
                "OPAQUE_TOOL_CLAIM", "warning",
                "过程依赖脚本提取/计算的结论，但没有保留代码、完整输入或可复核输出",
            ))

    # A denomination total divided by its face value must normally imply an integer bill count.
    for lineno, line in enumerate(lines, 1):
        if "张" not in line or not re.search(r"\$\s*\d", line):
            continue
        match = DIV_RE.search(line)
        if match:
            count = _num(match.group("a")) / _num(match.group("b"))
            if abs(count - round(count)) > 1e-8:
                warnings.append(_issue(
                    "NON_INTEGER_BILL_COUNT", "warning",
                    f"按面额反推纸币张数得到非整数 {count:g}，需核对列含义、单位或数据抄录", lineno,
                ))

    task_mentions_maturity = bool(re.search(r"到期|matur(?:ity|e)|face value|面值", task, re.I))
    process_assumes_maturity = bool(re.search(
        r"第二个观察时点到期|second (?:observation|observed).*matur|面值等于第二个|D\s*=\s*1",
        process,
        re.I,
    ))
    if process_assumes_maturity and not task_mentions_maturity:
        warnings.append(_issue(
            "UNSUPPORTED_MATURITY_ASSUMPTION", "warning",
            "过程额外假设第二个观察时点即到期/面值等于第二个价格；题目未提供该可识别条件",
        ))

    if re.search(r"report in millions|in millions of|百万", task, re.I):
        if final and re.fullmatch(r"\s*[-+]?\d[\d,.]*\s*", final):
            warnings.append(_issue("FINAL_UNIT_MISSING", "warning", "题目要求单位，但最终答案只给数值"))

    if "skill_hash:" not in text[:300]:
        warnings.append(_issue("MISSING_SKILL_HASH", "warning", "frontmatter 缺少 skill_hash，无法做版本对齐"))

    score = max(0.0, 1.0 - 0.35 * len(hard_errors) - 0.08 * len(warnings))
    return {
        "path": path,
        "hard_errors": hard_errors,
        "warnings": warnings,
        "quality_score": round(score, 3),
    }


def analyze_file(path: Path) -> dict[str, Any]:
    return analyze_text(path.read_text(encoding="utf-8", errors="replace"), str(path))



def verdict_from_checks(item: str, checks: dict[str, Any]) -> dict[str, Any]:
    hard = checks.get("hard_errors") if isinstance(checks.get("hard_errors"), list) else []
    warnings = checks.get("warnings") if isinstance(checks.get("warnings"), list) else []
    if not hard:
        raise ValueError("verdict_from_checks requires at least one hard error")
    summary = "; ".join(str(x.get("message", "")) for x in hard[:2])
    return {
        "item": item,
        "verdict": "fail",
        "model_verdict": "not_run",
        "verdict_corrected": False,
        "hard_rule_hit": True,
        "rules_hit": [],
        "rubric_scores": {},
        "normalized_score": None,
        "critic_verdict": "not_applicable",
        "independent_verdict": "fail",
        "independent_direct_error": True,
        "disagreement": False,
        "evidence_coverage": 1.0,
        "applicable_critics": [],
        "confidence": 0.99,
        "reason": f"确定性自洽检查命中：{summary}"[:600],
        "static_override": True,
        "static_hard_errors": hard,
        "static_warnings": warnings,
        "audit_priority": "high",
    }

def merge_verdict(verdict: dict[str, Any], checks: dict[str, Any]) -> dict[str, Any]:
    out = dict(verdict)
    hard = checks.get("hard_errors") if isinstance(checks.get("hard_errors"), list) else []
    warnings = checks.get("warnings") if isinstance(checks.get("warnings"), list) else []
    out["static_hard_errors"] = hard
    out["static_warnings"] = warnings
    if hard:
        out["verdict"] = "fail"
        out["static_override"] = True
        out["hard_rule_hit"] = True
        out["confidence"] = max(float(out.get("confidence", 0.0) or 0.0), 0.95)
        summary = "; ".join(str(x.get("message", "")) for x in hard[:2])
        original = str(out.get("reason", ""))
        out["reason"] = (f"确定性自洽检查命中：{summary}。模型判决：{original}")[:600]
    else:
        out["static_override"] = False
        if warnings:
            # Evidence-quality warnings are not correctness labels. They only force audit priority.
            out["confidence"] = min(float(out.get("confidence", 0.0) or 0.0), 0.45)
            out["audit_priority"] = "high"
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("trajectory", type=Path)
    merge = sub.add_parser("merge-verdict")
    merge.add_argument("--checks", type=Path, required=True)
    merge.add_argument("--verdict", type=Path, required=True)
    direct = sub.add_parser("verdict-from-checks")
    direct.add_argument("--checks", type=Path, required=True)
    direct.add_argument("--item", required=True)
    args = parser.parse_args()

    if args.cmd == "check":
        result = analyze_file(args.trajectory)
    elif args.cmd == "verdict-from-checks":
        checks = json.loads(args.checks.read_text(encoding="utf-8"))
        result = verdict_from_checks(args.item, checks)
    else:
        checks = json.loads(args.checks.read_text(encoding="utf-8"))
        verdict = json.loads(args.verdict.read_text(encoding="utf-8"))
        result = merge_verdict(verdict, checks)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
