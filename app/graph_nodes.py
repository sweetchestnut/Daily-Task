"""LangGraph nodes for the planner flow."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

try:
    from app import memory_bridge, planner
    from app import task_extractor
    from app.graph_state import PlannerState
except ModuleNotFoundError:
    import memory_bridge  # type: ignore
    import planner  # type: ignore
    import task_extractor  # type: ignore
    from graph_state import PlannerState  # type: ignore


def load_input_node(state: PlannerState) -> PlannerState:
    payload = state.get("raw_input") or {}
    warnings = list(state.get("warnings", []))
    if isinstance(payload, str):
        payload = {"text_input": payload, "date": date.today().isoformat()}
    elif not isinstance(payload, dict):
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
    text_input = str(today_input.get("text_input") or "").strip() if isinstance(today_input, dict) else ""
    warnings = list(state.get("warnings", []))
    if text_input:
        extracted = task_extractor.extract_tasks(text_input, input_date=str(today_input.get("date") or date.today().isoformat()))
        if not extracted:
            warnings.append("未能从自然语言中提取任务。")
    elif not isinstance(tasks, list):
        warnings.append("tasks 字段不是列表，已忽略。")
        extracted = []
    else:
        extracted = []
        for task in tasks if isinstance(tasks, list) else []:
            if not isinstance(task, dict):
                continue
            normalized = task_extractor.normalize_task_item(
                task,
                input_date=str(today_input.get("date") or date.today().isoformat()),
            )
            if normalized:
                extracted.append(normalized)
    return {
        "extracted_tasks": extracted,
        "editable_tasks": deepcopy(extracted),
        "review_required": True,
        "approved": False,
        "warnings": warnings,
    }


def rank_tasks_node(state: PlannerState) -> PlannerState:
    tasks = list(state.get("editable_tasks") or state.get("extracted_tasks", []))
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
    extracted_tasks = list(state.get("extracted_tasks", []))
    return {
        "reminders": reminders,
        "warnings": warnings,
        "approved": bool(state.get("approved", False)),
        "editable_tasks": list(state.get("editable_tasks", extracted_tasks)),
        "review_required": bool(state.get("review_required", False)) and not bool(state.get("approved", False)),
    }


def save_results_node(state: PlannerState) -> PlannerState:
    if not state.get("approved", False):
        return {}
    today_input = state.get("today_input") or {}
    tasks = list(state.get("editable_tasks") or state.get("extracted_tasks", []))
    input_date = str(today_input.get("date") or date.today().isoformat())

    normalized_tasks: list[dict[str, Any]] = []
    for task in tasks:
        normalized_task = task_extractor.normalize_task_item(task, input_date) if isinstance(task, dict) else None
        if not normalized_task:
            continue
        normalized_tasks.append(normalized_task)
        memory_bridge.append_task_log_if_new(dict(normalized_task))

    for project_record in planner._build_project_records(normalized_tasks, input_date):
        memory_bridge.upsert_project_memory(project_record)

    project_memory = memory_bridge.get_project_memory()
    task_log = memory_bridge.get_task_log()
    reminders = planner.build_reminders(project_memory, task_log)
    return {
        "editable_tasks": normalized_tasks,
        "extracted_tasks": normalized_tasks,
        "project_memory": project_memory,
        "task_log": task_log,
        "reminders": reminders,
    }
