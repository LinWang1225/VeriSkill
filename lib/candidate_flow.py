#!/usr/bin/env python3
"""Utilities for VeriSkill's candidate-skill review and Oracle comparison flow.

The helper intentionally contains no model calls. It provides deterministic filesystem
operations, schema validation, Oracle queue construction, same-candidate comparison,
and atomic promotion of an accepted candidate skill library.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence

from fingerprint import hash_dir as canonical_hash_dir, hash_file
from sanitize_feedback import sanitize_records

RELIABLE_TRUTH = {"checker", "truth"}
REVIEW_VERDICTS = {"PASS", "REVISE", "ABSTAIN"}
COVERAGE_STATES = {"covered", "partial", "uncovered", "unjudgeable"}


class FlowError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FlowError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FlowError(f"invalid JSON in {path}: {exc}") from exc


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise FlowError(f"missing JSONL file: {path}") from exc
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FlowError(f"invalid JSONL at {path}:{lineno}: {exc}") from exc
        if not isinstance(value, dict):
            raise FlowError(f"JSONL row must be an object at {path}:{lineno}")
        rows.append(value)
    return rows


def dump_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def read_batch(path: Path) -> List[str]:
    ids: List[str] = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if not item:
            continue
        if item in seen:
            raise FlowError(f"duplicate item in batch: {item}")
        seen.add(item)
        ids.append(item)
    if not ids:
        raise FlowError(f"empty batch: {path}")
    return ids


def hash_dir(path: Path) -> str:
    try:
        return canonical_hash_dir(path)
    except ValueError as exc:
        raise FlowError(str(exc)) from exc


def copytree_clean(src: Path, dst: Path) -> None:
    if not src.exists():
        src.mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        raise FlowError(f"source is not a directory: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def cmd_prepare(args: argparse.Namespace) -> None:
    actor = Path(args.actor).resolve()
    round_dir = Path(args.round_dir).resolve()
    baseline = round_dir / "baseline_skills"
    candidate = round_dir / "candidate" / "iter0"
    state_path = round_dir / "candidate_state.json"
    if any(p.exists() for p in (baseline, candidate, state_path)) and not args.force:
        if state_path.is_file() and baseline.is_dir() and candidate.is_dir():
            state = load_json(state_path)
            if state.get("baseline_fingerprint") != hash_dir(baseline):
                raise FlowError(f"existing baseline snapshot changed: {baseline}")
            state = dict(state)
            state["resumed"] = True
            print(json.dumps(state, ensure_ascii=False))
            return
        raise FlowError(f"partially prepared round: {round_dir}; inspect it before using --force")
    if args.force:
        for path in (baseline, candidate):
            if path.exists():
                shutil.rmtree(path)
        if state_path.exists():
            state_path.unlink()
    for name in ("reviews", "oracle/baseline", "oracle/candidate", "feedback", "manifests"):
        (round_dir / name).mkdir(parents=True, exist_ok=True)
    actor.mkdir(parents=True, exist_ok=True)
    copytree_clean(actor, baseline)
    copytree_clean(actor, candidate)
    state = {
        "schema_version": 1,
        "baseline_dir": str(baseline),
        "baseline_fingerprint": hash_dir(baseline),
        "current_iteration": 0,
        "candidate_dir": str(candidate),
        "candidate_fingerprint": hash_dir(candidate),
        "status": "prepared",
    }
    dump_json(state_path, state)
    print(json.dumps(state, ensure_ascii=False))


def cmd_clone_iteration(args: argparse.Namespace) -> None:
    round_dir = Path(args.round_dir).resolve()
    src = round_dir / "candidate" / f"iter{args.from_iter}"
    dst = round_dir / "candidate" / f"iter{args.to_iter}"
    if args.to_iter <= args.from_iter:
        raise FlowError("--to-iter must be greater than --from-iter")
    if not src.is_dir():
        raise FlowError(f"missing source candidate: {src}")
    if dst.exists() and not args.force:
        if not dst.is_dir():
            raise FlowError(f"destination candidate is not a directory: {dst}")
        state_path = round_dir / "candidate_state.json"
        state = load_json(state_path)
        state.update({
            "current_iteration": args.to_iter,
            "candidate_dir": str(dst),
            "candidate_fingerprint": hash_dir(dst),
            "status": "revision_resumed",
            "resumed": True,
        })
        dump_json(state_path, state)
        print(json.dumps(state, ensure_ascii=False))
        return
    copytree_clean(src, dst)
    state_path = round_dir / "candidate_state.json"
    state = load_json(state_path)
    state.update({
        "current_iteration": args.to_iter,
        "candidate_dir": str(dst),
        "candidate_fingerprint": hash_dir(dst),
        "status": "revision_prepared",
    })
    dump_json(state_path, state)
    print(json.dumps(state, ensure_ascii=False))


def _as_string_list(value: Any, field: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
        raise FlowError(f"{field} must be a list of non-empty strings")
    return value


def cmd_validate_manifest(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    candidate_dir = Path(args.candidate_dir)
    batch = read_batch(Path(args.batch))
    batch_set = set(batch)
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise FlowError("manifest must be a JSON object")
    for field in ("candidate_version", "base_fingerprint", "trajectory_clusters", "changes",
                  "expected_coverage", "uncovered", "response_to_d"):
        if field not in manifest:
            raise FlowError(f"manifest missing field: {field}")
    if args.base_fingerprint and manifest["base_fingerprint"] != args.base_fingerprint:
        raise FlowError("manifest base_fingerprint does not match the round baseline")
    if not isinstance(manifest["trajectory_clusters"], list):
        raise FlowError("trajectory_clusters must be a list")
    if not isinstance(manifest["changes"], list):
        raise FlowError("changes must be a list")
    if not isinstance(manifest["expected_coverage"], dict):
        raise FlowError("expected_coverage must be an object keyed by item id")
    uncovered = set(_as_string_list(manifest["uncovered"], "uncovered"))
    response_to_d = manifest["response_to_d"]
    if not isinstance(response_to_d, list):
        raise FlowError("response_to_d must be a list")
    covered = set(manifest["expected_coverage"])
    extras = (covered | uncovered) - batch_set
    missing = batch_set - covered - uncovered
    overlap = covered & uncovered
    if extras:
        raise FlowError(f"manifest references items outside current_batch: {sorted(extras)}")
    if missing:
        raise FlowError(f"manifest omits current_batch items: {sorted(missing)}")
    if overlap:
        raise FlowError(f"items cannot be both covered and uncovered: {sorted(overlap)}")
    for item, refs in manifest["expected_coverage"].items():
        _as_string_list(refs, f"expected_coverage[{item}]")
    normalized = dict(manifest)
    candidate_fingerprint = hash_dir(candidate_dir)
    normalized["candidate_fingerprint"] = candidate_fingerprint
    normalized["batch_size"] = len(batch)
    if args.out:
        dump_json(Path(args.out), normalized)
    if args.state:
        state_path = Path(args.state)
        state = load_json(state_path)
        if not isinstance(state, dict):
            raise FlowError("candidate state must be a JSON object")
        if args.base_fingerprint and state.get("baseline_fingerprint") != args.base_fingerprint:
            raise FlowError("candidate state baseline_fingerprint does not match the manifest")
        state.update({
            "candidate_dir": str(candidate_dir.resolve()),
            "candidate_fingerprint": candidate_fingerprint,
            "manifest_hash": hash_file(manifest_path),
            "status": "g_validated",
        })
        dump_json(state_path, state)
    print(json.dumps(normalized, ensure_ascii=False))


def cmd_validate_review(args: argparse.Namespace) -> None:
    review_path = Path(args.review)
    batch = read_batch(Path(args.batch))
    batch_set = set(batch)
    review = load_json(review_path)
    if not isinstance(review, dict):
        raise FlowError("review must be a JSON object")
    if review.get("mode") != "review_candidate":
        raise FlowError("review.mode must be review_candidate")
    verdict = str(review.get("verdict", "")).upper()
    if verdict not in REVIEW_VERDICTS:
        raise FlowError(f"invalid review verdict: {verdict}")
    if args.candidate_fingerprint and review.get("candidate_fingerprint") != args.candidate_fingerprint:
        raise FlowError("review candidate_fingerprint does not match the reviewed directory")
    confidence = review.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        raise FlowError("review.confidence must be in [0,1]")
    coverage = review.get("coverage")
    if not isinstance(coverage, list):
        raise FlowError("review.coverage must be a list")
    by_item: Dict[str, Dict[str, Any]] = {}
    for row in coverage:
        if not isinstance(row, dict):
            raise FlowError("each coverage row must be an object")
        item = row.get("item")
        status = row.get("status")
        if item not in batch_set:
            raise FlowError(f"coverage item outside current_batch: {item}")
        if item in by_item:
            raise FlowError(f"duplicate coverage row: {item}")
        if status not in COVERAGE_STATES:
            raise FlowError(f"invalid coverage status for {item}: {status}")
        by_item[item] = row
    missing = batch_set - set(by_item)
    if missing:
        raise FlowError(f"review omits current_batch items: {sorted(missing)}")
    hard_defects = review.get("hard_defects", [])
    soft_concerns = review.get("soft_concerns", [])
    feedback = review.get("feedback_to_g", [])
    if not all(isinstance(x, list) for x in (hard_defects, soft_concerns, feedback)):
        raise FlowError("hard_defects, soft_concerns and feedback_to_g must be lists")
    if verdict == "REVISE" and not (hard_defects or feedback):
        raise FlowError("REVISE requires hard_defects or actionable feedback_to_g")
    normalized = dict(review)
    normalized["verdict"] = verdict
    normalized["coverage"] = [by_item[item] for item in batch]
    if args.out:
        dump_json(Path(args.out), normalized)
    print(json.dumps(normalized, ensure_ascii=False))


def _truth_source(item: str, checker_dir: Path, truth_dir: Path) -> str | None:
    checker = checker_dir / f"{item}.sh"
    if checker.is_file() and os.access(checker, os.X_OK):
        return "checker"
    if (truth_dir / f"{item}.md").is_file():
        return "truth"
    return None


def cmd_build_oracle_queue(args: argparse.Namespace) -> None:
    batch = read_batch(Path(args.batch))
    review = load_json(Path(args.review))
    verdict = str(review.get("verdict", "")).upper()
    if verdict not in REVIEW_VERDICTS:
        raise FlowError(f"invalid review verdict: {verdict}")
    coverage = {row["item"]: row for row in review.get("coverage", []) if isinstance(row, dict)}
    checker_dir = Path(args.checker_dir)
    truth_dir = Path(args.truth_dir)
    eligible: List[Dict[str, Any]] = []
    for item in batch:
        source = _truth_source(item, checker_dir, truth_dir)
        if not source:
            continue
        row = coverage.get(item, {})
        eligible.append({
            "item": item,
            "review_status": row.get("status", "unjudgeable"),
            "truth_source": source,
        })
    rng = random.Random(args.round)
    random_key = {row["item"]: rng.random() for row in eligible}
    if verdict == "REVISE":
        priority = {"uncovered": 0, "partial": 1, "unjudgeable": 2, "covered": 3}
        limit = min(args.revise_audit, len(eligible))
        reason = "revise_audit"
    else:
        priority = {"unjudgeable": 0, "partial": 1, "covered": 2, "uncovered": 3}
        limit = min(args.budget, len(eligible))
        reason = "candidate_gate"
    eligible.sort(
        key=lambda row: (priority.get(row["review_status"], 9), random_key[row["item"]], row["item"])
    )
    chosen = []
    for row in eligible[:limit]:
        row = dict(row)
        row["reason"] = reason
        row["review_verdict"] = verdict
        chosen.append(row)
    dump_jsonl(Path(args.out), chosen)
    print(json.dumps({
        "review_verdict": verdict,
        "eligible": len(eligible),
        "selected": len(chosen),
        "excluded_unscored": len(batch) - len(eligible),
    }, ensure_ascii=False))


def _index_oracle(rows: Sequence[Mapping[str, Any]], label: str) -> Dict[str, Mapping[str, Any]]:
    index: Dict[str, Mapping[str, Any]] = {}
    for row in rows:
        item = row.get("item")
        if not isinstance(item, str) or not item:
            raise FlowError(f"{label} Oracle row missing item")
        if item in index:
            raise FlowError(f"duplicate {label} Oracle result: {item}")
        index[item] = row
    return index


def _safe_rate(num: int, den: int) -> float | None:
    return round(num / den, 6) if den else None


def cmd_compare(args: argparse.Namespace) -> None:
    review = load_json(Path(args.review))
    review_verdict = str(review.get("verdict", "")).upper()
    if review_verdict not in REVIEW_VERDICTS:
        raise FlowError(f"invalid review verdict: {review_verdict}")
    review_coverage = {
        str(row.get("item")): row
        for row in review.get("coverage", [])
        if isinstance(row, dict) and isinstance(row.get("item"), str)
    }
    baseline_rows = load_jsonl(Path(args.baseline))
    candidate_rows = load_jsonl(Path(args.candidate))
    baseline = _index_oracle(baseline_rows, "baseline")
    candidate = _index_oracle(candidate_rows, "candidate")
    common = sorted(set(baseline) & set(candidate))
    comparisons: List[Dict[str, Any]] = []
    counts = {"improvement": 0, "regression": 0, "retained_pass": 0, "unresolved_fail": 0}
    excluded = {"unreliable_truth": 0, "mismatched_truth_source": 0, "missing_pair": 0}
    excluded["missing_pair"] = len(set(baseline) ^ set(candidate))
    for item in common:
        b = baseline[item]
        c = candidate[item]
        b_source = b.get("truth_source")
        c_source = c.get("truth_source")
        if b_source not in RELIABLE_TRUTH or c_source not in RELIABLE_TRUTH:
            excluded["unreliable_truth"] += 1
            continue
        if b_source != c_source:
            excluded["mismatched_truth_source"] += 1
            continue
        if not isinstance(b.get("oracle_pass"), bool) or not isinstance(c.get("oracle_pass"), bool):
            excluded["unreliable_truth"] += 1
            continue
        bp = bool(b["oracle_pass"])
        cp = bool(c["oracle_pass"])
        if not bp and cp:
            kind = "improvement"
        elif bp and not cp:
            kind = "regression"
        elif bp and cp:
            kind = "retained_pass"
        else:
            kind = "unresolved_fail"
        counts[kind] += 1
        review_row = review_coverage.get(item, {})
        comparisons.append({
            "item": item,
            "kind": kind,
            "review_status": review_row.get("status"),
            "skill_refs": review_row.get("candidate_evidence", []),
            "baseline_pass": bp,
            "candidate_pass": cp,
            "truth_source": b_source,
            "baseline_skill_hash": b.get("skill_hash"),
            "candidate_skill_hash": c.get("skill_hash"),
            "baseline_evidence": b.get("evidence", ""),
            "candidate_evidence": c.get("evidence", ""),
            "baseline_result": b.get("skill_result", ""),
            "candidate_result": c.get("skill_result", ""),
        })
    scored = len(comparisons)
    baseline_passes = counts["regression"] + counts["retained_pass"]
    candidate_passes = counts["improvement"] + counts["retained_pass"]
    net_gain = counts["improvement"] - counts["regression"]
    baseline_fp = hash_dir(Path(args.baseline_dir))
    candidate_fp = hash_dir(Path(args.candidate_dir))
    baseline_oracle_hashes = sorted({
        str(row.get("skill_hash")) for row in baseline_rows if row.get("skill_hash")
    })
    candidate_oracle_hashes = sorted({
        str(row.get("skill_hash")) for row in candidate_rows if row.get("skill_hash")
    })
    fingerprint_issues: List[str] = []
    if baseline_oracle_hashes != [baseline_fp]:
        fingerprint_issues.append(
            f"baseline Oracle skill_hash {baseline_oracle_hashes} != expected {baseline_fp}"
        )
    if candidate_oracle_hashes != [candidate_fp]:
        fingerprint_issues.append(
            f"candidate Oracle skill_hash {candidate_oracle_hashes} != expected {candidate_fp}"
        )
    decision_status = "inconclusive" if fingerprint_issues else "scored"
    reasons: List[str] = list(fingerprint_issues)
    accepted = not fingerprint_issues
    if review_verdict == "REVISE":
        accepted = False
        reasons.append("D_REVISE candidates are calibration-only and cannot be promoted")
    if scored < args.min_scored:
        accepted = False
        reasons.append(f"scored_pairs {scored} < min_scored {args.min_scored}")
    if counts["improvement"] < args.min_improvements:
        accepted = False
        reasons.append(
            f"improvements {counts['improvement']} < min_improvements {args.min_improvements}"
        )
    if counts["regression"] > args.max_regressions:
        accepted = False
        reasons.append(
            f"regressions {counts['regression']} > max_regressions {args.max_regressions}"
        )
    if net_gain <= 0:
        accepted = False
        reasons.append(f"net_gain {net_gain} must be positive")
    if candidate_passes < baseline_passes:
        accepted = False
        reasons.append("candidate pass count is below baseline on paired items")
    if accepted:
        reasons.append("candidate improves at least one paired item with no disallowed regression")
    review_calibration = "not_scored"
    if decision_status == "inconclusive":
        review_calibration = "not_scored"
    elif review_verdict == "PASS":
        review_calibration = "correct_accept" if accepted else "false_accept"
    elif review_verdict == "REVISE":
        review_calibration = "false_reject_evidence" if counts["improvement"] > 0 else "supported_revise"
    elif review_verdict == "ABSTAIN":
        review_calibration = "useful_abstain" if scored else "unresolved_abstain"
    summary = {
        "schema_version": 1,
        "round": args.round,
        "candidate_version": args.candidate_version,
        "gd_revisions": args.gd_revisions,
        "review_verdict": review_verdict,
        "review_calibration": review_calibration,
        "decision_status": decision_status,
        "baseline_fingerprint": baseline_fp,
        "candidate_fingerprint": candidate_fp,
        "baseline_oracle_skill_hashes": baseline_oracle_hashes,
        "candidate_oracle_skill_hashes": candidate_oracle_hashes,
        "scored_pairs": scored,
        "counts": counts,
        "excluded": excluded,
        "baseline_pass_rate": _safe_rate(baseline_passes, scored),
        "candidate_pass_rate": _safe_rate(candidate_passes, scored),
        "net_gain": net_gain,
        "accepted": accepted,
        "decision_reasons": reasons,
    }
    dump_jsonl(Path(args.out_comparison), comparisons)
    dump_json(Path(args.out_decision), summary)
    raw_to_d: List[Mapping[str, Any]] = [{"record_type": "candidate_summary", **summary}]
    raw_to_d.extend({"record_type": "item", **row} for row in comparisons)
    raw_to_g = []
    for row in comparisons:
        if row["kind"] in {"improvement", "regression", "unresolved_fail"}:
            raw_to_g.append({
                "record_type": "item",
                "item": row["item"],
                "kind": row["kind"],
                "baseline_pass": row["baseline_pass"],
                "candidate_pass": row["candidate_pass"],
                "truth_source": row["truth_source"],
                "review_status": row.get("review_status"),
                "skill_refs": row.get("skill_refs", []),
                "candidate_evidence": row["candidate_evidence"],
                "candidate_result": row["candidate_result"],
                "feedback_scope": "train_only",
            })
    if args.out_to_d_raw:
        dump_jsonl(Path(args.out_to_d_raw), raw_to_d)
    if args.out_to_g_raw:
        dump_jsonl(Path(args.out_to_g_raw), raw_to_g)
    if decision_status == "inconclusive":
        raw_to_d = [{"record_type": "candidate_summary", **summary}]
        raw_to_g = []
    dump_jsonl(Path(args.out_to_d), sanitize_records([dict(row) for row in raw_to_d], "d"))
    dump_jsonl(Path(args.out_to_g), sanitize_records([dict(row) for row in raw_to_g], "g"))
    if args.metrics:
        metrics_path = Path(args.metrics)
        existing = load_jsonl(metrics_path) if metrics_path.exists() else []
        existing = [
            row for row in existing
            if not (row.get("round") == summary["round"] and
                    row.get("candidate_version") == summary["candidate_version"])
        ]
        existing.append(summary)
        existing.sort(key=lambda row: (int(row.get("round") or 0), str(row.get("candidate_version") or "")))
        dump_jsonl(metrics_path, existing)
    print(json.dumps(summary, ensure_ascii=False))


def cmd_commit(args: argparse.Namespace) -> None:
    actor = Path(args.actor).resolve()
    candidate = Path(args.candidate).resolve()
    decision = load_json(Path(args.decision))
    if decision.get("accepted") is not True:
        raise FlowError("candidate decision is not accepted")
    current_fp = hash_dir(actor)
    candidate_fp = hash_dir(candidate)
    baseline_fp = decision.get("baseline_fingerprint")
    if candidate_fp != decision.get("candidate_fingerprint"):
        raise FlowError("candidate directory changed after Oracle comparison")
    backup = Path(args.backup).resolve()
    if current_fp == candidate_fp:
        if backup.exists() and hash_dir(backup) != baseline_fp:
            raise FlowError("candidate is already promoted but backup does not match baseline")
        print(json.dumps({
            "accepted": True,
            "already_committed": True,
            "actor": str(actor),
            "backup": str(backup),
            "fingerprint": current_fp,
        }, ensure_ascii=False))
        return
    if current_fp != baseline_fp:
        raise FlowError(
            f"official actor skills changed after baseline snapshot: {current_fp} != {baseline_fp}"
        )
    if backup.exists():
        if hash_dir(backup) != baseline_fp:
            raise FlowError(f"existing backup does not match baseline: {backup}")
    else:
        backup.parent.mkdir(parents=True, exist_ok=True)
        copytree_clean(actor, backup)
    actor.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{actor.name}.promote-", dir=str(actor.parent)))
    staged = temp_dir / actor.name
    try:
        shutil.copytree(candidate, staged)
        old = actor.with_name(actor.name + ".old")
        if old.exists():
            shutil.rmtree(old)
        if actor.exists():
            os.replace(actor, old)
        os.replace(staged, actor)
        if old.exists():
            shutil.rmtree(old)
    except Exception:
        if not actor.exists() and backup.exists():
            shutil.copytree(backup, actor)
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    print(json.dumps({
        "accepted": True,
        "actor": str(actor),
        "backup": str(backup),
        "fingerprint": hash_dir(actor),
    }, ensure_ascii=False))


def cmd_report(args: argparse.Namespace) -> None:
    rows = load_jsonl(Path(args.metrics))
    calibration: Dict[str, int] = {}
    review_verdicts: Dict[str, int] = {"PASS": 0, "REVISE": 0, "ABSTAIN": 0}
    totals = {
        "rounds": len(rows),
        "accepted": 0,
        "scored_pairs": 0,
        "improvement": 0,
        "regression": 0,
        "retained_pass": 0,
        "unresolved_fail": 0,
        "net_gain": 0,
        "gd_revisions": 0,
    }
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        verdict = str(row.get("review_verdict", ""))
        if verdict in review_verdicts:
            review_verdicts[verdict] += 1
        cal = str(row.get("review_calibration", "unknown"))
        calibration[cal] = calibration.get(cal, 0) + 1
        counts = row.get("counts") or {}
        accepted = bool(row.get("accepted"))
        totals["accepted"] += int(accepted)
        totals["scored_pairs"] += int(row.get("scored_pairs") or 0)
        totals["gd_revisions"] += int(row.get("gd_revisions") or 0)
        for key in ("improvement", "regression", "retained_pass", "unresolved_fail"):
            totals[key] += int(counts.get(key) or 0)
        totals["net_gain"] += int(row.get("net_gain") or 0)
        normalized.append({
            "round": row.get("round"),
            "candidate_version": row.get("candidate_version"),
            "review_verdict": verdict,
            "review_calibration": cal,
            "gd_revisions": row.get("gd_revisions", 0),
            "scored_pairs": row.get("scored_pairs", 0),
            "improvement": counts.get("improvement", 0),
            "regression": counts.get("regression", 0),
            "retained_pass": counts.get("retained_pass", 0),
            "unresolved_fail": counts.get("unresolved_fail", 0),
            "net_gain": row.get("net_gain", 0),
            "accepted": accepted,
            "baseline_pass_rate": row.get("baseline_pass_rate"),
            "candidate_pass_rate": row.get("candidate_pass_rate"),
        })
    totals["accept_rate"] = _safe_rate(totals["accepted"], totals["rounds"])
    totals["mean_gd_revisions"] = _safe_rate(totals["gd_revisions"], totals["rounds"])
    report = {
        "schema_version": 1,
        "totals": totals,
        "review_verdicts": review_verdicts,
        "review_calibration": dict(sorted(calibration.items())),
        "rounds": normalized,
    }
    if args.out_json:
        dump_json(Path(args.out_json), report)
    if args.out_md:
        lines = [
            "# VeriSkill candidate evolution report",
            "",
            f"- rounds: {totals['rounds']}",
            f"- accepted: {totals['accepted']} (rate={totals['accept_rate']})",
            f"- scored pairs: {totals['scored_pairs']}",
            f"- improvement / regression / net gain: {totals['improvement']} / {totals['regression']} / {totals['net_gain']}",
            f"- mean G-D revisions: {totals['mean_gd_revisions']}",
            "",
            "## Per round",
            "",
            "| round | candidate | D | calibration | revisions | scored | improve | regress | retained | unresolved | net | accepted |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for row in normalized:
            lines.append(
                f"| {row['round']} | {row['candidate_version']} | {row['review_verdict']} | "
                f"{row['review_calibration']} | {row['gd_revisions']} | {row['scored_pairs']} | "
                f"{row['improvement']} | {row['regression']} | {row['retained_pass']} | "
                f"{row['unresolved_fail']} | {row['net_gain']} | {str(row['accepted']).lower()} |"
            )
        lines.extend(["", "## D review calibration", ""])
        for key, value in sorted(calibration.items()):
            lines.append(f"- {key}: {value}")
        Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fingerprint")
    p.add_argument("--skills-dir", required=True)
    p.set_defaults(func=lambda a: print(hash_dir(Path(a.skills_dir))))

    p = sub.add_parser("prepare")
    p.add_argument("--actor", required=True)
    p.add_argument("--round-dir", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("clone-iteration")
    p.add_argument("--round-dir", required=True)
    p.add_argument("--from-iter", type=int, required=True)
    p.add_argument("--to-iter", type=int, required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_clone_iteration)

    p = sub.add_parser("validate-manifest")
    p.add_argument("--manifest", required=True)
    p.add_argument("--batch", required=True)
    p.add_argument("--candidate-dir", required=True)
    p.add_argument("--base-fingerprint")
    p.add_argument("--out")
    p.add_argument("--state")
    p.set_defaults(func=cmd_validate_manifest)

    p = sub.add_parser("validate-review")
    p.add_argument("--review", required=True)
    p.add_argument("--batch", required=True)
    p.add_argument("--candidate-fingerprint")
    p.add_argument("--out")
    p.set_defaults(func=cmd_validate_review)

    p = sub.add_parser("build-oracle-queue")
    p.add_argument("--batch", required=True)
    p.add_argument("--review", required=True)
    p.add_argument("--checker-dir", required=True)
    p.add_argument("--truth-dir", required=True)
    p.add_argument("--budget", type=int, required=True)
    p.add_argument("--revise-audit", type=int, default=1)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_build_oracle_queue)

    p = sub.add_parser("compare")
    p.add_argument("--review", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--baseline-dir", required=True)
    p.add_argument("--candidate-dir", required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--candidate-version", required=True)
    p.add_argument("--gd-revisions", type=int, default=0)
    p.add_argument("--min-scored", type=int, default=2)
    p.add_argument("--min-improvements", type=int, default=1)
    p.add_argument("--max-regressions", type=int, default=0)
    p.add_argument("--out-comparison", required=True)
    p.add_argument("--out-decision", required=True)
    p.add_argument("--out-to-d", required=True)
    p.add_argument("--out-to-g", required=True)
    p.add_argument("--out-to-d-raw")
    p.add_argument("--out-to-g-raw")
    p.add_argument("--metrics")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("commit")
    p.add_argument("--actor", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--decision", required=True)
    p.add_argument("--backup", required=True)
    p.set_defaults(func=cmd_commit)

    p = sub.add_parser("report")
    p.add_argument("--metrics", required=True)
    p.add_argument("--out-json")
    p.add_argument("--out-md")
    p.set_defaults(func=cmd_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except (FlowError, OSError, ValueError) as exc:
        print(f"candidate_flow: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
