"""Validation node."""

from oma_info_system.workflow.state import AgentState, ReviewIssue


def run_validation(state: AgentState) -> AgentState:
    """Run script-based validation on generated fields and modules."""
    modules = state.get("modules") or []
    fields = state.get("fields") or {}
    issues: list[ReviewIssue] = []

    # Check module naming
    for m in modules:
        name = m.get("name") or ""
        if not name or not name[0].isupper():
            issues.append(
                {
                    "type": "naming",
                    "severity": "warning",
                    "message": f"Module '{name}' is not PascalCase",
                    "suggestion": "Rename the module so it starts with an uppercase letter",
                }
            )

    # Check each module has fields
    for m in modules:
        name = m.get("name") or ""
        if not fields.get(name):
            issues.append(
                {
                    "type": "missing",
                    "severity": "error",
                    "message": f"Module '{name}' has no fields",
                    "suggestion": "Add at least one field to this module",
                }
            )

    state["review_issues"] = issues

    detail = {
        "title": "设计验证",
        "summary": f"检查 {len(modules)} 个模块, 发现 {len(issues)} 个问题"
        if issues
        else f"检查 {len(modules)} 个模块, 全部通过",
        "data": {"module_count": len(modules), "issues": issues},
        "error": None,
    }
    details = dict(state.get("step_details") or {})
    details["run_validation"] = detail
    state["step_details"] = details

    state["current_step"] = "run_validation"
    state["step_history"] = state.get("step_history", []) + ["run_validation"]
    return state
