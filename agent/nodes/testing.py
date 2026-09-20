"""Generated project validation node."""

import py_compile
from pathlib import Path

from agent.state.types import AgentState


def test_launch(state: AgentState) -> AgentState:
    """Run lightweight checks against the generated project.

    Generated projects have their own dependencies, so this node deliberately
    avoids installing packages or starting a long-running server. It verifies
    the generated files and compiles every Python file; real failures are
    passed to the auto-fix loop.
    """
    project_path = state.get("project_path")
    detail = {
        "title": "自检",
        "summary": "",
        "data": {"project_path": project_path, "checks": []},
        "error": None,
    }

    try:
        if not project_path:
            raise FileNotFoundError("Generated project path is missing")

        root = Path(project_path)
        if not root.is_dir():
            raise FileNotFoundError(f"Generated project directory not found: {root}")

        required_files = ("app.py", "models.py", "views.py", "config.py", "run.py")
        missing = [name for name in required_files if not (root / name).is_file()]
        if missing:
            raise FileNotFoundError(f"Generated project is missing: {', '.join(missing)}")
        detail["data"]["checks"].append("required_files")

        python_files = sorted(root.glob("*.py"))
        for source_file in python_files:
            py_compile.compile(str(source_file), doraise=True)
        detail["data"]["checks"].append("python_compile")

        state["test_errors"] = None
        detail["summary"] = f"静态启动检查通过 ({len(python_files)} 个 Python 文件)"
    except Exception as exc:
        state["test_errors"] = str(exc)
        detail["error"] = str(exc)
        detail["summary"] = f"静态启动检查失败: {exc}"

    details = dict(state.get("step_details") or {})
    attempt = state.get("retry_count", 0)
    details[f"test_launch_{attempt}"] = detail
    details["test_launch"] = detail
    state["step_details"] = details

    state["current_step"] = "test_launch"
    state["step_history"] = state.get("step_history", []) + ["test_launch"]
    return state
