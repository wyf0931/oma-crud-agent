from pathlib import Path
from typing import cast

from oma_info_system.workflow.nodes.testing import test_launch as run_test_launch
from oma_info_system.workflow.state import AgentState


def _state(project_path: str) -> AgentState:
    return cast(
        AgentState,
        {
            "project_path": project_path,
            "step_history": [],
            "step_details": {},
            "test_errors": None,
        },
    )


def test_test_launch_passes_valid_generated_project(tmp_path):
    for name in ("app.py", "models.py", "views.py", "config.py", "run.py"):
        (tmp_path / name).write_text("value = 1\n")

    result = run_test_launch(_state(str(tmp_path)))

    assert result["test_errors"] is None
    assert "通过" in result["step_details"]["test_launch"]["summary"]


def test_test_launch_reports_invalid_python(tmp_path):
    for name in ("app.py", "models.py", "views.py", "config.py", "run.py"):
        (tmp_path / name).write_text("value = 1\n")
    (Path(tmp_path) / "app.py").write_text("def broken(:\n")

    result = run_test_launch(_state(str(tmp_path)))

    assert result["test_errors"]
    assert result["step_details"]["test_launch"]["error"]
