"""LangGraph nodes for the planner flow."""

from __future__ import annotations

from datetime import date

try:
    from app import memory_bridge, planner
    from app.graph_state import PlannerState
except ModuleNotFoundError:
    import memory_bridge  # type: ignore
    import planner  # type: ignore
    from graph_state import PlannerState  # type: ignore


def load_input_node(state: PlannerState) -> PlannerState:
    payload = state.get("raw_input") or {}
    warnings = list(state.get("warnings", []))
    if not isinstance(payload, dict):
        warnings.append("输入格式无效，已回退为空。")
        payload = {}
    return {"today_input": payload, "warnings": warnings}


def load_memory_node(state: PlannerState) -> PlannerState:
    memory_bridge.normalize_data_files()
    return {
        "user_memory": memory_bridge.get_user_memory(),
        "project_memory": memory_bridge.get_project_memory(),
        "task_log": memory_bridge.get_task_log(),
    }


def extract_today_tasks_node(state: PlannerState) -> PlannerState:
    today_input = state.get("today_input") or {}
    tasks = today_input.get("tasks", []) if isinstance(today_input, dict) else []
    warnings = list(state.get("warnings", []))
    if not isinstance(tasks, list):
        warnings.append("tasks 字段不是列表，已忽略。")
        tasks = []
    extracted = [task for task in tasks if isinstance(task, dict)]
    return {"extracted_tasks": extracted, "warnings": warnings}


def rank_tasks_node(state: PlannerState) -> PlannerState:
    tasks = list(state.get("extracted_tasks", []))
    ranked = sorted(tasks, key=planner.task_sort_key)
    return {"ranked_tasks": ranked}


def schedule_tasks_node(state: PlannerState) -> PlannerState:
    user_memory = state.get("user_memory", {})
    max_tasks, peak_sessions, avoid_heavy_after = planner._get_user_preferences(user_memory)
    ranked = list(state.get("ranked_tasks", []))
    top_tasks = planner.select_top_tasks(ranked, max_tasks=max_tasks)
    scheduled = planner.assign_time_blocks(top_tasks, peak_sessions=peak_sessions, avoid_heavy_after=avoid_heavy_after)
    delays = planner.suggest_delays(ranked, top_tasks)
    return {"ranked_tasks": top_tasks, "scheduled_tasks": scheduled, "delays": delays}


def review_node(state: PlannerState) -> PlannerState:
    reminders = planner.build_reminders(
        list(state.get("project_memory", [])),
        list(state.get("task_log", [])),
    )
    warnings = planner._dedupe_lines(list(state.get("warnings", [])))
    return {"reminders": reminders, "warnings": warnings, "approved": True}


def save_results_node(state: PlannerState) -> PlannerState:
    today_input = state.get("today_input") or {}
    tasks = list(state.get("extracted_tasks", []))
    input_date = str(today_input.get("date") or date.today().isoformat())

    for task in tasks:
        if not str(task.get("task_name") or task.get("title") or "").strip():
            continue
        task_record = dict(task)
        task_record["date"] = str(task_record.get("date") or input_date)
        memory_bridge.append_task_log_if_new(task_record)

    for project_record in planner._build_project_records(tasks, input_date):
        memory_bridge.upsert_project_memory(project_record)

    project_memory = memory_bridge.get_project_memory()
    task_log = memory_bridge.get_task_log()
    reminders = planner.build_reminders(project_memory, task_log)
    return {"project_memory": project_memory, "task_log": task_log, "reminders": reminders}
