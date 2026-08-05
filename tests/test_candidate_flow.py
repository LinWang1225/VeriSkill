import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from fingerprint import hash_dir  # noqa: E402

SCRIPT = ROOT / "lib" / "candidate_flow.py"


class CandidateFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, check=True):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and proc.returncode != 0:
            self.fail(f"command failed ({proc.returncode}): {proc.stderr}\n{proc.stdout}")
        return proc

    @staticmethod
    def write_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def write_jsonl(path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

    def test_prepare_and_clone_keep_official_untouched(self):
        actor = self.root / "workspace" / "actor_skills"
        actor.mkdir(parents=True)
        (actor / "g-demo.md").write_text("baseline\n", encoding="utf-8")
        round_dir = self.root / "rounds" / "r1"

        self.run_cli("prepare", "--actor", actor, "--round-dir", round_dir)
        resumed = self.run_cli("prepare", "--actor", actor, "--round-dir", round_dir)
        self.assertTrue(json.loads(resumed.stdout)["resumed"])
        candidate0 = round_dir / "candidate" / "iter0"
        (candidate0 / "g-demo.md").write_text("candidate\n", encoding="utf-8")
        self.assertEqual((actor / "g-demo.md").read_text(), "baseline\n")

        self.run_cli(
            "clone-iteration", "--round-dir", round_dir,
            "--from-iter", 0, "--to-iter", 1,
        )
        self.assertEqual((round_dir / "candidate" / "iter1" / "g-demo.md").read_text(), "candidate\n")
        self.assertEqual((actor / "g-demo.md").read_text(), "baseline\n")

    def test_manifest_requires_every_batch_item_once(self):
        batch = self.root / "batch.list"
        batch.write_text("q1\nq2\n", encoding="utf-8")
        candidate = self.root / "candidate"
        candidate.mkdir()
        manifest = self.root / "manifest.json"
        self.write_json(manifest, {
            "candidate_version": "r1-i0",
            "base_fingerprint": "abc",
            "trajectory_clusters": [],
            "changes": [],
            "expected_coverage": {"q1": ["g-a#step"]},
            "uncovered": [],
            "response_to_d": [],
        })
        proc = self.run_cli(
            "validate-manifest", "--manifest", manifest, "--batch", batch,
            "--candidate-dir", candidate, "--base-fingerprint", "abc",
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("omits current_batch", proc.stderr)

        data = json.loads(manifest.read_text())
        data["uncovered"] = ["q2"]
        self.write_json(manifest, data)
        self.run_cli(
            "validate-manifest", "--manifest", manifest, "--batch", batch,
            "--candidate-dir", candidate, "--base-fingerprint", "abc",
        )

    def test_review_requires_actionable_revise_and_full_coverage(self):
        batch = self.root / "batch.list"
        batch.write_text("q1\nq2\n", encoding="utf-8")
        review = self.root / "review.json"
        self.write_json(review, {
            "mode": "review_candidate",
            "candidate_fingerprint": "fp",
            "verdict": "REVISE",
            "confidence": 0.9,
            "coverage": [
                {"item": "q1", "status": "uncovered"},
                {"item": "q2", "status": "covered"},
            ],
            "hard_defects": [],
            "soft_concerns": [],
            "feedback_to_g": [],
        })
        proc = self.run_cli(
            "validate-review", "--review", review, "--batch", batch,
            "--candidate-fingerprint", "fp", check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("REVISE requires", proc.stderr)

        data = json.loads(review.read_text())
        data["feedback_to_g"] = [{"feedback_id": "F1", "message": "cover q1"}]
        self.write_json(review, data)
        self.run_cli(
            "validate-review", "--review", review, "--batch", batch,
            "--candidate-fingerprint", "fp",
        )

    def test_oracle_queue_excludes_unscored_and_audits_revise(self):
        batch = self.root / "batch.list"
        batch.write_text("q1\nq2\nq3\n", encoding="utf-8")
        checkers = self.root / "checkers"
        truth = self.root / "truth"
        checkers.mkdir()
        truth.mkdir()
        (checkers / "q1.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (truth / "q2.md").write_text("truth\n", encoding="utf-8")
        review = self.root / "review.json"
        self.write_json(review, {
            "verdict": "REVISE",
            "coverage": [
                {"item": "q1", "status": "covered"},
                {"item": "q2", "status": "uncovered"},
                {"item": "q3", "status": "unjudgeable"},
            ],
        })
        out = self.root / "queue.jsonl"
        self.run_cli(
            "build-oracle-queue", "--batch", batch, "--review", review,
            "--checker-dir", checkers, "--truth-dir", truth,
            "--budget", 3, "--revise-audit", 1, "--round", 7, "--out", out,
        )
        rows = [json.loads(x) for x in out.read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item"], "q2")
        self.assertEqual(rows[0]["reason"], "revise_audit")

    def make_compare_inputs(self, verdict="PASS", candidate_second=True):
        baseline_dir = self.root / "baseline"
        candidate_dir = self.root / "candidate"
        baseline_dir.mkdir(exist_ok=True)
        candidate_dir.mkdir(exist_ok=True)
        (baseline_dir / "skill.md").write_text("base\n", encoding="utf-8")
        (candidate_dir / "skill.md").write_text("candidate\n", encoding="utf-8")
        review = self.root / "review.json"
        self.write_json(review, {"verdict": verdict})
        baseline = self.root / "baseline.jsonl"
        candidate = self.root / "candidate.jsonl"
        baseline_hash = hash_dir(baseline_dir)
        candidate_hash = hash_dir(candidate_dir)
        self.write_jsonl(baseline, [
            {"item": "q1", "oracle_pass": False, "truth_source": "checker", "skill_hash": baseline_hash},
            {"item": "q2", "oracle_pass": True, "truth_source": "checker", "skill_hash": baseline_hash},
        ])
        self.write_jsonl(candidate, [
            {"item": "q1", "oracle_pass": True, "truth_source": "checker", "skill_hash": candidate_hash},
            {"item": "q2", "oracle_pass": candidate_second, "truth_source": "checker", "skill_hash": candidate_hash},
        ])
        return review, baseline, candidate, baseline_dir, candidate_dir

    def run_compare(self, verdict="PASS", candidate_second=True):
        review, baseline, candidate, baseline_dir, candidate_dir = self.make_compare_inputs(verdict, candidate_second)
        decision = self.root / "decision.json"
        metrics = self.root / "metrics.jsonl"
        self.run_cli(
            "compare",
            "--review", review, "--baseline", baseline, "--candidate", candidate,
            "--baseline-dir", baseline_dir, "--candidate-dir", candidate_dir,
            "--round", 1, "--candidate-version", "r1-i0", "--gd-revisions", 1,
            "--min-scored", 2, "--min-improvements", 1, "--max-regressions", 0,
            "--out-comparison", self.root / "comparison.jsonl",
            "--out-decision", decision,
            "--out-to-d", self.root / "to_d.jsonl",
            "--out-to-g", self.root / "to_g.jsonl",
            "--metrics", metrics,
        )
        return json.loads(decision.read_text()), baseline_dir, candidate_dir, metrics

    def test_compare_accepts_real_improvement_without_regression(self):
        decision, _, _, _ = self.run_compare("PASS", True)
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["counts"]["improvement"], 1)
        self.assertEqual(decision["counts"]["regression"], 0)
        self.assertEqual(decision["review_calibration"], "correct_accept")
        self.assertEqual(decision["gd_revisions"], 1)
        # Re-running compare replaces the same round/candidate metric instead of duplicating it.
        self.run_compare("PASS", True)
        metrics = self.root / "metrics.jsonl"
        self.assertEqual(len([x for x in metrics.read_text().splitlines() if x.strip()]), 1)

    def test_compare_rejects_regression(self):
        decision, _, _, _ = self.run_compare("PASS", False)
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["counts"]["regression"], 1)
        self.assertEqual(decision["review_calibration"], "false_accept")

    def test_revise_is_calibration_only_even_with_improvement(self):
        decision, _, _, _ = self.run_compare("REVISE", True)
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["review_calibration"], "false_reject_evidence")

    def test_commit_promotes_only_frozen_accepted_candidate(self):
        decision, baseline_dir, candidate_dir, _ = self.run_compare("PASS", True)
        actor = self.root / "actor"
        actor.mkdir()
        (actor / "skill.md").write_text("base\n", encoding="utf-8")
        decision_path = self.root / "decision.json"
        # The compare baseline fingerprint comes from baseline_dir, which has the same contents.
        backup = self.root / "history" / "before"
        self.run_cli(
            "commit", "--actor", actor, "--candidate", candidate_dir,
            "--decision", decision_path, "--backup", backup,
        )
        self.assertEqual((actor / "skill.md").read_text(), "candidate\n")
        self.assertEqual((backup / "skill.md").read_text(), "base\n")
        again = self.run_cli(
            "commit", "--actor", actor, "--candidate", candidate_dir,
            "--decision", decision_path, "--backup", backup,
        )
        self.assertTrue(json.loads(again.stdout)["already_committed"])

    def test_report_aggregates_candidate_and_d_metrics(self):
        _, _, _, metrics = self.run_compare("PASS", True)
        out_json = self.root / "report.json"
        out_md = self.root / "report.md"
        self.run_cli(
            "report", "--metrics", metrics,
            "--out-json", out_json, "--out-md", out_md,
        )
        report = json.loads(out_json.read_text())
        self.assertEqual(report["totals"]["accepted"], 1)
        self.assertEqual(report["totals"]["improvement"], 1)
        self.assertEqual(report["review_calibration"]["correct_accept"], 1)
        self.assertIn("Per round", out_md.read_text())


if __name__ == "__main__":
    unittest.main()
