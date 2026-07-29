#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tc = load("trajectory_checks", ROOT / "lib" / "trajectory_checks.py")
rr = load("result_report", ROOT / "lib" / "result_report.py")


class TrajectoryChecksTests(unittest.TestCase):
    def test_visible_geometric_mean_contradiction_is_hard_error(self):
        text = """---
skill_hash: abc
---
## 题目
Compute the geometric mean and report in millions.
## 激活技能
- g-calc
## 过程
ln(GM) = 691.76 / 80 = 8.64705
GM = e^8.64705 = 5155.8362
## 最终答案
5155.84
"""
        result = tc.analyze_text(text)
        codes = {issue["code"] for issue in result["hard_errors"]}
        self.assertIn("ARITH_EXP", codes)

    def test_opaque_aggregate_is_warning_not_failure(self):
        text = """---
skill_hash: abc
---
## 题目
Use all monthly values.
## 激活技能
- g-extract
## 过程
共80个月，关键来源举例：1942年3月、1942年4月。全部80个值均验证。
## 最终答案
10
"""
        result = tc.analyze_text(text)
        self.assertFalse(result["hard_errors"])
        self.assertIn("EVIDENCE_AGGREGATE_OPAQUE", {x["code"] for x in result["warnings"]})

    def test_hard_check_can_emit_verdict_without_model(self):
        checks = {
            "hard_errors": [{"code": "ARITH_EXP", "message": "visible contradiction"}],
            "warnings": [],
        }
        verdict = tc.verdict_from_checks("q", checks)
        self.assertEqual(verdict["verdict"], "fail")
        self.assertEqual(verdict["model_verdict"], "not_run")
        self.assertTrue(verdict["static_override"])
        self.assertGreaterEqual(verdict["confidence"], 0.95)

    def test_warning_caps_confidence_but_does_not_flip_pass(self):
        verdict = {"item": "x", "verdict": "pass", "confidence": 0.9, "reason": "ok"}
        checks = {"hard_errors": [], "warnings": [{"code": "OPAQUE", "message": "x"}]}
        merged = tc.merge_verdict(verdict, checks)
        self.assertEqual(merged["verdict"], "pass")
        self.assertEqual(merged["audit_priority"], "high")
        self.assertLessEqual(merged["confidence"], 0.45)


class ResultReportTests(unittest.TestCase):
    def test_json_array_is_reported_as_invalid_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "audit.jsonl"
            path.write_text('[{"item":"x"}]', encoding="utf-8")
            parsed = rr.read_jsonl(path)
            self.assertTrue(parsed.array_instead_of_jsonl)
            self.assertTrue(parsed.errors)

    def test_legacy_audits_are_excluded_from_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            round_dir = root / "rounds" / "r1"
            round_dir.mkdir(parents=True)
            (round_dir / "verdicts.jsonl").write_text(
                json.dumps({"item": "a", "verdict": "fail"}) + "\n", encoding="utf-8"
            )
            rows = [
                {"item": "a", "kind": "FP", "same_sample": False, "oracle_pass": True},
                {"item": "b", "kind": "TN", "same_sample": True, "oracle_pass": True},
            ]
            (round_dir / "audit.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            summary, errors = rr.summarize_round(1, round_dir)
            self.assertFalse(errors)
            self.assertEqual(summary["legacy_or_misaligned_rows"], 1)
            self.assertEqual(summary["d_metrics"]["counts"]["FP"], 0)
            self.assertEqual(summary["d_metrics"]["counts"]["TN"], 1)

    def test_final_test_is_reported_separately(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            final = root / "rounds" / "final_test"
            final.mkdir(parents=True)
            (final / "summary.json").write_text(json.dumps({
                "n_sampled": 2, "n_oracle_judged": 2, "g_success_rate": 0.5
            }), encoding="utf-8")
            audit = [
                {"item": "a", "kind": "TP", "same_sample": True},
                {"item": "b", "kind": "TN", "same_sample": True},
            ]
            (final / "audit.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in audit), encoding="utf-8"
            )
            report, errors = rr.build_report(root)
            self.assertFalse(errors)
            self.assertEqual(report["final_test"]["summary"]["g_success_rate"], 0.5)
            self.assertEqual(report["final_test"]["d_metrics"]["balanced_accuracy"], 1.0)

    def test_full_report_writes_same_sample_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pool" / "traj.full").mkdir(parents=True)
            (root / "pool" / "traj.full" / "q.md").write_text(
                "---\nskill_hash: h\n---\n## 题目\nQ\n## 激活技能\n- g\n## 过程\n1+1=2\n## 最终答案\n2\n",
                encoding="utf-8",
            )
            round_dir = root / "rounds" / "r2"
            round_dir.mkdir(parents=True)
            audit = [
                {"item": "a", "kind": "TP", "same_sample": True, "oracle_pass": False},
                {"item": "b", "kind": "TN", "same_sample": True, "oracle_pass": True},
            ]
            (round_dir / "audit.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in audit), encoding="utf-8"
            )
            report, errors = rr.build_report(root)
            self.assertFalse(errors)
            self.assertEqual(report["overall_d_metrics"]["balanced_accuracy"], 1.0)
            self.assertEqual(report["trajectories"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
