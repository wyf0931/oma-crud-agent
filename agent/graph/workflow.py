"""Main workflow orchestration with LangGraph."""

from datetime import datetime
import time
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state.types import AgentState
from agent.nodes import (
    understand_requirements,
    generate_modules,
    generate_fields,
    run_validation,
    generate_project,
    test_launch,
    output_result,
)
from agent.nodes.auto_fix import auto_fix_node
from shared.session.manager import SessionManager
from backend.core.config import settings
from shared.trace import session_trace_context, trace_event


def create_graph(session_manager: SessionManager) -> StateGraph:
    """Create the main workflow StateGraph."""

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
        }
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


def _timed_node(node_name, node):
    """Add wall-clock duration to every persisted milestone detail."""
    def run(state):
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


# Global graph instance
_graph = None
_session_manager = None


def initialize_graph():
    """Initialize the global graph instance."""
    global _graph, _session_manager

    _session_manager = SessionManager(settings.DATABASE_FILE)
    _graph = create_graph(_session_manager)


def get_graph():
    """Get the global graph instance."""
    global _graph
    if _graph is None:
        initialize_graph()
    return _graph


def run_workflow(session_id: str, user_input: str, mode: str):
    """Run the workflow for a session."""
    with session_trace_context(session_id):
        _run_workflow(session_id, user_input, mode)


def _run_workflow(session_id: str, user_input: str, mode: str):
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
        "status": "running"
    }

    config = {"configurable": {"thread_id": session_id}}

    # Run the workflow
    for event in graph.stream(initial_state, config):
        if isinstance(event, dict):
            for node_name, node_state in event.items():
                _session_manager.update(session_id, node_state)
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
    final_state = _graph.get_state(config)
    if final_state:
        values = dict(final_state.values)
        if values.get("status") in {"completed", "failed"}:
            values["finished_at"] = datetime.now().isoformat()
        _session_manager.update(session_id, values)
    trace_event("workflow_finished", status=final_state.values.get("status") if final_state else None)


def continue_workflow(session_id: str):
    """Continue workflow after HITL approval."""
    with session_trace_context(session_id):
        graph = get_graph()
        session = _session_manager.get(session_id)

        if not session:
            raise ValueError(f"Session {session_id} not found")

        config = {"configurable": {"thread_id": session_id}}
        trace_event("workflow_continued")
        for event in graph.stream(session, config):
            if isinstance(event, dict):
                for node_name, node_state in event.items():
                    _session_manager.update(session_id, node_state)
                    detail = (node_state.get("step_details") or {}).get(node_name, {})
                    trace_event("node_finished", node=node_name, summary=detail.get("summary"), error=detail.get("error"))
        _session_manager.update(session_id, {"finished_at": datetime.now().isoformat()})
        trace_event("workflow_finished", status=_session_manager.get(session_id).get("status"))
