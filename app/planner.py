"""Minimal local daily planner."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

try:
    from app import memory_bridge, status_summary
except ModuleNotFoundError:
    import memory_bridge  # type: ignore
    import status_summary  # type: ignore


DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "today_input.json"
TIME_BLOCKS = [
    "10:00-11:30",
    "14:00-15:30",
    "15:30-17:00",
    "19:00-20:30",
    "20:30-21:30",
]
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}
UNCERTAINTY_RANK = {"high": 0, "medium": 1, "low": 2}


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _task_name(task: dict) -> str:
    return str(task.get("task_name") or task.get("title") or "未命名任务").strip()


def _duration_minutes(task: dict) -> int:
    raw = task.get("estimated_duration_minutes", task.get("estimated_duration"))
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


def _parse_deadline(value: object) -> tuple[int, str]:
    if value is None:
        return (1, "9999-12-31")
    text = str(value).strip()
    if not text:
        return (1, "9999-12-31")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return (0, parsed.strftime("%Y-%m-%d %H:%M:%S"))
        except ValueError:
            continue
    return (1, text)


def _project_key(task: dict) -> str:
    return str(task.get("project") or "").strip().lower()


def _time_to_minutes(value: str) -> int:
    try:
        hour_text, minute_text = value.split(":", 1)
        return int(hour_text) * 60 + int(minute_text)
    except (TypeError, ValueError):
        return 24 * 60


def _block_end_minutes(block: str) -> int:
    if "-" not in block:
        return 24 * 60
    return _time_to_minutes(block.split("-", 1)[1])


def _normalize_time_blocks(peak_sessions: object) -> list[str]:
    if isinstance(peak_sessions, list):
        blocks = [str(item).strip() for item in peak_sessions if str(item).strip()]
        if blocks:
            return blocks
    return TIME_BLOCKS


def _get_user_preferences(user_memory: dict) -> tuple[int, list[str], str]:
    preferences = user_memory.get("preferences", {}) if isinstance(user_memory, dict) else {}
    work_rhythm = user_memory.get("work_rhythm", {}) if isinstance(user_memory, dict) else {}

    max_tasks_raw = preferences.get("max_core_tasks_per_day", 3) if isinstance(preferences, dict) else 3
    try:
        max_tasks = max(int(max_tasks_raw), 1)
    except (TypeError, ValueError):
        max_tasks = 3

    peak_sessions = work_rhythm.get("peak_sessions") if isinstance(work_rhythm, dict) else None
    avoid_heavy_after = work_rhythm.get("avoid_heavy_after", "21:30") if isinstance(work_rhythm, dict) else "21:30"
    return max_tasks, _normalize_time_blocks(peak_sessions), str(avoid_heavy_after or "21:30")


def _build_project_record(task: dict) -> dict | None:
    project_name = str(task.get("project") or "").strip()
    if not project_name:
        return None
    return {
        "project_name": project_name,
        "project_stage": str(task.get("project_stage") or "").strip(),
        "latest_result": str(task.get("current_progress") or "").strip(),
        "next_step": "",
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


def load_input(path: Path) -> dict:
    """Load planner input JSON with a safe fallback."""
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def task_sort_key(task: dict) -> tuple:
    """Sort by priority, uncertainty and execution risk."""
    priority = PRIORITY_RANK.get(str(task.get("priority", "P2")).upper(), 9)
    uncertainty = UNCERTAINTY_RANK.get(str(task.get("uncertainty_level", "low")).lower(), 9)
    deadline = _parse_deadline(task.get("deadline"))
    return (
        priority,
        uncertainty,
        0 if _bool_value(task.get("need_authoritative_web_search")) else 1,
        deadline,
        0 if _bool_value(task.get("external_dependency")) else 1,
        0 if _bool_value(task.get("first_time_doing")) else 1,
    )


def select_top_tasks(tasks: list[dict], max_tasks: int = 3) -> list[dict]:
    """Select at most max_tasks core tasks."""
    sorted_tasks = sorted(
        [task for task in tasks if isinstance(task, dict)],
        key=task_sort_key,
    )
    return sorted_tasks[: max(max_tasks, 1)]


def assign_time_blocks(
    tasks: list[dict],
    peak_sessions: list[str] | None = None,
    avoid_heavy_after: str = "21:30",
) -> list[dict]:
    """Assign tasks into preferred time blocks."""
    time_blocks = _normalize_time_blocks(peak_sessions)
    avoid_minutes = _time_to_minutes(avoid_heavy_after)
    deep_blocks = [block for block in time_blocks if _block_end_minutes(block) <= avoid_minutes]
    light_blocks = time_blocks[1:] or time_blocks
    deep_tasks = [task for task in tasks if _bool_value(task.get("need_deep_thinking"))]
    light_tasks = [task for task in tasks if not _bool_value(task.get("need_deep_thinking"))]
    assignments: list[dict] = []
    used_blocks: set[str] = set()

    for task in deep_tasks:
        for block in deep_blocks or time_blocks:
            if block not in used_blocks and _block_end_minutes(block) <= avoid_minutes:
                assignments.append({"time_block": block, "task": task})
                used_blocks.add(block)
                break

    short_tasks = sorted(light_tasks, key=lambda item: (_duration_minutes(item) > 45, task_sort_key(item)))
    for task in short_tasks:
        preferred_blocks = light_blocks if _duration_minutes(task) <= 45 else time_blocks
        for block in preferred_blocks:
            if block not in used_blocks:
                assignments.append({"time_block": block, "task": task})
                used_blocks.add(block)
                break

    block_order = {block: index for index, block in enumerate(time_blocks)}
    assignments.sort(key=lambda item: block_order.get(item["time_block"], 999))
    return assignments


def suggest_delays(all_tasks: list[dict], selected_tasks: list[dict]) -> list[str]:
    """Return brief suggestions for non-core tasks."""
    selected_ids = {id(task) for task in selected_tasks}
    remaining = [task for task in all_tasks if isinstance(task, dict) and id(task) not in selected_ids]
    suggestions: list[str] = []
    seen_projects: set[str] = set()

    for task in sorted(remaining, key=task_sort_key)[:5]:
        name = _task_name(task)
        project = _project_key(task)
        if project and project in seen_projects:
            suggestions.append(f"{name} 可与同类任务合并处理")
        else:
            suggestions.append(f"{name} 建议延后到明天")
        if project:
            seen_projects.add(project)
    return suggestions


def build_reminders(projects: list[dict], tasks: list[dict]) -> list[str]:
    """Build concise progress/change reminders."""
    reminders: list[str] = []
    reminders.extend(status_summary.summarize_projects(projects)[:3])
    reminders.extend(status_summary.summarize_major_changes(projects)[:2])
    reminders.extend(status_summary.summarize_blockers(projects)[:2])
    reminders.extend(status_summary.summarize_recent_progress(tasks)[:3])
    return reminders[:8]


def print_report(top_tasks: list[dict], blocks: list[dict], delays: list[str], reminders: list[str]) -> None:
    """Print the final planner output."""
    print("今日 Top 3")
    if top_tasks:
        for index, task in enumerate(top_tasks, start=1):
            print(f"{index}. {_task_name(task)}")
    else:
        print("1. 暂无核心任务")

    print("\n时间块安排")
    if blocks:
        for item in blocks:
            print(f"- {item['time_block']}：{_task_name(item['task'])}")
    else:
        print("- 暂无安排")

    print("\n延期建议")
    if delays:
        for line in delays:
            print(f"- {line}")
    else:
        print("- 暂无")

    print("\n进度/变更提醒")
    if reminders:
        for line in reminders:
            print(f"- {line}")
    else:
        print("- 暂无")


def main() -> None:
    """Planner entrypoint."""
    memory_bridge.normalize_data_files()

    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    payload = load_input(input_path)
    tasks = payload.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    input_date = str(payload.get("date") or date.today().isoformat())
    user_memory = memory_bridge.get_user_memory()
    project_memory = memory_bridge.get_project_memory()
    task_log = memory_bridge.get_task_log()
    max_tasks, peak_sessions, avoid_heavy_after = _get_user_preferences(user_memory)

    sorted_tasks = sorted([task for task in tasks if isinstance(task, dict)], key=task_sort_key)
    top_tasks = select_top_tasks(sorted_tasks, max_tasks=max_tasks)
    blocks = assign_time_blocks(top_tasks, peak_sessions=peak_sessions, avoid_heavy_after=avoid_heavy_after)
    delays = suggest_delays(sorted_tasks, top_tasks)
    reminders = build_reminders(project_memory, task_log)

    print_report(top_tasks, blocks, delays, reminders)

    for task in tasks:
        if not isinstance(task, dict):
            continue
        if not str(task.get("task_name") or task.get("title") or "").strip():
            continue

        task_record = dict(task)
        task_record["date"] = str(task_record.get("date") or input_date)
        memory_bridge.append_task_log_if_new(task_record)

        project_record = _build_project_record(task_record)
        if project_record:
            memory_bridge.upsert_project_memory(project_record)


if __name__ == "__main__":
    main()
