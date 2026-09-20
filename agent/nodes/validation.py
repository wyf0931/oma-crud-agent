"""Validation node."""

from agent.state.types import AgentState


def run_validation(state: AgentState) -> AgentState:
    """Run script-based validation on generated fields and modules."""
    modules = state.get("modules", [])
    fields = state.get("fields", {})
    issues = []

    # Check module naming
    for m in modules:
        if not m.get("name") or not m["name"][0].isupper():
            issues.append({"type": "naming", "message": f"Module '{m.get('name')}' is not PascalCase"})

    # Check each module has fields
    for m in modules:
        mf = fields.get(m["name"], [])
        if not mf:
            issues.append({"type": "missing", "message": f"Module '{m['name']}' has no fields"})

    state["review_issues"] = issues

    detail = {
        "title": "设计验证",
        "summary": f"检查 {len(modules)} 个模块, 发现 {len(issues)} 个问题" if issues else f"检查 {len(modules)} 个模块, 全部通过",
        "data": {"module_count": len(modules), "issues": issues},
        "error": None,
    }
    details = dict(state.get("step_details") or {})
    details["run_validation"] = detail
    state["step_details"] = details

    state["current_step"] = "run_validation"
    state["step_history"] = state.get("step_history", []) + ["run_validation"]
    return state
