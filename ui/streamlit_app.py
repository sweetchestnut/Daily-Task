"""Minimal Streamlit UI for the planner graph."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent

try:
    from app.graph_flow import run_graph
    from app.planner import DEFAULT_INPUT, load_input
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(ROOT_DIR))
    from app.graph_flow import run_graph  # type: ignore
    from app.planner import DEFAULT_INPUT, load_input  # type: ignore


st.set_page_config(page_title="Daily Planner", layout="wide")
st.title("本地日计划助手")

default_payload = load_input(DEFAULT_INPUT)
default_text = json.dumps(default_payload, ensure_ascii=False, indent=2)

input_text = st.text_area("今日输入区", value=default_text, height=260)

if st.button("运行今日规划"):
    try:
        payload = json.loads(input_text) if input_text.strip() else {}
    except json.JSONDecodeError as exc:
        st.error(f"输入 JSON 解析失败：{exc}")
    else:
        state = run_graph(payload)
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("自动提取任务区")
            st.json(state.get("extracted_tasks", []))
            st.subheader("排序结果区")
            st.json(state.get("ranked_tasks", []))

        with col2:
            st.subheader("时间块安排区")
            st.json(state.get("scheduled_tasks", []))
            st.subheader("提醒与警告")
            st.write("reminders")
            st.json(state.get("reminders", []))
            st.write("warnings")
            st.json(state.get("warnings", []))
