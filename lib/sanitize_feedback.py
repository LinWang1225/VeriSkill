#!/usr/bin/env python3
"""Sanitize Oracle feedback before it becomes cross-round G/D memory."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

SENSITIVE_KEYS = {
    "item",
    "baseline_evidence",
    "candidate_evidence",
    "baseline_result",
    "candidate_result",
    "skill_result",
    "gold",
    "prediction",
    "pred",
}
G_ALLOWED_ITEM_KINDS = {"improvement", "regression", "unresolved_fail"}
GOLD_PRED_RE = re.compile(r"\b(?:gold|pred(?:iction)?)\s*[=:]", re.IGNORECASE)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
        rows.append(value)
    return rows


def dump_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
    tmp.replace(path)


def _case_tokens(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    item_ids = sorted(
        {
            str(row["item"])
            for row in rows
            if isinstance(row.get("item"), str) and row.get("item")
        }
    )
    return {item_id: f"case-{index:03d}" for index, item_id in enumerate(item_ids, 1)}


def _sanitize_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "record_type",
        "schema_version",
        "round",
        "candidate_version",
        "gd_revisions",
        "review_verdict",
        "review_calibration",
        "scored_pairs",
        "counts",
        "excluded",
        "baseline_pass_rate",
        "candidate_pass_rate",
        "net_gain",
        "accepted",
        "decision_status",
        "decision_reasons",
    }
    return {key: row[key] for key in allowed if key in row}


def _diagnostic_label(row: Mapping[str, Any]) -> str:
    evidence = " ".join(
        str(row.get(key, ""))
        for key in ("baseline_evidence", "candidate_evidence")
    ).lower()
    if "numeric-list" in evidence:
        return "structured_numeric_list_check"
    if "numeric-scalar" in evidence:
        return "numeric_scalar_check"
    if "format" in evidence:
        return "format_check"
    if "score_answer" in evidence:
        return "semantic_answer_check"
    return "oracle_outcome_only"


def _sanitize_item(row: Mapping[str, Any], case_id: str, channel: str) -> dict[str, Any] | None:
    kind = str(row.get("kind", ""))
    if channel == "g" and kind not in G_ALLOWED_ITEM_KINDS:
        return None
    clean: dict[str, Any] = {
        "record_type": "case",
        "case_id": case_id,
        "kind": kind,
        "truth_source": row.get("truth_source"),
        "baseline_pass": row.get("baseline_pass"),
        "candidate_pass": row.get("candidate_pass"),
        "diagnostic": _diagnostic_label(row),
        "feedback_scope": "train_only",
    }
    # Preserve only non-answer diagnostic labels explicitly emitted by future checkers.
    for key in (
        "failure_type", "format_pass", "semantic_pass", "change_group",
        "review_status", "skill_refs",
    ):
        if key in row:
            clean[key] = row[key]
    return clean


def sanitize_records(rows: list[dict[str, Any]], channel: str) -> list[dict[str, Any]]:
    if channel not in {"g", "d"}:
        raise ValueError("channel must be g or d")
    tokens = _case_tokens(rows)
    sanitized: list[dict[str, Any]] = []
    for row in rows:
        if row.get("record_type") == "candidate_summary":
            sanitized.append(_sanitize_summary(row))
            continue
        item = row.get("item")
        if not isinstance(item, str) or item not in tokens:
            continue
        clean = _sanitize_item(row, tokens[item], channel)
        if clean is not None:
            sanitized.append(clean)
    return sanitized


def _load_ids(meta_path: Path) -> list[str]:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    items = meta.get("items")
    if not isinstance(items, list):
        raise ValueError("meta.json must contain items")
    return sorted(
        str(row["id"])
        for row in items
        if isinstance(row, dict) and isinstance(row.get("id"), str) and row.get("id")
    )


def lint_tree(root: Path, meta_path: Path) -> list[str]:
    ids = _load_ids(meta_path)
    violations: list[str] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file() or file_path.suffix not in {".md", ".json", ".jsonl", ".txt"}:
            continue
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for item_id in ids:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(item_id)}(?![A-Za-z0-9_])", text):
                violations.append(f"{file_path}: contains item id {item_id}")
        if GOLD_PRED_RE.search(text):
            violations.append(f"{file_path}: contains gold/pred answer material")
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sanitize = sub.add_parser("sanitize")
    sanitize.add_argument("--input", required=True)
    sanitize.add_argument("--output", required=True)
    sanitize.add_argument("--channel", choices=("g", "d"), required=True)

    lint = sub.add_parser("lint-tree")
    lint.add_argument("--root", required=True)
    lint.add_argument("--meta", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "sanitize":
            rows = load_jsonl(Path(args.input))
            dump_jsonl(Path(args.output), sanitize_records(rows, args.channel))
            return 0
        violations = lint_tree(Path(args.root), Path(args.meta))
        if violations:
            print("\n".join(violations), file=sys.stderr)
            return 2
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"sanitize_feedback: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
