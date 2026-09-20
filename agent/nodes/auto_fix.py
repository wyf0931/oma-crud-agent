"""Auto-fix node with thinking mode enabled."""

from pathlib import Path

from agent.state.types import AgentState
from agent.providers.openai_compatible import get_provider
from agent.json_utils import parse_json_response


def auto_fix_node(state: AgentState) -> AgentState:
    """Auto-fix errors using the configured LLM."""
    provider = get_provider()

    error_msg = state.get("test_errors", "Unknown error")
    retry_count = state.get("retry_count", 0)
    project_path = Path(state.get("project_path") or ".")
    existing_files = sorted(
        str(path.relative_to(project_path))
        for path in project_path.rglob("*")
        if path.is_file()
    ) if project_path.is_dir() else []

    prompt = f"""You are an expert Python debugger. The following error occurred when testing a generated Flask-Admin project:

Generated project: {project_path}
Existing generated files: {", ".join(existing_files) or "unknown"}

Error (attempt {retry_count + 1}/{state.get('max_retries', 3)}):
```
{error_msg}
```

Analyze the error and provide a fix:

1. Identify the root cause
2. Specify which file needs to be modified
3. Provide the exact fix (code change or command)

Only refer to files in the existing generated project. Do not invent modules,
folders, or files such as app/admin.py unless they are listed above.

Respond in JSON format:
{{
  "analysis": "Root cause analysis",
  "file_to_fix": "relative/path/to/file.py",
  "fix_type": "code|command|config",
  "fix_content": "The actual fix",
  "verification": "How to verify the fix"
}}

Return exactly one JSON object. Do not use Markdown fences or explanatory text."""

    detail = {
        "title": "修复",
        "summary": "",
        "thinking": None,
        "prompt": prompt,
        "response": None,
        "data": None,
        "error": None,
    }

    try:
        resp = provider.call_detailed(
            prompt=prompt,
        )
        detail["response"] = resp.get("content")
        detail["thinking"] = resp.get("thinking")
        fix_info = parse_json_response(resp.get("content"))

        state["retry_count"] = retry_count + 1
        state["review_fixes"] = state.get("review_fixes", []) + [
            f"Attempt {retry_count + 1}: {fix_info.get('analysis', 'N/A')}"
        ]

        detail["summary"] = f"修复尝试 {retry_count + 1}: {fix_info.get('analysis', 'N/A')[:60]}"
        detail["thinking"] = resp.get("thinking")
        detail["response"] = resp["content"]
        detail["data"] = fix_info

    except Exception as e:
        state["error"] = f"Auto-fix failed: {e}"
        state["retry_count"] = state.get("max_retries", 3)
        detail["error"] = str(e)
        detail["summary"] = f"修复失败: {e}"

    # Use indexed key so each retry is recorded separately, plus a canonical
    # "auto_fix" key that always reflects the latest attempt (the UI's
    # milestone lookup hits the canonical key).
    details = dict(state.get("step_details") or {})
    details[f"auto_fix_{retry_count}"] = detail
    details["auto_fix"] = detail
    state["step_details"] = details

    state["current_step"] = "auto_fix"
    state["step_history"] = state.get("step_history", []) + ["auto_fix"]
    return state
