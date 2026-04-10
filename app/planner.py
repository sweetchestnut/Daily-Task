"""Minimal local daily planner."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

try:
    from app import memory_bridge, status_summary
    from app import task_extractor
except ModuleNotFoundError:
    import memory_bridge  # type: ignore
    import status_summary  # type: ignore
    import task_extractor  # type: ignore


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
    raw = task.get("duration_minutes", task.get("estimated_duration_minutes", task.get("estimated_duration")))
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        return 30
    return max(30, minutes)


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
        return 0


def _minutes_to_time(value: int) -> str:
    hour = value // 60
    minute = value % 60
    return f"{hour:02d}:{minute:02d}"


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


def _expand_time_blocks(peak_sessions: object) -> list[str]:
    slots: list[str] = []
    for block in _normalize_time_blocks(peak_sessions):
        if "-" not in block:
            continue
        start_text, end_text = block.split("-", 1)
        start_minutes = _time_to_minutes(start_text)
        end_minutes = _time_to_minutes(end_text)
        while start_minutes + 30 <= end_minutes:
            slots.append(f"{_minutes_to_time(start_minutes)}-{_minutes_to_time(start_minutes + 30)}")
            start_minutes += 30
    return slots


def _merge_slots(slots: list[str]) -> str:
    if not slots:
        return ""
    first = slots[0].split("-", 1)[0]
    last = slots[-1].split("-", 1)[1]
    return f"{first}-{last}"


def _dedupe_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if line and line not in seen:
            seen.add(line)
            result.append(line)
    return result


def _split_text_tasks(text: str) -> list[str]:
    normalized = re.sub(r"[，。；\n]+", "，", str(text).strip())
    normalized = normalized.replace("然后", "，").replace("再", "，").replace("最后", "，")
    normalized = normalized.replace("晚上", "，").replace("下午", "，").replace("上午", "，")
    return [part.strip(" ，") for part in normalized.split("，") if part.strip(" ，")]


def _guess_project(task_name: str) -> str:
    lowered = task_name.lower()
    if "streamlit" in lowered:
        return "Streamlit"
    if "langgraph" in lowered or "graph" in lowered:
        return "LangGraph"
    if "daily-task" in lowered or "记忆" in task_name or "memory" in lowered:
        return "Daily-Task"
    return ""


def _guess_duration(task_name: str) -> int:
    lowered = task_name.lower()
    if "检查" in task_name or "看一下" in task_name or "check" in lowered:
        return 30
    if "跑起来" in task_name or "整理" in task_name or "补" in task_name:
        return 60
    return 30


def _guess_priority(task_name: str) -> str:
    lowered = task_name.lower()
    if "先" in task_name or "streamlit" in lowered or "langgraph" in lowered:
        return "P0"
    if "最后" in task_name:
        return "P2"
    return "P1"


def _guess_need_deep_work(task_name: str) -> bool:
    lowered = task_name.lower()
    keywords = ("整理", "检查", "设计", "graph", "langgraph", "streamlit")
    return any(keyword in task_name or keyword in lowered for keyword in keywords)


def extract_tasks_from_text(text: str, input_date: str | None = None) -> list[dict]:
    """Extract tasks from free-form text with simple rules."""
    tasks: list[dict] = []
    for chunk in _split_text_tasks(text):
        uncertainty_flags: list[str] = []
        project = _guess_project(chunk)
        priority = _guess_priority(chunk)
        duration_minutes = _guess_duration(chunk)
        need_deep_work = _guess_need_deep_work(chunk)
        if not project:
            uncertainty_flags.append("project_inferred_missing")
        if priority == "P1":
            uncertainty_flags.append("priority_defaulted")
        if duration_minutes == 30:
            uncertainty_flags.append("duration_defaulted")
        tasks.append(
            {
                "task_name": chunk,
                "priority": priority,
                "duration_minutes": duration_minutes,
                "estimated_duration": duration_minutes,
                "project": project,
                "need_deep_work": need_deep_work,
                "need_deep_thinking": need_deep_work,
                "uncertainty_flags": uncertainty_flags,
                "uncertainty_level": "high" if uncertainty_flags else "medium",
                "date": input_date or date.today().isoformat(),
            }
        )
    return tasks


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


def _build_project_records(tasks: list[dict], input_date: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for task in tasks:
        project_name = str(task.get("project") or "").strip()
        if not project_name:
            continue
        group = grouped.setdefault(project_name, {"stages": [], "results": []})
        stage = str(task.get("project_stage") or "").strip()
        result = str(task.get("current_progress") or "").strip()
        if stage and stage not in group["stages"]:
            group["stages"].append(stage)
        if result and result not in group["results"]:
            group["results"].append(result)

    records: list[dict] = []
    for project_name, group in grouped.items():
        records.append(
            {
                "project_name": project_name,
                "project_stage": group["stages"][-1] if group["stages"] else "",
                "latest_result": "；".join(group["results"][:3]),
                "next_step": "",
                "last_updated": f"{input_date}T{datetime.now().strftime('%H:%M:%S')}",
            }
        )
    return records


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
    sorted_tasks = sorted([task for task in tasks if isinstance(task, dict)], key=task_sort_key)
    return sorted_tasks[: max(max_tasks, 1)]


def assign_time_blocks(
    tasks: list[dict],
    peak_sessions: list[str] | None = None,
    avoid_heavy_after: str = "21:30",
) -> list[dict]:
    """Assign tasks into 30-minute slots, then merge contiguous slots for output."""
    slots = _expand_time_blocks(peak_sessions or TIME_BLOCKS)
    avoid_minutes = _time_to_minutes(avoid_heavy_after)
    deep_tasks = [task for task in tasks if _bool_value(task.get("need_deep_thinking"))]
    light_tasks = [task for task in tasks if not _bool_value(task.get("need_deep_thinking"))]
    ordered_tasks = deep_tasks + light_tasks
    assignments: list[dict] = []
    used_indexes: set[int] = set()

    for task in ordered_tasks:
        needed_slots = max(1, (_duration_minutes(task) + 29) // 30)
        is_deep = _bool_value(task.get("need_deep_thinking"))
        for start in range(0, len(slots) - needed_slots + 1):
            indexes = list(range(start, start + needed_slots))
            if any(index in used_indexes for index in indexes):
                continue
            candidate_slots = [slots[index] for index in indexes]
            if is_deep and _block_end_minutes(candidate_slots[-1]) > avoid_minutes:
                continue
            used_indexes.update(indexes)
            assignments.append({"time_block": _merge_slots(candidate_slots), "task": task})
            break

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
    return _dedupe_lines(reminders)[:8]


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


def run_planner(payload: dict | None = None) -> dict:
    """Run the planner and return structured output for CLI or graph use."""
    memory_bridge.normalize_data_files()

    payload = payload if isinstance(payload, dict) else {}
    input_date = str(payload.get("date") or date.today().isoformat())
    text_input = str(payload.get("text_input") or "").strip()
    tasks = payload.get("tasks", [])
    if text_input:
        tasks = task_extractor.extract_tasks(text_input, input_date=input_date)
    elif not isinstance(tasks, list):
        tasks = []

    user_memory = memory_bridge.get_user_memory()
    max_tasks, peak_sessions, avoid_heavy_after = _get_user_preferences(user_memory)

    cleaned_tasks = [task for task in tasks if isinstance(task, dict)]
    sorted_tasks = sorted(cleaned_tasks, key=task_sort_key)
    top_tasks = select_top_tasks(sorted_tasks, max_tasks=max_tasks)
    blocks = assign_time_blocks(top_tasks, peak_sessions=peak_sessions, avoid_heavy_after=avoid_heavy_after)
    delays = suggest_delays(sorted_tasks, top_tasks)

    for task in cleaned_tasks:
        if not str(task.get("task_name") or task.get("title") or "").strip():
            continue
        task_record = dict(task)
        task_record["date"] = str(task_record.get("date") or input_date)
        memory_bridge.append_task_log_if_new(task_record)

    for project_record in _build_project_records(cleaned_tasks, input_date):
        memory_bridge.upsert_project_memory(project_record)

    refreshed_projects = memory_bridge.get_project_memory()
    refreshed_task_log = memory_bridge.get_task_log()
    reminders = build_reminders(refreshed_projects, refreshed_task_log)

    return {
        "raw_input": payload,
        "input_date": input_date,
        "tasks": cleaned_tasks,
        "sorted_tasks": sorted_tasks,
        "top_tasks": top_tasks,
        "blocks": blocks,
        "delays": delays,
        "reminders": reminders,
        "user_memory": user_memory,
        "project_memory": refreshed_projects,
        "task_log": refreshed_task_log,
    }


def main() -> None:
    """Planner entrypoint."""
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    payload = load_input(input_path)
    result = run_planner(payload)
    print_report(result["top_tasks"], result["blocks"], result["delays"], result["reminders"])


if __name__ == "__main__":
    main()
