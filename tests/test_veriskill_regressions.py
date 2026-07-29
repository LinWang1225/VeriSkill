#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


jsonx = load_module("veriskill_jsonx", ROOT / "lib" / "jsonx.py")


class JsonxRegressionTests(unittest.TestCase):
    def test_independent_fail_without_rubric_is_not_inferred_hard(self):
        out = jsonx.build_verdict(
            {
                "verdict": "fail",
                "critic_verdict": "not_applicable",
                "independent_verdict": "fail",
                "hard_rule_hit": False,
                "rubric_scores": {},
                "normalized_score": None,
                "evidence_coverage": 0.6,
                "reason": "独立核查发现疑点",
            },
            "x",
            0.6,
        )
        self.assertFalse(out["hard_rule_hit"])
        self.assertEqual(out["verdict"], "pass")
        self.assertTrue(out["verdict_corrected"])
        self.assertLessEqual(out["confidence"], 0.5)

    def test_direct_independent_error_can_fail_without_critic(self):
        out = jsonx.build_verdict(
            {
                "verdict": "fail",
                "critic_verdict": "not_applicable",
                "independent_verdict": "fail",
                "independent_direct_error": True,
                "evidence_coverage": 0.9,
                "rubric_scores": {},
            },
            "x",
            0.6,
        )
        self.assertEqual(out["verdict"], "fail")

    def test_disagreement_is_forced_into_audit_band(self):
        out = jsonx.build_verdict(
            {
                "verdict": "pass",
                "critic_verdict": "fail",
                "independent_verdict": "pass",
                "rubric_scores": {"r": 0},
                "normalized_score": 0.0,
                "evidence_coverage": 1.0,
                "disagreement": True,
            },
            "x",
            0.6,
        )
        self.assertTrue(out["disagreement"])
        self.assertLessEqual(out["confidence"], 0.35)


class PoolRegressionTests(unittest.TestCase):
    def run_queue(self, verdicts, checker_ids, budget=4):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            verdict_path = d / "verdicts.jsonl"
            verdict_path.write_text(
                "".join(json.dumps(v) + "\n" for v in verdicts), encoding="utf-8"
            )
            audited = d / "audited.json"
            audited.write_text("[]", encoding="utf-8")
            checkers = d / "checkers"
            truth = d / "truth"
            checkers.mkdir()
            truth.mkdir()
            for item in checker_ids:
                p = checkers / f"{item}.sh"
                p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                p.chmod(0o755)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "lib" / "pool.py"),
                    "audit-queue",
                    "--verdicts",
                    str(verdict_path),
                    "--audited",
                    str(audited),
                    "--fingerprint",
                    "abc",
                    "--budget",
                    str(budget),
                    "--round",
                    "7",
                    "--checker-dir",
                    str(checkers),
                    "--truth-dir",
                    str(truth),
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def test_queue_covers_all_four_risk_segments(self):
        verdicts = []
        for i, confidence in enumerate((0.1, 0.3, 0.8, 0.95)):
            verdicts.append({"item": f"f{i}", "verdict": "fail", "confidence": confidence})
            verdicts.append({"item": f"p{i}", "verdict": "pass", "confidence": confidence})
        rows = self.run_queue(verdicts, {v["item"] for v in verdicts}, budget=4)
        self.assertEqual(
            {r["segment"] for r in rows},
            {"fail-low", "fail-high", "pass-low", "pass-random"},
        )

    def test_items_without_checker_or_truth_are_not_audited(self):
        verdicts = [
            {"item": "scored", "verdict": "pass", "confidence": 0.2},
            {"item": "unscored", "verdict": "fail", "confidence": 0.2},
        ]
        rows = self.run_queue(verdicts, {"scored"}, budget=2)
        self.assertEqual([r["item"] for r in rows], ["scored"])


if __name__ == "__main__":
    unittest.main()
