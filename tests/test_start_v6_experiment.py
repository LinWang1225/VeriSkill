import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "start_v6_experiment.py"


class StartV6ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "pool").mkdir(parents=True)
        (self.root / "pool" / "traj").mkdir()
        (self.root / "pool" / "traj.full").mkdir()
        (self.root / "pool" / "traj_orig").mkdir()
        (self.root / "pool" / "traj" / "q1.md").write_text("mutated trajectory\n", encoding="utf-8")
        (self.root / "pool" / "traj.full" / "q1.md").write_text("mutated full\n", encoding="utf-8")
        (self.root / "pool" / "traj_orig" / "q1.md").write_text("original trajectory\n", encoding="utf-8")
        (self.root / "workspace" / "actor_skills").mkdir(parents=True)
        (self.root / "workspace" / "critics").mkdir(parents=True)
        (self.root / "workspace" / "actor_skills" / "g-old.md").write_text("old g\n", encoding="utf-8")
        (self.root / "workspace" / "critics" / "d-old.md").write_text("old d\n", encoding="utf-8")
        meta = {
            "items": [
                {"id": "q1", "split": "train", "used_count": 3, "g_version": 4},
                {"id": "q2", "split": "test", "used_count": 2, "g_version": 4},
            ]
        }
        (self.root / "pool" / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (self.root / "rounds").mkdir()
        (self.root / "rounds" / "old.txt").write_text("old\n", encoding="utf-8")
        (self.root / "stats").mkdir()
        (self.root / "ledger.json").write_text('{"round": 12}\n', encoding="utf-8")
        (self.root / "report.md").write_text("old report\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, check=True):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and proc.returncode != 0:
            self.fail(f"command failed: {proc.stderr}\n{proc.stdout}")
        return proc

    def test_dry_run_does_not_modify_state(self):
        proc = self.run_cli("--label", "before_v6")
        result = json.loads(proc.stdout)
        self.assertFalse(result["applied"])
        self.assertTrue((self.root / "rounds" / "old.txt").exists())
        self.assertEqual(json.loads((self.root / "ledger.json").read_text())["round"], 12)
        self.assertFalse((self.root / "archive" / "before_v6").exists())

    def test_apply_archives_old_run_and_cold_starts(self):
        proc = self.run_cli("--label", "before_v6", "--apply")
        result = json.loads(proc.stdout)
        self.assertTrue(result["applied"])
        archive = self.root / "archive" / "before_v6"
        self.assertTrue((archive / "rounds" / "old.txt").exists())
        self.assertTrue((archive / "workspace" / "actor_skills" / "g-old.md").exists())
        self.assertTrue((archive / "workspace" / "critics" / "d-old.md").exists())
        self.assertEqual((archive / "pool" / "traj_before_v6" / "q1.md").read_text(), "mutated trajectory\n")
        self.assertEqual((self.root / "pool" / "traj" / "q1.md").read_text(), "original trajectory\n")
        self.assertEqual((self.root / "pool" / "traj.full" / "q1.md").read_text(), "original trajectory\n")
        self.assertEqual(list((self.root / "workspace" / "actor_skills").iterdir()), [])
        self.assertEqual(list((self.root / "workspace" / "critics").iterdir()), [])
        meta = json.loads((self.root / "pool" / "meta.json").read_text())
        self.assertEqual([x["used_count"] for x in meta["items"]], [0, 0])
        self.assertEqual([x["g_version"] for x in meta["items"]], [0, 0])
        ledger = json.loads((self.root / "ledger.json").read_text())
        self.assertEqual(ledger["flow_version"], 6)
        self.assertEqual(ledger["round"], 0)
        self.assertTrue((self.root / "stats" / "candidate_eval.jsonl").exists())
        self.assertIn("VeriSkill v6 experiment", (self.root / "report.md").read_text())

    def test_preserve_actor_warm_start(self):
        self.run_cli("--label", "warm", "--apply", "--preserve-actor")
        self.assertTrue((self.root / "workspace" / "actor_skills" / "g-old.md").exists())
        self.assertFalse((self.root / "workspace" / "critics" / "d-old.md").exists())
        self.assertFalse((self.root / "archive" / "warm" / "workspace" / "actor_skills").exists())
        self.assertTrue((self.root / "archive" / "warm" / "workspace" / "critics" / "d-old.md").exists())


if __name__ == "__main__":
    unittest.main()
