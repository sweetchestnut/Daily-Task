"""Task extraction with LLM-first and rule-based fallback."""

from __future__ import annotations

import json
import os
from typing import Any, Callable


VALID_PRIORITIES = {"P0", "P1", "P2"}
DEFAULT_DURATION_MINUTES = 30


def normalize_task_item(item: dict[str, Any], input_date: str) -> dict[str, Any] | None:
    """Validate and normalize one extracted task."""
    if not isinstance(item, dict):
        return None
    task_name = str(item.get("task_name") or item.get("title") or "").strip()
    if not task_name:
        return None

    priority = str(item.get("priority") or "P1").upper()
    if priority not in VALID_PRIORITIES:
        priority = "P1"

    try:
        duration_minutes = int(item.get("duration_minutes", item.get("estimated_duration", DEFAULT_DURATION_MINUTES)))
    except (TypeError, ValueError):
        duration_minutes = DEFAULT_DURATION_MINUTES
    duration_minutes = max(DEFAULT_DURATION_MINUTES, duration_minutes)

    uncertainty_flags = item.get("uncertainty_flags")
    if isinstance(uncertainty_flags, list):
        normalized_flags = [str(flag).strip() for flag in uncertainty_flags if str(flag).strip()]
    elif isinstance(uncertainty_flags, str) and uncertainty_flags.strip():
        normalized_flags = [part.strip() for part in uncertainty_flags.split(",") if part.strip()]
    else:
        normalized_flags = []

    need_deep_work = item.get("need_deep_work", item.get("need_deep_thinking", False))
    if isinstance(need_deep_work, str):
        need_deep_work = need_deep_work.strip().lower() in {"1", "true", "yes", "y"}
    else:
        need_deep_work = bool(need_deep_work)

    return {
        "task_name": task_name,
        "priority": priority,
        "duration_minutes": duration_minutes,
        "estimated_duration": duration_minutes,
        "project": str(item.get("project") or "").strip(),
        "need_deep_work": need_deep_work,
        "need_deep_thinking": need_deep_work,
        "uncertainty_flags": normalized_flags,
        "uncertainty_level": "high" if normalized_flags else "medium",
        "date": input_date,
    }


def _extract_json_payload(text: str) -> Any:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise ValueError("empty llm output")
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def _normalize_task_list(items: Any, input_date: str) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError("llm output is not a list")
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_task_item(item, input_date) if isinstance(item, dict) else None
        if normalized:
            normalized_items.append(normalized)
    return normalized_items


def _default_llm_json_loader(text: str) -> Any:
    """Try to extract tasks via an optional LLM client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise RuntimeError("openai package is unavailable")

    prompt = (
        "Convert the user's daily task text into strict JSON only.\n"
        "Return a JSON array.\n"
        "Each item must contain exactly these fields: "
        "task_name, priority, duration_minutes, project, need_deep_work, uncertainty_flags.\n"
        "Do not include markdown fences, explanations, or any extra text.\n\n"
        f"User text:\n{text}"
    )

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=os.getenv("PLANNER_EXTRACTION_MODEL", "gpt-4.1-mini"),
        input=prompt,
    )
    output_text = getattr(response, "output_text", "") or ""
    return _extract_json_payload(output_text)


def _rule_extract_tasks(text: str, input_date: str) -> list[dict[str, Any]]:
    """Use the existing rule-based extractor as fallback."""
    try:
        from app import planner
    except ModuleNotFoundError:
        import planner  # type: ignore

    fallback_tasks = planner.extract_tasks_from_text(text, input_date=input_date)
    result: list[dict[str, Any]] = []
    for item in fallback_tasks:
        normalized = normalize_task_item(item, input_date)
        if normalized:
            result.append(normalized)
    return result


def extract_tasks(
    text: str,
    input_date: str,
    llm_json_loader: Callable[[str], Any] | None = None,
) -> list[dict[str, Any]]:
    """Use LLM first, then fall back to rule extraction."""
    llm_loader = llm_json_loader or _default_llm_json_loader
    try:
        llm_items = llm_loader(text)
        llm_tasks = _normalize_task_list(llm_items, input_date)
        if llm_tasks:
            return llm_tasks
    except Exception:
        pass

    return _rule_extract_tasks(text, input_date)
