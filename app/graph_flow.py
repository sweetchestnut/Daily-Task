"""Minimal LangGraph flow wrapper for the planner."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:
    END = "END"
    START = "START"
    StateGraph = None

try:
    from app.graph_nodes import (
        extract_today_tasks_node,
        load_input_node,
        load_memory_node,
        rank_tasks_node,
        review_node,
        save_results_node,
        schedule_tasks_node,
    )
    from app.graph_state import PlannerState
    from app.planner import DEFAULT_INPUT, load_input
except ModuleNotFoundError:
    from graph_nodes import (  # type: ignore
        extract_today_tasks_node,
        load_input_node,
        load_memory_node,
        rank_tasks_node,
        review_node,
        save_results_node,
        schedule_tasks_node,
    )
    from graph_state import PlannerState  # type: ignore
    from planner import DEFAULT_INPUT, load_input  # type: ignore


def build_extract_graph():
    if StateGraph is None:
        return None
    graph = StateGraph(PlannerState)
    graph.add_node("load_input_node", load_input_node)
    graph.add_node("load_memory_node", load_memory_node)
    graph.add_node("extract_today_tasks_node", extract_today_tasks_node)

    graph.add_edge(START, "load_input_node")
    graph.add_edge("load_input_node", "load_memory_node")
    graph.add_edge("load_memory_node", "extract_today_tasks_node")
    graph.add_edge("extract_today_tasks_node", END)
    return graph.compile()


def build_schedule_graph():
    if StateGraph is None:
        return None
    graph = StateGraph(PlannerState)
    graph.add_node("rank_tasks_node", rank_tasks_node)
    graph.add_node("schedule_tasks_node", schedule_tasks_node)
    graph.add_node("review_node", review_node)
    graph.add_node("save_results_node", save_results_node)

    graph.add_edge(START, "rank_tasks_node")
    graph.add_edge("rank_tasks_node", "schedule_tasks_node")
    graph.add_edge("schedule_tasks_node", "review_node")
    graph.add_edge("review_node", "save_results_node")
    graph.add_edge("save_results_node", END)
    return graph.compile()


def run_extract_flow(raw_input: dict | str | None = None) -> PlannerState:
    graph = build_extract_graph()
    state: PlannerState = {
        "raw_input": raw_input or {},
        "warnings": [],
        "approved": False,
        "editable_tasks": [],
        "review_required": False,
    }
    if graph is not None:
        return graph.invoke(state)
    for node in (load_input_node, load_memory_node, extract_today_tasks_node):
        state.update(node(state))
    return state


def run_schedule_flow(state: PlannerState) -> PlannerState:
    current = dict(state)
    current["extracted_tasks"] = list(current.get("editable_tasks") or current.get("extracted_tasks", []))
    if not current.get("approved", False):
        current["review_required"] = True
        return current

    graph = build_schedule_graph()
    if graph is not None:
        return graph.invoke(current)
    for node in (rank_tasks_node, schedule_tasks_node, review_node, save_results_node):
        current.update(node(current))
    return current


def run_graph(raw_input: dict | None = None) -> PlannerState:
    initial_state = run_extract_flow(raw_input)
    initial_state["approved"] = True
    return run_schedule_flow(initial_state)


def _print_graph_result(state: PlannerState) -> None:
    print("提取任务")
    for index, task in enumerate(state.get("extracted_tasks", []), start=1):
        print(f"{index}. {task.get('task_name') or task.get('title') or '未命名任务'}")

    print("\n排序结果")
    for index, task in enumerate(state.get("ranked_tasks", []), start=1):
        print(f"{index}. {task.get('task_name') or task.get('title') or '未命名任务'}")

    print("\n时间块安排")
    for item in state.get("scheduled_tasks", []):
        task = item.get("task", {})
        name = task.get("task_name") or task.get("title") or "未命名任务"
        print(f"- {item.get('time_block', '')}：{name}")

    print("\n提醒")
    for line in state.get("reminders", []):
        print(f"- {line}")

    warnings = state.get("warnings", [])
    if warnings:
        print("\n警告")
        for line in warnings:
            print(f"- {line}")


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    payload = load_input(input_path)
    state = run_graph(payload)
    _print_graph_result(state)


if __name__ == "__main__":
    main()
