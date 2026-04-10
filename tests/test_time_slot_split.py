import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import planner


class TimeSlotSplitTest(unittest.TestCase):
    def test_peak_sessions_split_into_30_min_slots(self):
        slots = planner._expand_time_blocks(["14:00-17:00"])
        self.assertEqual(slots[0], "14:00-14:30")
        self.assertEqual(slots[-1], "16:30-17:00")
        self.assertEqual(len(slots), 6)

    def test_30_min_task_does_not_take_full_session(self):
        tasks = [{"task_name": "检查 graph 输出", "duration_minutes": 30, "need_deep_thinking": False}]
        result = planner.assign_time_blocks(tasks, peak_sessions=["14:00-17:00"])
        self.assertEqual(result[0]["time_block"], "14:00-14:30")


if __name__ == "__main__":
    unittest.main()
