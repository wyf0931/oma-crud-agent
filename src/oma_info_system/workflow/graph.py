"""Main workflow orchestration with LangGraph."""

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from oma_info_system.config import settings
from oma_info_system.platform.sessions import SessionManager
from oma_info_system.platform.trace import session_trace_context, trace_event
from oma_info_system.workflow.nodes import (
    generate_fields,
    generate_modules,
    generate_project,
    output_result,
    run_validation,
    test_launch,
    understand_requirements,
)
from oma_info_system.workflow.nodes.auto_fix import auto_fix_node
from oma_info_system.workflow.state import AgentState


def create_graph(session_manager: SessionManager) -> CompiledStateGraph:
    """Build and compile the main workflow graph."""

    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("understand_requirements", _timed_node("understand_requirements", understand_requirements))
    workflow.add_node("generate_modules", _timed_node("generate_modules", generate_modules))
    workflow.add_node("generate_fields", _timed_node("generate_fields", generate_fields))
    workflow.add_node("run_validation", _timed_node("run_validation", run_validation))
    workflow.add_node("generate_project", _timed_node("generate_project", generate_project))
    workflow.add_node("test_launch", _timed_node("test_launch", test_launch))
    workflow.add_node("auto_fix", _timed_node("auto_fix", auto_fix_node))
    workflow.add_node("output_result", _timed_node("output_result", output_result))

    # Set entry point
    workflow.set_entry_point("understand_requirements")

    # Define edges
    workflow.add_edge("understand_requirements", "generate_modules")
    workflow.add_edge("generate_modules", "generate_fields")
    workflow.add_edge("generate_fields", "run_validation")
    workflow.add_edge("run_validation", "generate_project")
    workflow.add_edge("generate_project", "test_launch")

    # Conditional edge for test results
    workflow.add_conditional_edges(
        "test_launch",
        should_retry_fix,
        {
            "success": "output_result",
            "retry": "auto_fix",
            "failed": "output_result",
        },
    )

    workflow.add_edge("auto_fix", "test_launch")
    workflow.add_edge("output_result", END)

    # Compile with checkpoint
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


def should_retry_fix(state: AgentState) -> str:
    """Determine if we should retry fixing or give up."""
    if state.get("test_errors") is None:
        return "success"

    if state["retry_count"] >= state["max_retries"]:
        return "failed"

    return "retry"


def _timed_node(node_name: str, node: Callable[[AgentState], AgentState]) -> Any:
    """Add wall-clock duration to every persisted milestone detail.

    Returns Any because LangGraph's StateNode union is not structurally
    satisfiable by a hand-written closure, while the runtime contract
    (AgentState in, AgentState out) is exact.
    """

    def run(state: AgentState) -> AgentState:
        started = time.perf_counter()
        result = node(state)
        duration_ms = round((time.perf_counter() - started) * 1000)
        details = dict(result.get("step_details") or {})
        detail = dict(details.get(node_name) or {})
        detail["duration_ms"] = duration_ms
        details[node_name] = detail
        for key in details:
            if key.startswith(f"{node_name}_"):
                details[key] = {**details[key], "duration_ms": duration_ms}
        result["step_details"] = details
        return result

    return run


# Lazily-initialized process-wide graph and session manager.
_graph: CompiledStateGraph | None = None
_session_manager: SessionManager | None = None


def initialize_graph() -> None:
    """Initialize the global graph instance."""
    global _graph, _session_manager

    _session_manager = SessionManager(settings.DATABASE_FILE)
    _graph = create_graph(_session_manager)


def get_graph() -> CompiledStateGraph:
    """Get the global graph instance, initializing it on first use."""
    global _graph
    if _graph is None:
        initialize_graph()
    assert _graph is not None
    return _graph


def get_session_manager() -> SessionManager:
    """Get the global session manager, initializing it on first use."""
    global _session_manager
    if _session_manager is None:
        initialize_graph()
    assert _session_manager is not None
    return _session_manager


def run_workflow(session_id: str, user_input: str, mode: Literal["yolo", "hitl"]):
    """Run the workflow for a session."""
    with session_trace_context(session_id):
        _run_workflow(session_id, user_input, mode)


def _run_workflow(session_id: str, user_input: str, mode: Literal["yolo", "hitl"]) -> None:
    graph = get_graph()
    trace_event("workflow_started", mode=mode)

    initial_state: AgentState = {
        "user_input": user_input,
        "mode": mode,
        "output_dir": settings.OUTPUT_DIR,
        "current_step": "",
        "step_history": [],
        "step_details": {},
        "project_name": None,
        "business_domain": None,
        "module_count_max": None,
        "field_count_max": None,
        "modules": None,
        "fields": None,
        "project_config": None,
        "project_path": None,
        "review_issues": [],
        "review_fixes": [],
        "test_errors": None,
        "retry_count": 0,
        "max_retries": 3,
        "approval_required": False,
        "pending_approval": None,
        "approval_response": None,
        "result": None,
        "error": None,
        "status": "running",
    }

    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    # Run the workflow
    for event in graph.stream(initial_state, config):
        if isinstance(event, dict):
            for node_name, node_state in event.items():
                get_session_manager().update(session_id, node_state)
                detail = (node_state.get("step_details") or {}).get(node_name, {})
                trace_event(
                    "node_finished",
                    node=node_name,
                    status=node_state.get("status"),
                    current_step=node_state.get("current_step"),
                    summary=detail.get("summary"),
                    error=detail.get("error") or node_state.get("error"),
                    duration_ms=detail.get("duration_ms"),
                    retry_count=node_state.get("retry_count"),
                    project_path=node_state.get("project_path"),
                )

    # Final update
    final_state = graph.get_state(config)
    if final_state:
        values = dict(final_state.values)
        if values.get("status") in {"completed", "failed"}:
            values["finished_at"] = datetime.now().isoformat()
        get_session_manager().update(session_id, values)
        trace_event("workflow_finished", status=values.get("status"))
    else:
        trace_event("workflow_finished", status=None)


def continue_workflow(session_id: str) -> None:
    """Continue workflow after HITL approval."""
    with session_trace_context(session_id):
        graph = get_graph()
        session = get_session_manager().get(session_id)

        if not session:
            raise ValueError(f"Session {session_id} not found")

        config: RunnableConfig = {"configurable": {"thread_id": session_id}}
        trace_event("workflow_continued")
        for event in graph.stream(session, config):
            if isinstance(event, dict):
                for node_name, node_state in event.items():
                    get_session_manager().update(session_id, node_state)
                    detail = (node_state.get("step_details") or {}).get(node_name, {})
                    trace_event(
                        "node_finished", node=node_name, summary=detail.get("summary"), error=detail.get("error")
                    )
        get_session_manager().update(session_id, {"finished_at": datetime.now().isoformat()})
        final = get_session_manager().get(session_id) or {}
        trace_event("workflow_finished", status=final.get("status"))
