import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from fingerprint import hash_dir  # noqa: E402
from sanitize_feedback import lint_tree, sanitize_records  # noqa: E402


def load_make_checkers():
    path = ROOT / "adapters" / "make_checkers.py"
    spec = importlib.util.spec_from_file_location("make_checkers", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FingerprintTests(unittest.TestCase):
    def test_same_contents_different_absolute_paths_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "left"
            right = root / "nested" / "right"
            for directory in (left, right):
                (directory / "sub").mkdir(parents=True)
                (directory / "sub" / "skill.md").write_text("same\n", encoding="utf-8")
            self.assertEqual(hash_dir(left), hash_dir(right))

    def test_relative_name_and_mode_are_part_of_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (first / "a.md").write_text("same\n", encoding="utf-8")
            (second / "b.md").write_text("same\n", encoding="utf-8")
            self.assertNotEqual(hash_dir(first), hash_dir(second))
            (second / "b.md").rename(second / "a.md")
            self.assertEqual(hash_dir(first), hash_dir(second))
            os.chmod(second / "a.md", os.stat(second / "a.md").st_mode | stat.S_IXUSR)
            self.assertNotEqual(hash_dir(first), hash_dir(second))

    def test_transient_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skill.md").write_text("content\n", encoding="utf-8")
            before = hash_dir(root)
            (root / "scratch.tmp").write_text("noise\n", encoding="utf-8")
            (root / ".DS_Store").write_text("noise\n", encoding="utf-8")
            self.assertEqual(before, hash_dir(root))


class SanitizerTests(unittest.TestCase):
    def test_feedback_replaces_item_ids_and_drops_answers(self):
        rows = [
            {
                "record_type": "candidate_summary",
                "round": 3,
                "candidate_version": "r3-i1",
                "counts": {"regression": 1},
                "accepted": False,
            },
            {
                "record_type": "item",
                "item": "q063",
                "kind": "unresolved_fail",
                "baseline_pass": False,
                "candidate_pass": False,
                "truth_source": "checker",
                "baseline_result": "[41.74, 239.09]",
                "candidate_result": "[44.00, 231.52]",
                "candidate_evidence": "checker: score_answer pred=[44.00,231.52] gold=[44.00,231.52]",
            },
        ]
        sanitized = sanitize_records(rows, "g")
        encoded = json.dumps(sanitized, ensure_ascii=False)
        self.assertIn("case-001", encoded)
        self.assertNotIn("q063", encoded)
        self.assertNotIn("44.00", encoded)
        self.assertNotIn("gold", encoded.lower())
        self.assertIn("semantic_answer_check", encoded)

    def test_g_memory_keeps_improvement_regression_and_unresolved_only(self):
        rows = [
            {"record_type": "item", "item": "q1", "kind": "retained_pass"},
            {"record_type": "item", "item": "q2", "kind": "improvement"},
            {"record_type": "item", "item": "q3", "kind": "regression"},
        ]
        sanitized = sanitize_records(rows, "g")
        self.assertEqual([row["kind"] for row in sanitized], ["improvement", "regression"])

    def test_lint_tree_rejects_ids_and_gold_pred_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            critics = root / "critics"
            critics.mkdir()
            meta = root / "meta.json"
            meta.write_text(json.dumps({"items": [{"id": "q063"}]}), encoding="utf-8")
            (critics / "rule.md").write_text("针对 q063，gold=44.00。\n", encoding="utf-8")
            violations = lint_tree(critics, meta)
            self.assertTrue(any("q063" in violation for violation in violations))
            self.assertTrue(any("gold/pred" in violation for violation in violations))


class GeneratedCheckerTests(unittest.TestCase):
    def run_checker(self, gold, pred, official_score=0.0):
        module = load_make_checkers()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "golds.json").write_text(json.dumps({"q": gold}), encoding="utf-8")
            (root / "run_officeqa.py").write_text(
                f"def score_answer(gold, pred):\n    return {official_score!r}\n",
                encoding="utf-8",
            )
            checker = root / "checker_core.py"
            checker.write_text(module.CORE, encoding="utf-8")
            traj = root / "traj.md"
            traj.write_text(f"## 题目\nX\n\n## 最终答案\n{pred}\n", encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(checker), "q", str(traj)],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

    def test_numeric_list_spacing_is_semantically_equal(self):
        proc = self.run_checker("[44.00,231.52]", "[44.00, 231.52]")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("route=numeric-fallback", proc.stdout)

    def test_numeric_list_integer_first_element_no_space(self):
        # 逗号在列表里是分隔符不是千分位：首元素为无小数点的大整数时，
        # "10102000000,4.73" 不能被当成一个数 101020000004.73。
        proc = self.run_checker("[10102000000, 4.73]", "[10102000000,4.73]")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("route=numeric-fallback", proc.stdout)

    def test_numeric_scalar_can_have_explanation(self):
        proc = self.run_checker("11.60", "11.60 million dollars")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_different_numeric_list_still_fails(self):
        proc = self.run_checker("[44.00,231.52]", "[44.00, 231.53]")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_scalar_fallback_does_not_scan_explanatory_numbers(self):
        proc = self.run_checker("1945", "In 1945 the computed answer is 11.60")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_official_score_remains_authoritative_for_non_numeric_answers(self):
        proc = self.run_checker("yes", "equivalent prose", official_score=1.0)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("route=official", proc.stdout)


if __name__ == "__main__":
    unittest.main()
