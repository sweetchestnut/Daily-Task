import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import memory_bridge
from app.graph_flow import run_extract_flow, run_graph, run_schedule_flow


class GraphFlowSmokeTest(unittest.TestCase):
    def test_graph_flow_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            user = base / "user_memory.json"
            project = base / "project_memory.json"
            task_log = base / "task_log.json"
            memory_bridge.save_json(str(user), {})
            memory_bridge.save_json(str(project), [])
            memory_bridge.save_json(str(task_log), [])
            with mock.patch.object(memory_bridge, "USER_MEMORY_PATH", user), mock.patch.object(
                memory_bridge, "PROJECT_MEMORY_PATH", project
            ), mock.patch.object(memory_bridge, "TASK_LOG_PATH", task_log):
                state = run_graph({"date": "2026-04-10", "text_input": "先整理 Daily-Task，再补记忆"})
        self.assertIn("extracted_tasks", state)
        self.assertIn("ranked_tasks", state)
        self.assertIn("scheduled_tasks", state)
        self.assertIn("reminders", state)

    def test_extract_flow_stops_before_scheduling(self):
        state = run_extract_flow({"date": "2026-04-10", "text_input": "先整理 Daily-Task，再补记忆"})
        self.assertIn("extracted_tasks", state)
        self.assertNotIn("ranked_tasks", state)
        self.assertTrue(state.get("review_required"))
        self.assertFalse(state.get("approved"))

    def test_schedule_flow_requires_approval(self):
        state = run_extract_flow({"date": "2026-04-10", "text_input": "先整理 Daily-Task，再补记忆"})
        result = run_schedule_flow(state)
        self.assertNotIn("ranked_tasks", result)
        self.assertTrue(result.get("review_required"))


if __name__ == "__main__":
    unittest.main()
