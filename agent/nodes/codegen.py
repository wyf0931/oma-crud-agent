"""Code generation node — delegates to Jinja2 template-based CodeGenerator."""

import os
from pathlib import Path
from agent.state.types import AgentState
from shared.trace import trace_event


def generate_project(state: AgentState) -> AgentState:
    """Build project config and render the Flask-Admin project templates."""
    import traceback

    detail = {
        "title": "生成项目",
        "summary": "",
        "data": None,
        "error": None,
    }

    try:
        from codegen.generator import CodeGenerator

        output_dir = os.path.expanduser(state.get("output_dir", "data/projects"))
        project_config = state.get("project_config") or _build_config(state)
        state["project_config"] = project_config

        generator = CodeGenerator()
        project_path = generator.generate(
            project_config=project_config,
            output_dir=output_dir,
        )

        state["project_path"] = project_path

        gen_files = []
        for p in sorted(Path(project_path).rglob("*")):
            if p.is_file() and '__pycache__' not in str(p):
                gen_files.append(str(p.relative_to(project_path)))

        detail["summary"] = f"生成 {len(gen_files)} 个文件"
        detail["data"] = {"project_path": project_path, "files": gen_files}
        trace_event("files_generated", project_path=project_path, file_count=len(gen_files), files=gen_files)

    except Exception as e:
        print(f"[CODEGEN] Error: {e}")
        traceback.print_exc()
        state["error"] = f"Failed to generate code: {e}"
        state["project_path"] = None
        detail["error"] = str(e)
        detail["summary"] = f"代码生成失败: {e}"

    details = dict(state.get("step_details") or {})
    details["generate_project"] = detail
    state["step_details"] = details

    state["current_step"] = "generate_project"
    state["step_history"] = state.get("step_history", []) + ["generate_project"]
    return state


def _build_config(state: AgentState) -> dict:
    """Build the template configuration from the workflow state."""
    import secrets
    import string
    import random

    code_chars = string.ascii_lowercase + string.digits
    project_code = ''.join(random.choices(code_chars[:5], k=5))

    return {
        "project": {
            "code": project_code,
            "name": state.get("project_name", "Admin System"),
            "version": "V1.0",
            "theme": "yeti",
            "secret_key": secrets.token_hex(32),
            "admin_account": "admin",
            "admin_password": "admin123",
        },
        "modules": state.get("modules", []),
        "fields": state.get("fields", {}),
    }
