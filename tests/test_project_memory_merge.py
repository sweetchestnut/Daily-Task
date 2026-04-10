import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import planner


class ProjectMemoryMergeTest(unittest.TestCase):
    def test_same_project_results_are_merged(self):
        tasks = [
            {"project": "Daily-Task", "project_stage": "Executing", "current_progress": "代码骨架已完成"},
            {"project": "Daily-Task", "project_stage": "Executing", "current_progress": "记忆初始化待写入"},
        ]
        records = planner._build_project_records(tasks, "2026-04-10")
        self.assertEqual(len(records), 1)
        self.assertIn("代码骨架已完成", records[0]["latest_result"])
        self.assertIn("记忆初始化待写入", records[0]["latest_result"])


if __name__ == "__main__":
    unittest.main()
