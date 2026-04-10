import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import planner, task_extractor


class TextTaskExtractionTest(unittest.TestCase):
    def test_extract_multiple_tasks_from_text(self):
        text = "今天先把 Streamlit 页面跑起来，再检查 LangGraph 节点流，晚上补项目记忆初始数据"
        tasks = planner.extract_tasks_from_text(text, input_date="2026-04-10")
        self.assertGreaterEqual(len(tasks), 3)
        self.assertTrue(all(task.get("task_name") for task in tasks))

    def test_default_fields_are_filled(self):
        tasks = planner.extract_tasks_from_text("看一下 graph 输出", input_date="2026-04-10")
        task = tasks[0]
        self.assertEqual(task["duration_minutes"], 30)
        self.assertIn(task["priority"], {"P0", "P1", "P2"})
        self.assertIn("uncertainty_flags", task)

    def test_llm_result_is_normalized(self):
        llm_items = [
            {
                "task_name": "修正提取逻辑",
                "priority": "bad-priority",
                "project": "Daily-Task",
                "need_deep_work": True,
            },
            {
                "priority": "P0",
                "duration_minutes": 90,
            },
        ]
        tasks = task_extractor.extract_tasks(
            "修正提取逻辑",
            input_date="2026-04-10",
            llm_json_loader=lambda _text: llm_items,
        )
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_name"], "修正提取逻辑")
        self.assertEqual(tasks[0]["priority"], "P1")
        self.assertEqual(tasks[0]["duration_minutes"], 30)
        self.assertEqual(tasks[0]["uncertainty_flags"], [])

    def test_llm_parse_failure_falls_back_to_rules(self):
        with mock.patch.object(task_extractor, "_rule_extract_tasks", return_value=[{"task_name": "规则兜底任务"}]):
            tasks = task_extractor.extract_tasks(
                "整理任务",
                input_date="2026-04-10",
                llm_json_loader=lambda _text: (_ for _ in ()).throw(ValueError("bad json")),
            )
        self.assertEqual(tasks, [{"task_name": "规则兜底任务"}])


if __name__ == "__main__":
    unittest.main()
