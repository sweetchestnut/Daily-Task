"""Minimal Streamlit UI for the planner graph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent

try:
    from app.graph_flow import run_extract_flow, run_schedule_flow
    from app.planner import DEFAULT_INPUT, load_input
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(ROOT_DIR))
    from app.graph_flow import run_extract_flow, run_schedule_flow  # type: ignore
    from app.planner import DEFAULT_INPUT, load_input  # type: ignore


PRIORITY_OPTIONS = ["P0", "P1", "P2"]


def _build_editor_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        rows.append(
            {
                "task_name": task.get("task_name") or task.get("title") or "",
                "priority": str(task.get("priority") or "P1").upper(),
                "duration_minutes": int(task.get("duration_minutes", task.get("estimated_duration", 30)) or 30),
                "project": task.get("project", ""),
                "need_deep_work": bool(task.get("need_deep_work", task.get("need_deep_thinking", False))),
                "uncertainty_flags": ", ".join(task.get("uncertainty_flags", []))
                if isinstance(task.get("uncertainty_flags"), list)
                else str(task.get("uncertainty_flags") or ""),
                "delete": False,
            }
        )
    return rows


def _normalize_editor_rows(rows: list[dict[str, Any]], input_date: str) -> list[dict[str, Any]]:
    confirmed_tasks: list[dict[str, Any]] = []
    for row in rows:
        if row.get("delete"):
            continue
        task_name = str(row.get("task_name") or "").strip()
        if not task_name:
            continue
        flags = row.get("uncertainty_flags", "")
        if isinstance(flags, str):
            uncertainty_flags = [part.strip() for part in flags.split(",") if part.strip()]
        elif isinstance(flags, list):
            uncertainty_flags = [str(part).strip() for part in flags if str(part).strip()]
        else:
            uncertainty_flags = []
        duration_minutes = row.get("duration_minutes", 30)
        try:
            duration_minutes = max(30, int(duration_minutes))
        except (TypeError, ValueError):
            duration_minutes = 30
        priority = str(row.get("priority") or "P1").upper()
        if priority not in PRIORITY_OPTIONS:
            priority = "P1"
        need_deep_work = bool(row.get("need_deep_work", False))
        confirmed_tasks.append(
            {
                "task_name": task_name,
                "priority": priority,
                "duration_minutes": duration_minutes,
                "estimated_duration": duration_minutes,
                "project": str(row.get("project") or "").strip(),
                "need_deep_work": need_deep_work,
                "need_deep_thinking": need_deep_work,
                "uncertainty_flags": uncertainty_flags,
                "uncertainty_level": "high" if uncertainty_flags else "medium",
                "date": input_date,
            }
        )
    return confirmed_tasks


st.set_page_config(page_title="Daily Planner", layout="wide")
st.title("本地日计划助手")

default_payload = load_input(DEFAULT_INPUT)
default_text = json.dumps(default_payload, ensure_ascii=False, indent=2)

if "natural_text" not in st.session_state:
    st.session_state["natural_text"] = "今天先把 Streamlit 页面跑起来，再检查 LangGraph 节点流，晚上补项目记忆初始数据"
if "extract_state" not in st.session_state:
    st.session_state["extract_state"] = None
if "schedule_state" not in st.session_state:
    st.session_state["schedule_state"] = None
if "editable_tasks_table_seed" not in st.session_state:
    st.session_state["editable_tasks_table_seed"] = []

if st.button("加载示例输入"):
    st.session_state["natural_text"] = "先整理 Daily-Task，再补记忆，最后看一下 graph 输出"

natural_text = st.text_area(
    "自然语言输入今日任务",
    value=st.session_state.get("natural_text", ""),
    height=120,
)
input_text = st.text_area("今日输入区", value=default_text, height=260)

col_a, col_b = st.columns(2)
with col_a:
    extract_clicked = st.button("提取今日任务")
with col_b:
    confirm_clicked = st.button("确认任务并继续排程")

payload: dict[str, Any] = {}
json_error = None
try:
    payload = json.loads(input_text) if input_text.strip() else {}
except json.JSONDecodeError as exc:
    json_error = str(exc)

if json_error:
    st.error(f"输入 JSON 解析失败：{json_error}")

if extract_clicked and not json_error:
    if natural_text.strip():
        payload = {
            "date": payload.get("date") if isinstance(payload, dict) else None,
            "text_input": natural_text.strip(),
        }
    st.session_state["extract_state"] = run_extract_flow(payload)
    st.session_state["editable_tasks_table_seed"] = _build_editor_rows(
        list(st.session_state["extract_state"].get("editable_tasks", []))
    )
    st.session_state["schedule_state"] = None

extract_state = st.session_state.get("extract_state")
if extract_state:
    st.subheader("原始输入")
    st.json(extract_state.get("today_input", payload))

    st.subheader("自动提取任务")
    edited_df = st.data_editor(
        st.session_state.get("editable_tasks_table_seed", []),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "priority": st.column_config.SelectboxColumn("priority", options=PRIORITY_OPTIONS),
            "duration_minutes": st.column_config.NumberColumn("duration_minutes", min_value=0, step=15),
            "need_deep_work": st.column_config.CheckboxColumn("need_deep_work"),
            "delete": st.column_config.CheckboxColumn("delete"),
        },
        key="editable_tasks_table",
    )

    if confirm_clicked:
        input_date = str((extract_state.get("today_input") or {}).get("date") or "")
        confirmed_tasks = _normalize_editor_rows(list(edited_df), input_date)

        next_state = dict(extract_state)
        next_state["editable_tasks"] = confirmed_tasks
        next_state["approved"] = True
        next_state["review_required"] = False
        st.session_state["extract_state"] = next_state
        st.session_state["schedule_state"] = run_schedule_flow(next_state)

schedule_state = st.session_state.get("schedule_state")
if schedule_state:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("排序结果")
        st.json(schedule_state.get("ranked_tasks", []))
    with col2:
        st.subheader("时间块安排")
        st.json(schedule_state.get("scheduled_tasks", []))

    st.subheader("reminders")
    st.json(schedule_state.get("reminders", []))
    st.subheader("warnings")
    st.json(schedule_state.get("warnings", []))
