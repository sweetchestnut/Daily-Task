"""Short status summary helpers."""

from __future__ import annotations


def _clean_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _task_name(task: dict) -> str:
    return _clean_text(task.get("task_name") or task.get("title"))


def summarize_projects(projects: list[dict]) -> list[str]:
    """Return short project summaries."""
    lines: list[str] = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        name = _clean_text(project.get("project_name") or project.get("project"))
        if not name:
            continue

        parts: list[str] = []
        stage = _clean_text(project.get("project_stage") or project.get("stage"))
        if stage:
            parts.append(stage)
        latest_result = _clean_text(project.get("latest_result"))
        if latest_result:
            parts.append(f"阶段结果 {latest_result}")
        next_step = _clean_text(project.get("next_step"))
        if next_step:
            parts.append(f"下一步 {next_step}")
        if parts:
            lines.append(f"{name}：" + "；".join(parts))
    return lines


def summarize_major_changes(projects: list[dict]) -> list[str]:
    """Return short major-change reminders."""
    lines: list[str] = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        name = _clean_text(project.get("project_name") or project.get("project"))
        change = _clean_text(project.get("last_major_change"))
        if name and change:
            lines.append(f"{name} 有较大修改：{change}")
    return lines


def summarize_blockers(projects: list[dict]) -> list[str]:
    """Return short blocker summaries."""
    lines: list[str] = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        name = _clean_text(project.get("project_name") or project.get("project"))
        blockers = project.get("blockers")
        if isinstance(blockers, list):
            blocker_text = "；".join(_clean_text(item) for item in blockers if _clean_text(item))
        else:
            blocker_text = _clean_text(blockers)
        if name and blocker_text:
            lines.append(f"{name} 阻塞：{blocker_text}")
    return lines


def summarize_recent_progress(tasks: list[dict]) -> list[str]:
    """Return up to 5 recent progress notes."""
    lines: list[str] = []
    for task in reversed(tasks):
        if not isinstance(task, dict):
            continue
        name = _task_name(task)
        progress = _clean_text(task.get("current_progress"))
        if name and progress:
            lines.append(f"{name}：{progress}")
        if len(lines) >= 5:
            break
    return lines
