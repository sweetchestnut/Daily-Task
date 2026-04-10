"""State schema for the planner graph."""

from __future__ import annotations

from typing import Any

try:
    from typing import TypedDict
except ImportError:
    try:
        from typing_extensions import TypedDict  # type: ignore
    except ImportError:
        class PlannerState(dict):  # type: ignore[no-redef]
            pass
    else:
        class PlannerState(TypedDict, total=False):
            raw_input: dict[str, Any]
            today_input: dict[str, Any]
            extracted_tasks: list[dict[str, Any]]
            ranked_tasks: list[dict[str, Any]]
            scheduled_tasks: list[dict[str, Any]]
            user_memory: dict[str, Any]
            project_memory: list[dict[str, Any]]
            task_log: list[dict[str, Any]]
            reminders: list[str]
            warnings: list[str]
            approved: bool
            delays: list[str]
else:
    class PlannerState(TypedDict, total=False):
        raw_input: dict[str, Any]
        today_input: dict[str, Any]
        extracted_tasks: list[dict[str, Any]]
        ranked_tasks: list[dict[str, Any]]
        scheduled_tasks: list[dict[str, Any]]
        user_memory: dict[str, Any]
        project_memory: list[dict[str, Any]]
        task_log: list[dict[str, Any]]
        reminders: list[str]
        warnings: list[str]
        approved: bool
        delays: list[str]
