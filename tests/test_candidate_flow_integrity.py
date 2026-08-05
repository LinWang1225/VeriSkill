import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "lib" / "candidate_flow.py"
sys.path.insert(0, str(ROOT / "lib"))
from fingerprint import hash_dir  # noqa: E402


class CandidateFlowIntegrityTests(unittest.TestCase):
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
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_validate_manifest_refreshes_candidate_state(self):
        round_dir = self.root / "rounds" / "r1"
        candidate = round_dir / "candidate" / "iter0"
        candidate.mkdir(parents=True)
        (candidate / "g-demo.md").write_text("candidate\n", encoding="utf-8")
        state = round_dir / "candidate_state.json"
        self.write_json(state, {
            "baseline_fingerprint": "base",
            "candidate_fingerprint": "stale",
            "candidate_dir": str(candidate),
            "status": "prepared",
        })
        batch = round_dir / "current_batch.list"
        batch.write_text("q1\n", encoding="utf-8")
        manifest = round_dir / "manifests" / "iter0.json"
        self.write_json(manifest, {
            "candidate_version": "r1-i0",
            "base_fingerprint": "base",
            "trajectory_clusters": [],
            "changes": [],
            "expected_coverage": {"q1": ["g-demo#step"]},
            "uncovered": [],
            "response_to_d": [],
        })
        self.run_cli(
            "validate-manifest",
            "--manifest", manifest,
            "--batch", batch,
            "--candidate-dir", candidate,
            "--base-fingerprint", "base",
            "--state", state,
        )
        updated = json.loads(state.read_text())
        self.assertEqual(updated["candidate_fingerprint"], hash_dir(candidate))
        self.assertEqual(updated["status"], "g_validated")
        self.assertTrue(updated["manifest_hash"])

    def test_compare_marks_wrong_oracle_fingerprint_inconclusive(self):
        baseline_dir = self.root / "baseline"
        candidate_dir = self.root / "candidate"
        baseline_dir.mkdir()
        candidate_dir.mkdir()
        (baseline_dir / "skill.md").write_text("base\n", encoding="utf-8")
        (candidate_dir / "skill.md").write_text("candidate\n", encoding="utf-8")
        review = self.root / "review.json"
        self.write_json(review, {"verdict": "PASS"})
        baseline = self.root / "baseline.jsonl"
        candidate = self.root / "candidate.jsonl"
        self.write_jsonl(baseline, [{
            "item": "q1", "oracle_pass": False, "truth_source": "checker", "skill_hash": "wrong"
        }])
        self.write_jsonl(candidate, [{
            "item": "q1", "oracle_pass": True, "truth_source": "checker", "skill_hash": hash_dir(candidate_dir)
        }])
        decision = self.root / "decision.json"
        to_d = self.root / "to_d.jsonl"
        to_g = self.root / "to_g.jsonl"
        self.run_cli(
            "compare",
            "--review", review,
            "--baseline", baseline,
            "--candidate", candidate,
            "--baseline-dir", baseline_dir,
            "--candidate-dir", candidate_dir,
            "--round", 1,
            "--candidate-version", "r1-i0",
            "--min-scored", 1,
            "--min-improvements", 1,
            "--max-regressions", 0,
            "--out-comparison", self.root / "comparison.jsonl",
            "--out-decision", decision,
            "--out-to-d", to_d,
            "--out-to-g", to_g,
        )
        result = json.loads(decision.read_text())
        self.assertEqual(result["decision_status"], "inconclusive")
        self.assertFalse(result["accepted"])
        self.assertEqual(to_g.read_text(), "")

    def test_compare_writes_sanitized_feedback_and_optional_raw_files(self):
        baseline_dir = self.root / "baseline"
        candidate_dir = self.root / "candidate"
        baseline_dir.mkdir()
        candidate_dir.mkdir()
        (baseline_dir / "skill.md").write_text("base\n", encoding="utf-8")
        (candidate_dir / "skill.md").write_text("candidate\n", encoding="utf-8")
        review = self.root / "review.json"
        self.write_json(review, {"verdict": "PASS"})
        baseline = self.root / "baseline.jsonl"
        candidate = self.root / "candidate.jsonl"
        self.write_jsonl(baseline, [{
            "item": "q063", "oracle_pass": False, "truth_source": "checker",
            "skill_hash": hash_dir(baseline_dir), "skill_result": "wrong"
        }])
        self.write_jsonl(candidate, [{
            "item": "q063", "oracle_pass": True, "truth_source": "checker",
            "skill_hash": hash_dir(candidate_dir), "skill_result": "gold=44.00"
        }])
        to_d = self.root / "to_d.jsonl"
        to_g = self.root / "to_g.jsonl"
        raw_d = self.root / "to_d.raw.jsonl"
        raw_g = self.root / "to_g.raw.jsonl"
        self.run_cli(
            "compare",
            "--review", review,
            "--baseline", baseline,
            "--candidate", candidate,
            "--baseline-dir", baseline_dir,
            "--candidate-dir", candidate_dir,
            "--round", 1,
            "--candidate-version", "r1-i0",
            "--min-scored", 1,
            "--min-improvements", 1,
            "--max-regressions", 0,
            "--out-comparison", self.root / "comparison.jsonl",
            "--out-decision", self.root / "decision.json",
            "--out-to-d", to_d,
            "--out-to-g", to_g,
            "--out-to-d-raw", raw_d,
            "--out-to-g-raw", raw_g,
        )
        sanitized = to_d.read_text()
        self.assertIn("case-001", sanitized)
        self.assertNotIn("q063", sanitized)
        self.assertNotIn("44.00", sanitized)
        self.assertIn("q063", raw_d.read_text())
        self.assertIn("q063", raw_g.read_text())


if __name__ == "__main__":
    unittest.main()
