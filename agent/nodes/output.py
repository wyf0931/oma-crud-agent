"""Output node."""

from agent.state.types import AgentState


def output_result(state: AgentState) -> AgentState:
    """Generate final result."""
    is_ok = not state.get("error")
    state["status"] = "completed" if is_ok else "failed"
    state["current_step"] = "output_result"
    state["step_history"] = state.get("step_history", []) + ["output_result"]

    detail = {
        "title": "完成",
        "summary": "生成完成" if is_ok else f"生成失败: {state.get('error', '')}",
        "data": {
            "project_path": state.get("project_path"),
            "modules": [m["name"] for m in (state.get("modules") or [])],
            "total_steps": len(state.get("step_history", [])),
            "fixes_applied": len(state.get("review_fixes", [])),
        },
        "error": state.get("error"),
    }
    details = dict(state.get("step_details") or {})
    details["output_result"] = detail
    state["step_details"] = details

    return state
