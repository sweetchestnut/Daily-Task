<<<<<<< HEAD
"""Local JSON memory bridge for the planner."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
USER_MEMORY_PATH = DATA_DIR / "user_memory.json"
PROJECT_MEMORY_PATH = DATA_DIR / "project_memory.json"
TASK_LOG_PATH = DATA_DIR / "task_log.json"


def load_json(path: str, default: object) -> object:
    """Load JSON and fall back to default on missing/invalid data."""
    file_path = Path(path)
    try:
        if not file_path.exists():
            return default
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: str, data: object) -> None:
    """Save JSON with UTF-8 and indentation."""
    file_path = Path(path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except OSError:
        return


def normalize_data_files() -> None:
    """Normalize initial data files into expected container types."""
    user_memory = load_json(str(USER_MEMORY_PATH), {})
    project_memory = load_json(str(PROJECT_MEMORY_PATH), [])
    task_log = load_json(str(TASK_LOG_PATH), [])

    if not isinstance(user_memory, dict):
        save_json(str(USER_MEMORY_PATH), {})
    if not isinstance(project_memory, list):
        save_json(str(PROJECT_MEMORY_PATH), [])
    if not isinstance(task_log, list):
        save_json(str(TASK_LOG_PATH), [])


def get_user_memory() -> dict:
    """Return user long-term memory."""
    data = load_json(str(USER_MEMORY_PATH), {})
    return data if isinstance(data, dict) else {}


def get_project_memory() -> list[dict]:
    """Return project memory list."""
    data = load_json(str(PROJECT_MEMORY_PATH), [])
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def get_task_log() -> list[dict]:
    """Return task log list."""
    data = load_json(str(TASK_LOG_PATH), [])
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def append_task_log(task: dict) -> None:
    """Append one task log record with last_updated timestamp."""
    if not isinstance(task, dict):
        return
    task_log = get_task_log()
    record = dict(task)
    record["last_updated"] = datetime.now().isoformat(timespec="seconds")
    task_log.append(record)
    save_json(str(TASK_LOG_PATH), task_log)


def append_task_log_if_new(task: dict) -> None:
    """Append only when same task/project/day does not already exist."""
    if not isinstance(task, dict):
        return

    task_name = str(task.get("task_name") or task.get("title") or "").strip()
    project_name = str(task.get("project") or "").strip()
    task_date = str(task.get("date") or datetime.now().date().isoformat()).strip()
    if not task_name:
        return

    for item in get_task_log():
        existing_name = str(item.get("task_name") or item.get("title") or "").strip()
        existing_project = str(item.get("project") or "").strip()
        existing_date = str(item.get("date") or "").strip()
        if existing_name == task_name and existing_project == project_name and existing_date == task_date:
            return

    record = dict(task)
    if not record.get("date"):
        record["date"] = task_date
    append_task_log(record)


def upsert_project_memory(project_record: dict) -> None:
    """Update or insert a project record by project_name."""
    if not isinstance(project_record, dict):
        return
    project_name = str(project_record.get("project_name", "")).strip()
    if not project_name:
        return

    projects = get_project_memory()
    updated = False
    for index, item in enumerate(projects):
        if str(item.get("project_name", "")).strip() == project_name:
            projects[index] = {**item, **project_record}
            updated = True
            break
    if not updated:
        projects.append(project_record)
    save_json(str(PROJECT_MEMORY_PATH), projects)


def save_user_memory(memory: dict) -> None:
    """Save user long-term memory."""
    if not isinstance(memory, dict):
        return
    save_json(str(USER_MEMORY_PATH), memory)
=======

>>>>>>> 4004b40d2e87f9beb5876d2b4dc9f9baa8352807
