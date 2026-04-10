import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import memory_bridge


class TaskLogDedupeTest(unittest.TestCase):
    def test_duplicate_task_log_is_deduped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "task_log.json"
            memory_bridge.save_json(
                str(tmp_path),
                [
                    {"date": "2026-04-10", "project": "Daily-Task", "task_name": "整理 Daily-Task"},
                    {"date": "2026-04-10", "project": "Daily-Task", "task_name": "整理 Daily-Task"},
                ],
            )
            with mock.patch.object(memory_bridge, "TASK_LOG_PATH", tmp_path):
                items = memory_bridge.get_task_log()
            self.assertEqual(len(items), 1)


if __name__ == "__main__":
    unittest.main()
